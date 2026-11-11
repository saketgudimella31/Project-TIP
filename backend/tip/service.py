import hashlib
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import PurePosixPath

import httpx
from pydantic import ValidationError

from .config import Settings
from .batching import AnalysisAccumulator, iter_artifact_batches
from .documents import (
    DocumentBundle,
    create_business_document,
    create_document,
    render_generated_diagrams,
)
from .extraction import Extractor, jira_stories, safe_path, source_directory
from .gateway import Gateway, GatewayError
from .models import AnalysisOptions, Artifact, InputContext, SourceType, SupportingInputs
from .storage import Store, now
from .validation import add_backend_warnings, validate_merged_result, validate_result
from codebase_rag.services.knowledge.local_store import EmbeddingError

logger = logging.getLogger(__name__)
MIN_ADAPTIVE_CHUNK_CHARACTERS = 1_000


class Cancelled(Exception):
    pass


@dataclass
class Upload:
    name: str
    content: bytes
    kind: SourceType


def repo_identifier(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()[:20]


class TaskManager:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        gateway: Gateway,
    ):
        self.settings = settings
        self.store = store
        self.gateway = gateway
        self.executor = ThreadPoolExecutor(
            max_workers=settings.max_concurrent_tasks, thread_name_prefix="tip"
        )
        self.lock = threading.RLock()
        self.events: dict[str, threading.Event] = {}

    def submit(self, metadata: dict, operation):
        with self.lock:
            if len(self.events) >= self.settings.max_concurrent_tasks * 4:
                raise ValueError("Task queue is full; wait for an existing task to finish")
            task = self.store.create(metadata)
            event = threading.Event()
            self.events[task["task_id"]] = event
            self.executor.submit(self.run, task["task_id"], event, operation)
        return task

    def check(self, task_id: str):
        event = self.events.get(task_id)
        if event and event.is_set():
            raise Cancelled()

    def _wait_for_gateway_retry(self, task_id: str, delay: float):
        event = self.events.get(task_id)
        if event is not None and event.wait(delay):
            raise Cancelled()
        if event is None:
            time.sleep(delay)
        self.check(task_id)

    def progress(self, task_id: str, progress: int, message: str):
        with self.lock:
            self.check(task_id)
            self.store.update(task_id, status="running", progress=progress, message=message)

    def run(self, task_id, event, operation):
        start = time.monotonic()
        try:
            with self.lock:
                self.check(task_id)
                self.store.update(task_id, status="running", started_at=now())
            result, document = operation(task_id)
            business_document = None
            if isinstance(document, DocumentBundle):
                business_document = document.business
                document = document.technical
            result["duration_ms"] = round((time.monotonic() - start) * 1000)
            with self.lock:
                self.check(task_id)
                self.store.complete(task_id, result, document, business_document)
        except Cancelled:
            pass
        except Exception as error:
            missing_name = None
            if isinstance(error, ValidationError):
                message = "Model/input schema validation failed: " + "; ".join(
                    f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
                    for item in error.errors(include_input=False)[:8]
                )
            elif isinstance(error, httpx.RemoteProtocolError):
                message = (
                    "Remote service closed the connection without a valid HTTP response "
                    "(RemoteProtocolError); verify the configured endpoint, request signing, "
                    "and network/proxy/VPN connectivity."
                )
            elif isinstance(error, httpx.HTTPError):
                message = f"An integration request failed ({type(error).__name__}); check connectivity"
            elif isinstance(error, FileNotFoundError):
                missing_name = (
                    PurePosixPath(str(error.filename).replace("\\", "/")).name
                    if error.filename else "unknown item"
                )
                message = f"Required file or executable not found: {missing_name}"
            elif isinstance(error, (ValueError, EmbeddingError)):
                message = str(error)
            else:
                message = f"Processing failed ({type(error).__name__}); see backend configuration"
            # Keep diagnostics useful without logging secrets, source content, or absolute paths.
            if missing_name:
                logger.error(
                    "Task %s failed: %s (missing %s)",
                    task_id, type(error).__name__, missing_name,
                )
            elif isinstance(error, httpx.RemoteProtocolError):
                logger.error("Task %s failed: %s", task_id, message)
            else:
                logger.error("Task %s failed: %s", task_id, type(error).__name__)
            with self.lock:
                if not event.is_set():
                    self.store.update(
                        task_id, status="failed", progress=100, message="Failed",
                        error=message, completed_at=now(),
                    )
        finally:
            with self.lock:
                self.events.pop(task_id, None)

    def cancel(self, task_id: str):
        with self.lock:
            task = self.store.get(task_id)
            if not task:
                raise KeyError(task_id)
            if task["status"] not in {"pending", "running"}:
                raise ValueError("Only queued or running tasks can be cancelled")
            event = self.events.get(task_id)
            if event:
                event.set()
            return self.store.update(
                task_id, status="cancelled", completed_at=now(),
                message="Cancelled; any in-flight integration call may finish but will not publish results",
            )

    def close(self):
        with self.lock:
            for task_id in list(self.events):
                self.cancel(task_id)
        self.executor.shutdown(wait=True, cancel_futures=False)

    def retrieve(
        self, repo_id: str, focus: str, limit: int | None = None,
        path_prefix: str | None = None,
    ) -> list[Artifact]:
        limit = min(limit or self.settings.max_analysis_files, self.settings.max_analysis_files)
        if not self.settings.rag_base_url or not focus:
            artifacts = self.store.rag_retrieve(
                repo_id, focus, limit=limit, path_prefix=path_prefix,
            )
        else:
            with httpx.Client(timeout=30, follow_redirects=False) as client:
                response = client.get(
                    f"{self.settings.rag_base_url}/context/pack",
                    params={"repoId": repo_id, "focus": focus, "keywords": focus, "budget": 12000},
                )
            if response.status_code != 200:
                raise ValueError(f"External source selector returned HTTP {response.status_code}")
            pack = response.json()
            paths = []
            seen_paths = set()
            for item in pack.get("items", []):
                if not isinstance(item, dict):
                    raise ValueError("External source selector returned an invalid item")
                path = (item.get("extra") or {}).get("path") or item.get("ref")
                if (
                    isinstance(path, str) and path not in seen_paths
                    and (not path_prefix or path.startswith(path_prefix))
                ):
                    paths.append(path)
                    seen_paths.add(path)
            paths = paths[:limit]
            artifacts = self.store.retrieve_refs(repo_id, paths)
            matched_paths = {a.filePath for a in artifacts}
            if not paths or set(paths) - matched_paths:
                raise ValueError(
                    "External source selector returned missing or unknown source paths. Index the same "
                    "readable code locally before analysis; summaries alone cannot verify implementation."
                )
        if not artifacts:
            raise ValueError("No matching indexed source content; ingest the repository or change the focus")
        return artifacts

    def analyze(self, task_id: str, options: AnalysisOptions, uploads: list[Upload]):
        extractor = Extractor(self.settings)
        self.progress(task_id, 10, "Extracting and normalizing source artifacts")
        uploaded_artifacts: list[Artifact] = []
        code_uploads = [u for u in uploads if u.kind == "CODE"]
        if options.code_source != "uploads" and code_uploads:
            raise ValueError("Code uploads cannot be combined with a different code source")
        if options.selected_path and options.code_source == "uploads":
            raise ValueError("Use folder/file selection for uploads instead of a repository path")
        for upload in uploads:
            self.check(task_id)
            uploaded_artifacts.extend(extractor.extract(upload.name, upload.content, upload.kind))
        uploaded_artifacts.extend(jira_stories(options.jira_issue_keys, self.settings, extractor))
        uploaded_artifacts.extend(extractor.story(story) for story in options.manual_stories)
        code = [a for a in uploaded_artifacts if a.sourceType == "CODE"]
        supporting_artifacts = [a for a in uploaded_artifacts if a.sourceType != "CODE"]
        source = {
            "repository": options.repo_url, "local": options.local_path,
            "indexed": options.indexed_repo_id, "uploads": None,
        }[options.code_source]
        repository_id = None
        index_result = {"files_indexed": 0, "characters_indexed": 0, "warnings": []}
        indexed_scope_prefix = None
        code_file_count = 0
        code_character_count = 0
        code_factory = lambda: iter(())
        if options.code_source in {"repository", "local"}:
            if source is None:
                raise ValueError("Repository or local source is required")
            repository_id = repo_identifier(source)
            with source_directory(
                self.settings, repo_url=options.repo_url if options.code_source == "repository" else None,
                local_path=options.local_path if options.code_source == "local" else None,
                branch=options.branch, selected_path=options.selected_path,
            ) as root:
                index_result = self.store.index_batches(
                    repository_id,
                    extractor.iter_directory(root, options.selected_path or ""),
                    batch_size=self.settings.repository_index_batch_files,
                    check=lambda: self.check(task_id),
                    progress=lambda count: self.progress(
                        task_id,
                        min(25, 12 + count * 13 // self.settings.max_repository_files),
                        f"Indexed {count:,} repository files locally",
                    ),
                )
            code_file_count = index_result["files_indexed"]
            code_character_count = index_result["characters_indexed"]
            if code_file_count:
                code_factory = lambda: self.store.iter_artifacts(
                    repository_id, batch_size=self.settings.repository_index_batch_files,
                )
            else:
                repository_id = None
                code_factory = lambda: iter(())
                index_result["warnings"].append(
                    "No readable code files were found in the repository source."
                )
        elif options.code_source == "indexed":
            repository_id = options.indexed_repo_id
            if options.selected_path:
                selected_path = safe_path(options.selected_path)
                if selected_path != ".":
                    indexed_scope_prefix = selected_path.rstrip("/") + "/"
            self.progress(task_id, 18, "Preparing complete indexed source scope")
            code_file_count, code_character_count = self.store.index_stats(
                repository_id, indexed_scope_prefix,
            )
            if not code_file_count:
                raise ValueError(
                    "No matching indexed source content; ingest the repository or change the selected path"
                )
            code_factory = lambda: self.store.iter_artifacts(
                repository_id, indexed_scope_prefix,
                batch_size=self.settings.repository_index_batch_files,
            )
        elif code:
            source = "uploads:" + "|".join(f"{a.filePath}:{a.sha256}" for a in code)
            repository_id = repo_identifier(source)
            self.progress(task_id, 20, "Preparing code context for analysis")
            graph_result = self.store.index(repository_id, code)
            index_result = {
                "files_indexed": len(code),
                "characters_indexed": sum(len(a.content) for a in code),
                "warnings": graph_result.get("warnings", []),
            }
            code_file_count = len(code)
            code_character_count = index_result["characters_indexed"]
            code_factory = lambda: iter(code)
        if not code_file_count and not supporting_artifacts:
            raise ValueError("NO_ANALYZABLE_INPUT: provide readable code, design, stories, or requirements")

        supporting_ids = {
            (artifact.sourceType, artifact.sourceName, artifact.externalId)
            for artifact in supporting_artifacts
        }
        total_artifact_count = code_file_count + len(supporting_artifacts)
        total_artifact_characters = (
            code_character_count + sum(len(a.content) for a in supporting_artifacts)
        )
        knowledge_warnings = []
        if self.store.knowledge:
            if (
                total_artifact_count <= self.settings.max_knowledge_index_files
                and total_artifact_characters <= self.settings.max_knowledge_index_characters
            ):
                self.progress(task_id, 30, "Preparing supplied evidence for model analysis")
                knowledge_artifacts = [*code_factory(), *supporting_artifacts]
                knowledge_documents = [
                    {
                        "ref": f"{index}:{artifact.filePath or artifact.sourceName}",
                        "content": artifact.content,
                        "metadata": artifact.model_dump(exclude={"content"}),
                    }
                    for index, artifact in enumerate(knowledge_artifacts)
                ]
                with self.store.connect() as db:
                    self.store.knowledge.index(db, f"analysis:{task_id}", knowledge_documents)
            else:
                knowledge_warnings.append(
                    "Analysis-specific semantic indexing was skipped because the complete input "
                    "exceeds the configured knowledge-index size limits."
                )
        host = (options.repo_url or "").lower() if options.code_source == "repository" else ""
        provider = (
            "GITHUB" if "://github.com/" in host else
            "GITLAB" if "gitlab" in host else
            "BITBUCKET" if "://bitbucket.org/" in host else
            "OTHER" if options.code_source == "repository" else None
        )
        input_type = {
            "repository": "REPOSITORY_PATH" if options.selected_path else "REPOSITORY",
            "local": "LOCAL_FOLDER", "indexed": "INTEGRATION", "uploads": options.upload_kind,
        }[options.code_source]
        if options.code_source == "uploads" and any(u.name.lower().endswith(".zip") for u in code_uploads):
            input_type = "ARCHIVE"
        context = InputContext(
            analysisMode=options.analysis_mode, inputType=input_type,
            sourceProvider=provider,
            repository=source if options.code_source in {"repository", "indexed"} else None,
            branch=options.branch if options.code_source == "repository" else None,
            selectedPath=options.selected_path,
            supportingInputs=SupportingInputs(
                designDocumentsProvided=any(
                    a.sourceType == "DESIGN_DOCUMENT" for a in supporting_artifacts
                ),
                jiraUserStoriesProvided=any(
                    a.sourceType == "JIRA_USER_STORY" for a in supporting_artifacts
                ),
                rawRequirementsProvided=any(
                    a.sourceType == "RAW_REQUIREMENT" for a in supporting_artifacts
                ),
            ),
            analysisFocus=options.focus,
        )
        self.progress(task_id, 40, "Analyzing all eligible artifacts in bounded model batches")
        accumulator = AnalysisAccumulator()
        completed_characters = 0
        successful_batches = 0
        request_count = 0
        last_progress = 40

        def analyze_batch(batch: list[Artifact]):
            nonlocal completed_characters, successful_batches, request_count, last_progress
            self.check(task_id)
            batch_code = [item for item in batch if item.sourceType == "CODE"]
            batch_coverage = {
                "indexedCodeFiles": code_file_count,
                "retrievedCodeFiles": len({
                    item.filePath or item.sourceName for item in batch_code
                }),
                "retrievedCharacters": sum(len(item.content) for item in batch_code),
                "selectionMethod": "all-file bounded batch analysis",
            }

            def smaller_batches():
                if len(batch) > 1:
                    midpoint = len(batch) // 2
                    return [batch[:midpoint], batch[midpoint:]]
                if len(batch[0].content) > MIN_ADAPTIVE_CHUNK_CHARACTERS:
                    return list(iter_artifact_batches(
                        batch, max_files=1,
                        max_characters=max(
                            MIN_ADAPTIVE_CHUNK_CHARACTERS,
                            len(batch[0].content) // 2,
                        ),
                    ))
                return []

            batch_context = context.model_copy(update={
                "supportingInputs": SupportingInputs(
                    designDocumentsProvided=any(
                        item.sourceType == "DESIGN_DOCUMENT" for item in batch
                    ),
                    jiraUserStoriesProvided=any(
                        item.sourceType == "JIRA_USER_STORY" for item in batch
                    ),
                    rawRequirementsProvided=any(
                        item.sourceType == "RAW_REQUIREMENT" for item in batch
                    ),
                ),
            })
            retry_attempt = 0
            while True:
                self.check(task_id)
                request_count += 1
                batch_coverage["batchRequestNumber"] = request_count
                try:
                    result = self.gateway.analyze(
                        options.target_application, batch_context, batch,
                        coverage=batch_coverage,
                    )
                except GatewayError as error:
                    if error.status_code != 504:
                        raise
                    smaller = smaller_batches()
                    if smaller:
                        for sub_batch in smaller:
                            analyze_batch(sub_batch)
                        return
                    retry_attempt += 1
                    delay = min(60.0, 2 ** min(retry_attempt - 1, 6))
                    message = (
                        "The AI gateway timed out on the smallest batch; "
                        f"retrying in {delay:g} seconds (attempt {retry_attempt})"
                    )
                    logger.warning("Task %s: %s", task_id, message)
                    self.progress(task_id, last_progress, message)
                    self._wait_for_gateway_retry(task_id, delay)
                    continue
                except ValueError as error:
                    if str(error).startswith("Model input exceeds the configured context limit"):
                        smaller = smaller_batches()
                        if smaller:
                            for sub_batch in smaller:
                                analyze_batch(sub_batch)
                            return
                    raise
                break

            self.check(task_id)
            validate_result(result, batch, context, options.target_application)
            accumulator.add(result)
            successful_batches += 1
            completed_characters += sum(len(item.content) for item in batch)
            progress = 40 + min(
                32, completed_characters * 32 // max(total_artifact_characters, 1),
            )
            if progress > last_progress:
                last_progress = progress
                self.progress(
                    task_id, progress, f"Analyzed {completed_characters:,} of "
                    f"{total_artifact_characters:,} source characters "
                    f"across {successful_batches:,} model batches",
                )

        for batch in iter_artifact_batches(
            _all_artifacts(code_factory, supporting_artifacts),
            max_files=self.settings.analysis_batch_files,
            max_characters=min(
                self.settings.analysis_batch_characters,
                self.settings.max_analysis_characters,
            ),
        ):
            analyze_batch(batch)

        result = accumulator.finish(
            context,
            expected_code_files=code_file_count,
            expected_supporting_artifacts=len(supporting_ids),
        )
        validate_merged_result(
            result, context, options.target_application,
            expected_code_files=code_file_count,
            expected_supporting_artifacts=len(supporting_ids),
        )
        coverage = None
        if code_file_count:
            coverage = {
                "indexedCodeFiles": code_file_count,
                "retrievedCodeFiles": code_file_count,
                "retrievedCharacters": code_character_count,
                "selectionMethod": "all-file bounded batch analysis",
                "analysisBatchCount": successful_batches,
            }
        self.progress(task_id, 75, "Validating merged output and preparing the report")
        extraction_warnings = [
            *extractor.warnings, *index_result["warnings"], *knowledge_warnings,
        ]
        if extractor.excluded_count:
            extraction_warnings.append(
                f"Excluded {extractor.excluded_count} sensitive, generated, or dependency paths."
            )
        if extractor.unsupported_count:
            extraction_warnings.append(
                f"Omitted {extractor.unsupported_count} unsupported or unreadable files."
            )
        if options.focus:
            extraction_warnings.append(
                "Analysis focus was supplied as guidance and did not exclude eligible files."
            )
        warning_artifacts = list(supporting_artifacts)
        if code_file_count:
            warning_artifacts.append(next(iter(code_factory())))
        add_backend_warnings(result, context, warning_artifacts, extraction_warnings)
        result.analysisScope.excludedFiles = list(dict.fromkeys([
            *result.analysisScope.excludedFiles, *extractor.excluded_files,
        ]))
        result.analysisScope.unsupportedFiles = list(dict.fromkeys([
            *result.analysisScope.unsupportedFiles, *extractor.unsupported_files,
        ]))
        if code_file_count:
            result.analysisScope.scopeDescription = (
                f"Analyzed all {code_file_count:,} eligible readable code files across "
                f"{successful_batches:,} bounded model batches."
            )
        else:
            result.analysisScope.scopeDescription = (
                f"Analyzed all {len(supporting_ids):,} supplied supporting artifacts."
            )
        if options.selected_path:
            result.analysisScope.scopeDescription += (
                f" Repository path scope: {options.selected_path}."
            )
        if options.focus:
            result.analysisScope.scopeDescription += f" Analysis focus: {options.focus}"
        self.progress(
            task_id, 80, "Rendering UML locally and generating both Word documents",
        )
        rendered_diagrams = render_generated_diagrams(result)
        document = create_document(result, rendered_diagrams)
        business_document = create_business_document(result, rendered_diagrams)
        self.check(task_id)
        indexed_files = (
            self.store.index_stats(repository_id, indexed_scope_prefix)[0]
            if repository_id and options.code_source == "indexed"
            else index_result["files_indexed"]
        )
        return {
            "analysis": result.model_dump(),
            "files_processed": extractor.file_count,
            "artifacts_processed": total_artifact_count,
            "files_indexed": indexed_files or code_file_count,
            "files_analyzed": code_file_count,
            "repository_coverage": coverage,
            "repo_id": repository_id,
            "document_url": f"/api/v1/tasks/{task_id}/document",
            "business_document_url": f"/api/v1/tasks/{task_id}/business-document",
            "json_url": f"/api/v1/tasks/{task_id}/analysis",
            "rag_scope": f"analysis:{task_id}",
        }, DocumentBundle(technical=document, business=business_document)


def _all_artifacts(code_factory, supporting_artifacts):
    yield from code_factory()
    yield from supporting_artifacts

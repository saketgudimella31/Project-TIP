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
from .documents import create_document
from .extraction import Extractor, jira_stories, source_directory
from .gateway import Gateway
from .models import AnalysisOptions, Artifact, InputContext, SourceType, SupportingInputs
from .storage import Store, now
from .validation import add_backend_warnings, validate_result

logger = logging.getLogger(__name__)


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
            result["duration_ms"] = round((time.monotonic() - start) * 1000)
            with self.lock:
                self.check(task_id)
                self.store.complete(task_id, result, document)
        except Cancelled:
            pass
        except Exception as error:
            if isinstance(error, ValidationError):
                message = "Model/input schema validation failed: " + "; ".join(
                    f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
                    for item in error.errors(include_input=False)[:8]
                )
            elif isinstance(error, httpx.HTTPError):
                message = f"An integration request failed ({type(error).__name__}); check connectivity"
            elif isinstance(error, ValueError):
                message = str(error)
            else:
                message = f"Processing failed ({type(error).__name__}); see backend configuration"
            # Log the exception type/task ID, not request bodies, tokens, or source content.
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

    def retrieve(self, repo_id: str, focus: str) -> list[Artifact]:
        if not self.settings.rag_base_url or not focus:
            artifacts = self.store.retrieve(repo_id, focus, self.settings.max_files)
        else:
            with httpx.Client(timeout=30, follow_redirects=False) as client:
                response = client.get(
                    f"{self.settings.rag_base_url}/context/pack",
                    params={"repoId": repo_id, "focus": focus, "keywords": focus, "budget": 12000},
                )
            if response.status_code != 200:
                raise ValueError(f"Existing RAG service returned HTTP {response.status_code}")
            pack = response.json()
            paths = set()
            for item in pack.get("items", []):
                if not isinstance(item, dict):
                    raise ValueError("RAG pack contains an invalid item")
                path = (item.get("extra") or {}).get("path") or item.get("ref")
                if isinstance(path, str):
                    paths.add(path)
            local = self.store.retrieve(repo_id, limit=self.settings.max_files)
            artifacts = [a for a in local if a.filePath in paths]
            matched_paths = {a.filePath for a in artifacts}
            if not paths or paths - matched_paths:
                raise ValueError(
                    "RAG returned missing/unknown source paths. Index the same readable code locally "
                    "before analysis; RAG summaries alone cannot verify implementation."
                )
        if not artifacts:
            raise ValueError("No matching indexed source content; ingest the repository or change the focus")
        return artifacts

    def analyze(self, task_id: str, options: AnalysisOptions, uploads: list[Upload]):
        extractor = Extractor(self.settings)
        self.progress(task_id, 10, "Extracting and normalizing source artifacts")
        artifacts: list[Artifact] = []
        code_uploads = [u for u in uploads if u.kind == "CODE"]
        if options.code_source != "uploads" and code_uploads:
            raise ValueError("Code uploads cannot be combined with a different code source")
        for upload in uploads:
            self.check(task_id)
            artifacts.extend(extractor.extract(upload.name, upload.content, upload.kind))
        source = {
            "repository": options.repo_url, "local": options.local_path,
            "indexed": options.indexed_repo_id, "uploads": None,
        }[options.code_source]
        if options.code_source in {"repository", "local"}:
            with source_directory(
                self.settings, repo_url=options.repo_url if options.code_source == "repository" else None,
                local_path=options.local_path if options.code_source == "local" else None,
                branch=options.branch, selected_path=options.selected_path,
            ) as root:
                artifacts.extend(extractor.directory(root, options.selected_path or ""))
        if options.code_source == "indexed":
            retrieval_method = (
                "external RAG file selector" if self.settings.rag_base_url and options.focus
                else "SQLite full-text search"
            )
            self.progress(task_id, 18, f"Retrieving indexed source with {retrieval_method}")
            artifacts.extend(self.retrieve(options.indexed_repo_id, options.focus))
            if options.selected_path:
                prefix = str(PurePosixPath(options.selected_path)).rstrip("/") + "/"
                artifacts = [
                    a for a in artifacts if a.sourceType != "CODE"
                    or (a.filePath or "").startswith(prefix)
                ]
        elif options.focus:
            raise ValueError("A retrieval focus is supported only with an indexed repository")
        if options.selected_path and options.code_source == "uploads":
            raise ValueError("Use folder/file selection for uploads instead of a repository path")
        code = [a for a in artifacts if a.sourceType == "CODE"]
        if code and options.code_source == "uploads":
            source = "uploads:" + "|".join(f"{a.filePath}:{a.sha256}" for a in code)
        if source and code and options.code_source != "indexed":
            self.store.index(repo_identifier(source), code)
        self.progress(task_id, 25, "Retrieving authorized Jira stories")
        artifacts.extend(jira_stories(options.jira_issue_keys, self.settings, extractor))
        for story in options.manual_stories:
            artifacts.append(extractor.story(story))
        if not artifacts:
            raise ValueError("NO_ANALYZABLE_INPUT: provide readable code, design, stories, or requirements")
        host = (options.repo_url or "").lower() if options.code_source == "repository" else ""
        provider = (
            "GITHUB" if "://github.com/" in host else
            "GITLAB" if "://gitlab.com/" in host else
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
                designDocumentsProvided=any(a.sourceType == "DESIGN_DOCUMENT" for a in artifacts),
                jiraUserStoriesProvided=any(a.sourceType == "JIRA_USER_STORY" for a in artifacts),
                rawRequirementsProvided=any(a.sourceType == "RAW_REQUIREMENT" for a in artifacts),
            ),
        )
        self.progress(task_id, 40, "Analyzing evidence with the configured model")
        result = self.gateway.analyze(options.target_application, context, artifacts)
        self.progress(task_id, 75, "Validating model output, provenance, and traceability")
        validate_result(result, artifacts, context, options.target_application)
        extraction_warnings = [*extractor.warnings]
        if extractor.excluded_files:
            extraction_warnings.append("Excluded sensitive/generated/dependency paths: " + ", ".join(extractor.excluded_files))
        if extractor.unsupported_files:
            extraction_warnings.append("Unsupported code files omitted: " + ", ".join(extractor.unsupported_files))
        add_backend_warnings(result, context, artifacts, extraction_warnings)
        result.analysisScope.excludedFiles = list(dict.fromkeys([
            *result.analysisScope.excludedFiles, *extractor.excluded_files,
        ]))
        result.analysisScope.unsupportedFiles = list(dict.fromkeys([
            *result.analysisScope.unsupportedFiles, *extractor.unsupported_files,
        ]))
        self.progress(task_id, 80, "Rendering UML locally and generating the Word document")
        document = create_document(result, self.settings)
        self.check(task_id)
        return {
            "analysis": result.model_dump(),
            "files_processed": extractor.file_count,
            "artifacts_processed": len(artifacts),
            "repo_id": repo_identifier(source) if source and options.code_source != "indexed" else options.indexed_repo_id,
            "document_url": f"/api/v1/tasks/{task_id}/document",
            "json_url": f"/api/v1/tasks/{task_id}/analysis",
        }, document

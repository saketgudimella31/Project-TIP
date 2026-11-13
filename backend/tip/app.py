import fnmatch
import hashlib
import io
import json
import os
import re
import subprocess
import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.datastructures import UploadFile

from .config import Settings
from .documents import mermaid_renderer_configured, mermaid_renderer_issue
from .extraction import Extractor, safe_path, source_directory
from .gateway import Gateway, prompt_file_issue
from .models import AnalysisOptions
from .service import TaskManager, Upload, repo_identifier
from .storage import Store
from .rag_routes import create_rag_router
from codebase_rag.services.graph.code_graph import CodeGraph, LIMITATIONS
from codebase_rag.services.knowledge.local_store import Embeddings, LocalKnowledge

logger = logging.getLogger(__name__)


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo_url: str | None = None
    local_path: str | None = None
    branch: str | None = None
    selected_path: str | None = None
    mode: str = "full"
    include_globs: list[str] = Field(default_factory=list)
    exclude_globs: list[str] = Field(default_factory=list)
    since_commit: str | None = None
    repo_id: str | None = Field(default=None, min_length=1, max_length=200)


class ProcessDocumentRequest(BaseModel):
    content: str = Field(min_length=1, max_length=150_000)
    filename: str = "document.txt"
    document_type: str = "CODE"


class ProcessDirectoryRequest(BaseModel):
    directory_path: str
    file_patterns: list[str] = Field(default_factory=list)
    recursive: bool = True


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    graph_path = config.data_dir / ("code.kuzu" if config.graph_backend == "kuzu" else "code-graph.sqlite3")
    graph = CodeGraph(graph_path, config.graph_backend)
    knowledge = LocalKnowledge(
        config.data_dir / "tip.sqlite3",
        Embeddings(config.embedding_provider, config.embedding_model, config.embedding_dimension),
        config.rag_chunk_characters,
    )
    store = Store(
        config.data_dir / "tip.sqlite3", graph, knowledge,
        max_graph_files=config.max_graph_index_files,
        max_graph_characters=config.max_graph_index_characters,
        max_knowledge_files=config.max_knowledge_index_files,
        max_knowledge_characters=config.max_knowledge_index_characters,
    )
    manager = TaskManager(config, store, Gateway(config))

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        try:
            yield
        finally:
            manager.close()
            graph.close()

    app = FastAPI(title="Test Intelligence Platform", version="1.0.0", lifespan=lifespan)
    app.state.manager = manager
    app.state.store = store
    app.state.graph = graph
    app.state.knowledge = knowledge
    app.include_router(create_rag_router(store, knowledge, manager.gateway, config))

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        # This package is a single-user local service, not an unauthenticated LAN API.
        host = request.headers.get("host", "").split(":")[0]
        if host not in {"localhost", "127.0.0.1", "testserver"}:
            return JSONResponse({"detail": "Local-only service: use localhost"}, status_code=403)
        origin = request.headers.get("origin")
        if origin:
            from urllib.parse import urlsplit
            parsed = urlsplit(origin)
            if parsed.hostname not in {"localhost", "127.0.0.1"}:
                return JSONResponse({"detail": "Cross-site requests are not allowed"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/v1/health")
    def health():
        sqlite_connected = store.verify_connectivity()
        graph_connected = graph.verify_connectivity()
        prompt_issue = prompt_file_issue()
        return {
            "status": "healthy" if sqlite_connected and graph_connected and not prompt_issue else "degraded",
            "services": {
                "storage": True, "local_retrieval": True,
                "task_queue": True,
                "graph_service": graph_connected,
                "sqlite_connected": sqlite_connected,
                "analysis_persistence": sqlite_connected,
                "analysis_prompts_configured": prompt_issue is None,
                "gateway_configured": bool(config.gateway_url),
                "gateway_auth_configured": config.gateway_auth_configured,
                "rag_configured": bool(config.rag_base_url),
                "jira_configured": bool(config.jira_base_url and config.jira_token.get_secret_value()),
                "diagram_renderer_configured": mermaid_renderer_configured(),
                "diagram_renderer_issue": mermaid_renderer_issue(),
            },
            "graph_backend": config.graph_backend,
            "retrieval_backend": "SQLite FTS5",
            "embedding_provider": config.embedding_provider,
            "version": "1.0.0",
        }

    @app.get("/api/v1/configuration")
    def configuration():
        prompt_issue = prompt_file_issue()
        return {
            "gateway_configured": bool(config.gateway_url),
            "gateway_auth_configured": config.gateway_auth_configured,
            "analysis_prompts_configured": prompt_issue is None,
            "analysis_prompt_issue": prompt_issue,
            "rag_configured": bool(config.rag_base_url),
            "persistence_configured": store.verify_connectivity(),
            "persistence_backend": "SQLite",
            "graph_backend": config.graph_backend,
            "graph_configured": graph.verify_connectivity(),
            "retrieval_backend": "SQLite FTS5",
            "graph_limitations": LIMITATIONS,
            "embedding_provider": config.embedding_provider,
            "semantic_search": config.embedding_provider == "sentence_transformers",
            "diagram_renderer_configured": mermaid_renderer_configured(),
            "diagram_renderer_issue": mermaid_renderer_issue(),
            "jira_configured": bool(config.jira_base_url and config.jira_token.get_secret_value()),
            "server_directories_enabled": config.local_source_root is not None,
            "max_upload_bytes": config.max_upload_bytes,
            "max_extracted_bytes": config.max_extracted_bytes,
            "max_supporting_file_bytes": config.max_supporting_file_bytes,
            "max_archive_files": config.max_archive_files,
            "max_archive_entries": config.max_archive_entries,
            "max_files": config.max_files,
            "max_artifact_characters": config.max_artifact_characters,
            "max_repository_files": config.max_repository_files,
            "max_repository_bytes": config.max_repository_bytes,
            "max_repository_file_bytes": config.max_repository_file_bytes,
            "repository_clone_timeout_seconds": config.repository_clone_timeout_seconds,
            "max_analysis_files": config.max_analysis_files,
            "max_analysis_characters": config.max_analysis_characters,
            "analysis_batch_files": config.analysis_batch_files,
            "analysis_batch_characters": config.analysis_batch_characters,
            "analysis_batch_concurrency": config.analysis_batch_concurrency,
            "max_graph_index_files": config.max_graph_index_files,
            "max_graph_index_characters": config.max_graph_index_characters,
            "max_knowledge_index_files": config.max_knowledge_index_files,
            "max_knowledge_index_characters": config.max_knowledge_index_characters,
            "single_user_local_only": True,
        }

    @app.get("/api/v1/metrics", response_class=Response)
    def metrics():
        return Response(store.metrics(), media_type="text/plain")

    def submit(metadata, operation, cleanup=None):
        try:
            task = manager.submit(metadata, operation, cleanup)
        except ValueError as error:
            raise HTTPException(429, str(error)) from error
        return {"task_id": task["task_id"], "status": task["status"], "message": "Queued"}

    @app.post("/api/v1/analysis", status_code=202)
    async def analysis(request: Request):
        if not config.gateway_url:
            raise HTTPException(
                503, "Configure TIP_GATEWAY_URL with the complete completion endpoint before analysis"
            )
        prompt_issue = prompt_file_issue()
        if prompt_issue:
            raise HTTPException(503, prompt_issue)
        if not store.verify_connectivity():
            raise HTTPException(503, "SQLite analysis storage is unavailable; analysis was not sent to the model")
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                body_limit = config.max_upload_bytes + max(
                    1_000_000, config.max_files * 4096 + 250_000,
                )
                if int(content_length) > body_limit:
                    raise HTTPException(413, "Combined upload exceeds the size limit")
            except ValueError as error:
                raise HTTPException(400, "Invalid Content-Length") from error
        kinds = {
            "code_files": "CODE", "design_files": "DESIGN_DOCUMENT",
            "requirements_files": "RAW_REQUIREMENT", "story_files": "JIRA_USER_STORY",
        }
        uploads: list[Upload] = []
        submitted = False

        def cleanup_uploads():
            for upload in uploads:
                upload.close()

        try:
            async with request.form(
                max_files=config.max_files, max_fields=10, max_part_size=1_000_000
            ) as form:
                try:
                    options = AnalysisOptions.model_validate_json(str(form.get("options", "")))
                except ValidationError as error:
                    raise HTTPException(422, [
                        {"loc": list(e["loc"]), "msg": e["msg"]} for e in error.errors()
                    ]) from error
                total = 0
                for name, value in form.multi_items():
                    if name == "options":
                        continue
                    if name not in kinds or not isinstance(value, UploadFile):
                        raise HTTPException(422, f"Unknown upload field: {name}")
                    try:
                        filename = safe_path(value.filename or "")
                    except ValueError as error:
                        raise HTTPException(422, str(error)) from error
                    file_size = value.size
                    if file_size is None:
                        value.file.seek(0, os.SEEK_END)
                        file_size = value.file.tell()
                    total += file_size
                    if total > config.max_upload_bytes:
                        raise HTTPException(413, "Combined upload exceeds the configured size limit")
                    value.file.rollover()
                    value.file.seek(0)
                    stream = os.fdopen(os.dup(value.file.fileno()), "rb")
                    uploads.append(Upload(
                        filename, b"", kinds[name], stream=stream, size=file_size,
                    ))
            if (
                not uploads and not options.manual_stories and not options.jira_issue_keys
                and options.code_source == "uploads"
            ):
                raise HTTPException(422, "NO_ANALYZABLE_INPUT: provide code or supporting evidence")
            has_code_source = (
                options.code_source != "uploads"
                or any(upload.kind == "CODE" for upload in uploads)
            )
            if has_code_source:
                renderer_issue = mermaid_renderer_issue()
                if renderer_issue:
                    raise HTTPException(
                        503,
                        "Code-based analysis requires embedded UML images. "
                        f"{renderer_issue}",
                    )
            response = submit(
                {"kind": "analysis", "target_application": options.target_application,
                 "mode": options.analysis_mode},
                lambda task_id: manager.analyze(task_id, options, uploads),
                cleanup=cleanup_uploads,
            )
            submitted = True
            return response
        finally:
            if not submitted:
                cleanup_uploads()

    @app.get("/api/v1/tasks")
    def tasks(
        status: str | None = None, limit: int = Query(default=100, ge=1, le=1000),
        include_result: bool = True,
    ):
        if status and status not in {"pending", "running", "success", "failed", "cancelled"}:
            raise HTTPException(422, "Unknown task status")
        return store.list_tasks(status, limit, include_result=include_result)

    def require_task(task_id: str):
        task = store.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        return task

    @app.get("/api/v1/tasks/stats")
    def queue_stats():
        return {
            "counts": {
                status: store.list_tasks(
                    status, limit=1, include_result=False,
                )["total_count"]
                for status in ("pending", "running", "success", "failed", "cancelled")
            },
            "max_concurrent_tasks": config.max_concurrent_tasks,
        }

    @app.get("/api/v1/tasks/{task_id}")
    def task(task_id: str):
        return require_task(task_id)

    @app.post("/api/v1/tasks/{task_id}/cancel")
    def cancel(task_id: str):
        try:
            return manager.cancel(task_id)
        except KeyError as error:
            raise HTTPException(404, "Task not found") from error
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @app.get("/api/v1/tasks/{task_id}/analysis")
    def analysis_result(task_id: str):
        task = require_task(task_id)
        result = task.get("result", {}).get("analysis")
        if task["status"] != "success" or not result:
            raise HTTPException(409, "Analysis is not successfully completed")
        return JSONResponse(
            content=result,
            headers={
                "Content-Disposition": f'attachment; filename="TIP-analysis-{task_id}.json"',
            },
        )

    @app.get("/api/v1/tasks/{task_id}/document")
    def download(task_id: str):
        task = require_task(task_id)
        document = store.document(task_id)
        if task["status"] != "success" or document is None:
            raise HTTPException(409, "Word document is not ready")
        return StreamingResponse(
            io.BytesIO(document),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="TIP-technical-requirements-{task_id}.docx"'},
        )

    @app.get("/api/v1/tasks/{task_id}/business-document")
    def download_business_document(task_id: str):
        task = require_task(task_id)
        document = store.business_document(task_id)
        if task["status"] != "success" or document is None:
            raise HTTPException(409, "Business Word document is not ready")
        return StreamingResponse(
            io.BytesIO(document),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition":
                    f'attachment; filename="TIP-non-technical-FRS-{task_id}.docx"'
            },
        )

    @app.post("/api/v1/ingest/repo", status_code=202)
    def ingest(data: IngestRequest):
        if bool(data.repo_url) == bool(data.local_path):
            raise HTTPException(422, "Supply exactly one of repo_url or local_path")
        if data.mode not in {"full", "incremental"}:
            raise HTTPException(422, "Mode must be full or incremental")
        if data.since_commit and not re.fullmatch(r"[a-fA-F0-9]{7,40}", data.since_commit):
            raise HTTPException(422, "since_commit must be a Git commit SHA")
        if data.since_commit and data.mode != "incremental":
            raise HTTPException(422, "since_commit is valid only for incremental ingestion")
        source = data.repo_url or data.local_path
        repo_id = data.repo_id or repo_identifier(source)

        def operation(task_id):
            manager.progress(task_id, 10, "Reading authorized repository source")
            extractor = Extractor(config)
            with source_directory(
                config, repo_url=data.repo_url, local_path=data.local_path,
                branch=data.branch, selected_path=data.selected_path,
            ) as root:
                if data.since_commit:
                    # Incremental requests still rebuild the complete current index. This
                    # removes deleted files reliably while reporting the actual change count.
                    if data.repo_url:
                        fetched = subprocess.run(
                            ["git", "-C", str(root), "fetch", "--depth=1", "origin", data.since_commit],
                            capture_output=True, timeout=120, check=False,
                        )
                        if fetched.returncode:
                            raise ValueError("Cannot retrieve the requested since_commit")
                    changed = subprocess.run(
                        ["git", "-C", str(root), "diff", "--name-only", data.since_commit, "HEAD"],
                        capture_output=True, timeout=30, check=False,
                    )
                    if changed.returncode:
                        raise ValueError("Cannot compare the requested since_commit")
                    changed_count = len(changed.stdout.decode("utf-8").splitlines())
                else:
                    changed_count = None
                def selected_artifacts():
                    for artifact in extractor.iter_directory(root, data.selected_path or ""):
                        path = artifact.filePath
                        if (
                            (not data.include_globs or any(
                                fnmatch.fnmatch(path, pattern) for pattern in data.include_globs
                            ))
                            and not any(
                                fnmatch.fnmatch(path, pattern) for pattern in data.exclude_globs
                            )
                        ):
                            yield artifact

                index_result = store.index_batches(
                    repo_id, selected_artifacts(),
                    batch_size=config.repository_index_batch_files,
                    check=lambda: manager.check(task_id),
                    progress=lambda count: manager.progress(
                        task_id,
                        min(65, 15 + count * 50 // config.max_repository_files),
                        f"Indexed {count:,} repository files locally",
                    ),
                )
            if not index_result["files_indexed"]:
                raise ValueError("No readable code artifacts to index")
            manager.progress(task_id, 70, "Finalizing the local source index")
            diagnostic_warnings = []
            if extractor.excluded_count:
                diagnostic_warnings.append(
                    f"Excluded {extractor.excluded_count} sensitive, generated, or dependency paths."
                )
            if extractor.unsupported_count:
                diagnostic_warnings.append(
                    f"Omitted {extractor.unsupported_count} unsupported or unreadable files."
                )
            return {
                "repo_id": repo_id, "files_processed": extractor.file_count,
                "files_indexed": index_result["files_indexed"],
                "characters_indexed": index_result["characters_indexed"],
                "mode": data.mode,
                "changed_files_count": changed_count,
                "warnings": [
                    *extractor.warnings, *diagnostic_warnings, *index_result["warnings"],
                ],
                "graph_backend": index_result["graph_backend"],
                "excluded_files": extractor.excluded_files,
                "unsupported_files": extractor.unsupported_files,
                "index_strategy": "batched_current_scope_snapshot",
            }, None

        return {**submit({"kind": "ingest", "repo_url": data.repo_url, "mode": data.mode}, operation),
                "repo_id": repo_id}

    @app.post("/api/v1/documents/process", status_code=202)
    def process_document(data: ProcessDocumentRequest):
        if data.document_type not in {"CODE", "DESIGN_DOCUMENT", "JIRA_USER_STORY", "RAW_REQUIREMENT"}:
            raise HTTPException(422, "Unknown document_type")

        def operation(task_id):
            manager.progress(task_id, 20, "Normalizing supplied document text")
            extractor = Extractor(config)
            name = safe_path(data.filename)
            artifact = extractor.artifact(
                data.document_type, name, data.content,
                **({"filePath": name, "sha256": hashlib.sha256(data.content.encode()).hexdigest()}
                   if data.document_type == "CODE" else {}),
            )
            repo_id = repo_identifier(name)
            if artifact.sourceType == "CODE":
                store.index(repo_id, [artifact])
            if artifact.sourceType != "CODE":
                knowledge.add_document(repo_id, artifact.content, artifact.sourceName, artifact.model_dump(exclude={"content"}))
            return {"files_processed": 1, "repo_id": repo_id,
                    "artifacts": [artifact.model_dump()]}, None
        return submit({"kind": "document", "filename": data.filename}, operation)

    @app.post("/api/v1/documents/process-directory", status_code=202)
    def process_directory(data: ProcessDirectoryRequest):
        def operation(task_id):
            manager.progress(task_id, 20, "Reading allowed server directory")
            extractor = Extractor(config)
            with source_directory(config, local_path=data.directory_path) as root:
                def selected_artifacts():
                    for artifact in extractor.iter_directory(root, recursive=data.recursive):
                        if not data.file_patterns or any(
                            fnmatch.fnmatch(artifact.filePath, pattern)
                            for pattern in data.file_patterns
                        ):
                            yield artifact

                index_result = store.index_batches(
                    repo_identifier(data.directory_path), selected_artifacts(),
                    batch_size=config.repository_index_batch_files,
                    check=lambda: manager.check(task_id),
                    progress=lambda count: manager.progress(
                        task_id,
                        min(75, 20 + count * 55 // config.max_repository_files),
                        f"Indexed {count:,} directory files locally",
                    ),
                )
            if not index_result["files_indexed"]:
                raise ValueError("No readable code artifacts to index")
            diagnostic_warnings = []
            if extractor.excluded_count:
                diagnostic_warnings.append(
                    f"Excluded {extractor.excluded_count} sensitive, generated, or dependency paths."
                )
            if extractor.unsupported_count:
                diagnostic_warnings.append(
                    f"Omitted {extractor.unsupported_count} unsupported or unreadable files."
                )
            repo_id = repo_identifier(data.directory_path)
            return {"repo_id": repo_id, "files_processed": extractor.file_count,
                    "files_indexed": index_result["files_indexed"],
                    "characters_indexed": index_result["characters_indexed"],
                    "warnings": [
                        *extractor.warnings, *diagnostic_warnings, *index_result["warnings"],
                    ],
                    "unsupported_files": extractor.unsupported_files}, None
        return submit({"kind": "directory", "local_path": data.directory_path}, operation)

    @app.get("/api/v1/graph/related")
    def related(query: str, repoId: str, limit: int = Query(default=10, ge=1, le=100)):
        artifacts = store.retrieve(repoId, query, limit)
        return {
            "query": query, "repo_id": repoId,
            "nodes": [
                {"type": "FILE", "ref": a.filePath, "path": a.filePath,
                 "lang": Path(a.filePath).suffix.lstrip("."), "score": 1 / (i + 1),
                 "summary": a.content[:1000]}
                for i, a in enumerate(artifacts)
            ],
        }

    @app.get("/api/v1/context/pack")
    def context_pack(repoId: str, stage: str = "requirements",
                     budget: int = Query(default=12000, ge=100, le=100_000),
                     keywords: str = "", focus: str = "",
                     mode: str = Query(default="hybrid", pattern="^(keyword|vector|hybrid)$")):
        # Budget is a character budget, not a claimed tokenizer-specific token count.
        try:
            artifacts = store.rag_retrieve(repoId, focus or keywords, mode, config.max_files)
        except (ValueError, RuntimeError, ImportError, sqlite3.Error) as error:
            logger.exception("RAG context retrieval failed")
            raise HTTPException(503, "Source context retrieval failed; check backend configuration and logs") from error
        items = []
        used = 0
        for artifact in artifacts:
            remaining = budget - used
            if remaining <= 0:
                break
            summary = artifact.content[:remaining]
            used += len(summary)
            items.append({
                "kind": "CODE", "title": artifact.sourceName, "summary": summary,
                "ref": artifact.filePath,
                "extra": {"path": artifact.filePath, "budget_unit": "characters"},
            })
        return {
            "items": items, "budget_used": used, "budget_limit": budget,
            "stage": stage, "repo_id": repoId, "category_counts": {"CODE": len(items)},
        }

    @app.get("/api/v1/graph/impact")
    def impact(repoId: str, file: str,
               depth: int = Query(default=2, ge=1, le=5),
               limit: int = Query(default=20, ge=1, le=100)):
        if not config.rag_base_url:
            try:
                return store.impact(repoId, file, depth, limit)
            except KeyError as error:
                raise HTTPException(404, "File is not indexed in this repository") from error
            except (RuntimeError, sqlite3.Error) as error:
                logger.exception("Code graph impact query failed")
                raise HTTPException(503, "Code graph is unavailable; check backend logs") from error
        try:
            with httpx.Client(timeout=30, follow_redirects=False) as client:
                response = client.get(
                    f"{config.rag_base_url}/graph/impact",
                    params={"repoId": repoId, "file": file, "depth": depth, "limit": limit},
                )
            if response.status_code != 200:
                raise HTTPException(502, f"Graph service returned HTTP {response.status_code}")
            return response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as error:
            raise HTTPException(502, "Graph service returned an invalid response or is unavailable") from error

    return app

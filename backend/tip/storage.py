import json
import hashlib
import re
import sqlite3
import threading
import uuid
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator

from .models import Artifact
from codebase_rag.services.graph.code_graph import CodeGraph
from codebase_rag.services.knowledge.local_store import LocalKnowledge

logger = logging.getLogger(__name__)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path, graph: CodeGraph | None = None,
                 knowledge: LocalKnowledge | None = None, *,
                 max_graph_files: int = 5_000,
                 max_graph_characters: int = 25_000_000,
                 max_knowledge_files: int = 500,
                 max_knowledge_characters: int = 5_000_000):
        self.path = path
        self.graph = graph
        self.knowledge = knowledge
        self.max_graph_files = max_graph_files
        self.max_graph_characters = max_graph_characters
        self.max_knowledge_files = max_knowledge_files
        self.max_knowledge_characters = max_knowledge_characters
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, body TEXT NOT NULL, document BLOB,
                    business_document BLOB
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY, repo_id TEXT NOT NULL,
                    ref TEXT NOT NULL, artifact TEXT NOT NULL,
                    UNIQUE(repo_id, ref)
                );
                CREATE TABLE IF NOT EXISTS analysis_records (
                    task_id TEXT PRIMARY KEY REFERENCES tasks(id),
                    target_application TEXT NOT NULL,
                    document_title TEXT NOT NULL,
                    analysis_json TEXT NOT NULL,
                    saved_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS requirements (
                    task_id TEXT NOT NULL REFERENCES analysis_records(task_id),
                    requirement_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    acceptance_criterion TEXT NOT NULL,
                    priority TEXT,
                    origin_json TEXT NOT NULL,
                    implementation_status TEXT NOT NULL,
                    evidence_status TEXT NOT NULL,
                    PRIMARY KEY (task_id, requirement_id)
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    task_id TEXT NOT NULL REFERENCES analysis_records(task_id),
                    evidence_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    file_path TEXT,
                    external_id TEXT,
                    worksheet TEXT,
                    row_number INTEGER,
                    description TEXT NOT NULL,
                    PRIMARY KEY (task_id, evidence_id)
                );
                CREATE TABLE IF NOT EXISTS requirement_evidence (
                    task_id TEXT NOT NULL,
                    requirement_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    evidence_description TEXT NOT NULL,
                    PRIMARY KEY (task_id, requirement_id, evidence_id),
                    FOREIGN KEY (task_id, requirement_id)
                        REFERENCES requirements(task_id, requirement_id),
                    FOREIGN KEY (task_id, evidence_id)
                        REFERENCES evidence(task_id, evidence_id)
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS source_fts USING fts5(
                    content, path, repo_id UNINDEXED, artifact_id UNINDEXED
                );
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(tasks)")}
            if "business_document" not in columns:
                db.execute("ALTER TABLE tasks ADD COLUMN business_document BLOB")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def recover(self):
        for task in self.list_tasks(limit=100_000)["tasks"]:
            if task["status"] in {"pending", "running"}:
                self.update(task["task_id"], status="failed", progress=100,
                            message="Backend restarted before completion",
                            error="BACKEND_RESTARTED: resubmit this task", completed_at=now())

    def create(self, metadata: dict) -> dict:
        task = {
            "task_id": str(uuid.uuid4()), "status": "pending", "progress": 0,
            "message": "Queued", "created_at": now(), "metadata": metadata,
        }
        with self.connect() as db:
            db.execute("INSERT INTO tasks(id, body) VALUES (?,?)",
                       (task["task_id"], json.dumps(task)))
        return task

    def get(self, task_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT body FROM tasks WHERE id=?", (task_id,)).fetchone()
        return json.loads(row["body"]) if row else None

    def update(self, task_id: str, **fields):
        with self.lock:
            task = self.get(task_id)
            if task is None:
                raise KeyError(task_id)
            task.update(fields)
            with self.connect() as db:
                db.execute("UPDATE tasks SET body=? WHERE id=?", (json.dumps(task), task_id))
            return task

    def complete(
        self, task_id: str, result: dict, document: bytes | None,
        business_document: bytes | None = None,
    ):
        with self.lock:
            task = self.get(task_id)
            if task is None:
                raise KeyError(task_id)
            task.update(status="success", progress=100, message="Completed",
                        completed_at=now(), result=result)
            with self.connect() as db:
                analysis = result.get("analysis")
                if isinstance(analysis, dict):
                    self._persist_analysis(db, task_id, analysis)
                db.execute(
                    "UPDATE tasks SET body=?, document=?, business_document=? WHERE id=?",
                    (json.dumps(task), document, business_document, task_id),
                )

    @staticmethod
    def _persist_analysis(db, task_id: str, analysis: dict):
        info = analysis.get("documentInformation") or {}
        db.execute(
            """INSERT INTO analysis_records
               (task_id, target_application, document_title, analysis_json, saved_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(task_id) DO UPDATE SET
                 target_application=excluded.target_application,
                 document_title=excluded.document_title,
                 analysis_json=excluded.analysis_json,
                 saved_at=excluded.saved_at""",
            (
                task_id,
                str(info.get("targetApplication", "")),
                str(analysis.get("documentTitle", "")),
                json.dumps(analysis, ensure_ascii=False),
                now(),
            ),
        )
        db.execute("DELETE FROM requirement_evidence WHERE task_id=?", (task_id,))
        db.execute("DELETE FROM evidence WHERE task_id=?", (task_id,))
        db.execute("DELETE FROM requirements WHERE task_id=?", (task_id,))
        for category, items in (
            ("FUNCTIONAL", analysis.get("highLevelRequirements", [])),
            ("NON_FUNCTIONAL", analysis.get("nonFunctionalRequirements", [])),
        ):
            for requirement in items:
                requirement_id = str(requirement["id"])
                db.execute(
                    """INSERT INTO requirements
                       (task_id, requirement_id, category, statement,
                        acceptance_criterion, priority, origin_json,
                        implementation_status, evidence_status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        task_id, requirement_id, category,
                        str(requirement.get("requirement", "")),
                        str(requirement.get("acceptanceCriterion", "")),
                        None if requirement.get("priority") is None else str(requirement["priority"]),
                        json.dumps(requirement.get("requirementOrigin", [])),
                        str(requirement.get("implementationEvidenceStatus", "")),
                        str(requirement.get("evidenceStatus", "")),
                    ),
                )
                for evidence in requirement.get("sourceEvidence", []):
                    identity = {
                        key: evidence.get(key) for key in (
                            "sourceType", "sourceName", "filePath", "externalId",
                            "worksheet", "row",
                        )
                    }
                    evidence_id = hashlib.sha256(
                        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
                    ).hexdigest()
                    db.execute(
                        """INSERT OR IGNORE INTO evidence
                           (task_id, evidence_id, source_type, source_name, file_path,
                            external_id, worksheet, row_number, description)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            task_id, evidence_id, str(evidence.get("sourceType", "")),
                            str(evidence.get("sourceName", "")), evidence.get("filePath"),
                            evidence.get("externalId"), evidence.get("worksheet"),
                            evidence.get("row"), str(evidence.get("evidenceDescription", "")),
                        ),
                    )
                    db.execute(
                        """INSERT OR IGNORE INTO requirement_evidence
                           (task_id, requirement_id, evidence_id, evidence_description)
                           VALUES (?, ?, ?, ?)""",
                        (
                            task_id, requirement_id, evidence_id,
                            str(evidence.get("evidenceDescription", "")),
                        ),
                    )

    def verify_connectivity(self) -> bool:
        try:
            with self.connect() as db:
                db.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def document(self, task_id: str) -> bytes | None:
        with self.connect() as db:
            row = db.execute("SELECT document FROM tasks WHERE id=?", (task_id,)).fetchone()
        return row["document"] if row else None

    def business_document(self, task_id: str) -> bytes | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT business_document FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
        return row["business_document"] if row else None

    def list_tasks(self, status: str | None = None, limit: int = 100) -> dict:
        with self.connect() as db:
            clauses = "WHERE json_extract(body, '$.status')=?" if status else ""
            params = (status,) if status else ()
            total = db.execute(f"SELECT count(*) FROM tasks {clauses}", params).fetchone()[0]
            rows = db.execute(
                f"SELECT body FROM tasks {clauses} "
                "ORDER BY json_extract(body, '$.created_at') DESC LIMIT ?", (*params, limit),
            ).fetchall()
        return {"tasks": [json.loads(row["body"]) for row in rows], "total_count": total}

    def index(
        self, repo_id: str, artifacts: list[Artifact], replace: bool = True, *,
        include_knowledge: bool = True, include_graph: bool = True,
    ):
        if not artifacts:
            raise ValueError("No readable code artifacts to index")
        warnings = []
        graph_result = {"backend": None, "warnings": []}
        with self.lock, self.connect() as db:
            if replace:
                db.execute("DELETE FROM source_fts WHERE repo_id=?", (repo_id,))
                db.execute("DELETE FROM artifacts WHERE repo_id=?", (repo_id,))
            for artifact in artifacts:
                ref = artifact.filePath or artifact.sourceName
                old = db.execute(
                    "SELECT id FROM artifacts WHERE repo_id=? AND ref=?", (repo_id, ref)
                ).fetchone()
                if old:
                    db.execute("DELETE FROM source_fts WHERE artifact_id=?", (old["id"],))
                    db.execute("DELETE FROM artifacts WHERE id=?", (old["id"],))
                row = db.execute(
                    "INSERT INTO artifacts(repo_id, ref, artifact) VALUES (?,?,?)",
                    (repo_id, ref, artifact.model_dump_json()),
                )
                db.execute(
                    "INSERT INTO source_fts(content,path,repo_id,artifact_id) VALUES (?,?,?,?)",
                    (artifact.content, ref, repo_id, row.lastrowid),
                )
            file_count, character_count = db.execute(
                "SELECT count(*), coalesce(sum(length(json_extract(artifact, '$.content'))), 0) "
                "FROM artifacts WHERE repo_id=?", (repo_id,),
            ).fetchone()
            if include_knowledge and self.knowledge:
                if (
                    file_count <= self.max_knowledge_files
                    and character_count <= self.max_knowledge_characters
                ):
                    documents = []
                    for row in db.execute(
                        "SELECT ref, artifact FROM artifacts WHERE repo_id=?", (repo_id,),
                    ):
                        artifact = json.loads(row["artifact"])
                        content = artifact.pop("content")
                        documents.append({
                            "ref": row["ref"], "content": content, "metadata": artifact,
                        })
                    self.knowledge.index(db, repo_id, documents)
                else:
                    db.execute("DELETE FROM rag_fts WHERE scope=?", (repo_id,))
                    db.execute("DELETE FROM rag_chunks WHERE scope=?", (repo_id,))
                    db.execute("DELETE FROM rag_snapshots WHERE scope=?", (repo_id,))
                    warnings.append(
                        "Semantic chunk/vector indexing was skipped above the configured limit; "
                        "SQLite full-text retrieval remains available."
                    )
            if include_graph and self.graph:
                # The graph is derived. Impact reads reconcile it with the authoritative
                # SQLite snapshot, including after an interrupted cross-database commit.
                graph_sources = (
                    self._sources(db, repo_id)
                    if (
                        file_count <= self.max_graph_files
                        and character_count <= self.max_graph_characters
                    )
                    else {}
                )
                if not graph_sources and file_count:
                    warnings.append(
                        "Code graph indexing was skipped above the configured limit; "
                        "SQLite full-text retrieval remains available."
                    )
                try:
                    graph_result = self.graph.index(repo_id, graph_sources)
                except (RuntimeError, sqlite3.Error) as error:
                    logger.exception("Code graph indexing failed")
                    raise ValueError(
                        "Code graph indexing failed; no source snapshot was committed. "
                        "Check the graph data directory and backend configuration."
                    ) from error
        return {
            "backend": graph_result.get("backend"),
            "warnings": list(dict.fromkeys([*warnings, *graph_result.get("warnings", [])])),
        }

    def index_batches(
        self, repo_id: str, artifacts: Iterable[Artifact], *,
        batch_size: int = 100, check: Callable[[], None] | None = None,
        progress: Callable[[int], None] | None = None,
    ) -> dict:
        if batch_size < 1:
            raise ValueError("Index batch size must be positive")
        staging_id = f"{repo_id}:staging:{uuid.uuid4().hex}"
        batch: list[Artifact] = []
        indexed_files = 0
        indexed_characters = 0
        warnings = []

        def flush():
            nonlocal batch, indexed_files, indexed_characters
            if not batch:
                return
            self.index(
                staging_id, batch, replace=indexed_files == 0,
                include_knowledge=False, include_graph=False,
            )
            indexed_files += len(batch)
            indexed_characters += sum(len(item.content) for item in batch)
            batch = []
            if progress:
                progress(indexed_files)

        try:
            for artifact in artifacts:
                if check:
                    check()
                batch.append(artifact)
                if len(batch) >= batch_size:
                    flush()
            flush()
            if not indexed_files:
                return {
                    "files_indexed": 0, "characters_indexed": 0,
                    "graph_backend": None, "warnings": [],
                }

            graph_sources = None
            with self.lock, self.connect() as db:
                if check:
                    check()
                db.execute("DELETE FROM source_fts WHERE repo_id=?", (repo_id,))
                db.execute("DELETE FROM artifacts WHERE repo_id=?", (repo_id,))
                db.execute(
                    "UPDATE artifacts SET repo_id=? WHERE repo_id=?", (repo_id, staging_id),
                )
                db.execute(
                    "UPDATE source_fts SET repo_id=? WHERE repo_id=?", (repo_id, staging_id),
                )
                if self.knowledge:
                    db.execute("DELETE FROM rag_fts WHERE scope=?", (repo_id,))
                    db.execute("DELETE FROM rag_chunks WHERE scope=?", (repo_id,))
                    db.execute("DELETE FROM rag_snapshots WHERE scope=?", (repo_id,))
                    if (
                        indexed_files <= self.max_knowledge_files
                        and indexed_characters <= self.max_knowledge_characters
                    ):
                        documents = []
                        for row in db.execute(
                            "SELECT ref, artifact FROM artifacts WHERE repo_id=?", (repo_id,),
                        ):
                            artifact = json.loads(row["artifact"])
                            content = artifact.pop("content")
                            documents.append({
                                "ref": row["ref"], "content": content, "metadata": artifact,
                            })
                        self.knowledge.index(db, repo_id, documents)
                    else:
                        warnings.append(
                            "Semantic chunk/vector indexing was skipped for this large repository; "
                            "SQLite full-text retrieval remains available."
                        )
                if self.graph:
                    if (
                        indexed_files <= self.max_graph_files
                        and indexed_characters <= self.max_graph_characters
                    ):
                        graph_sources = self._sources(db, repo_id)
                    else:
                        graph_sources = {}
                        warnings.append(
                            "Code graph indexing was skipped because the repository exceeds the "
                            f"{self.max_graph_files}-file or {self.max_graph_characters:,}-character "
                            "graph limit; SQLite full-text retrieval remains available."
                        )

            graph_result = {"backend": None, "warnings": []}
            if self.graph:
                try:
                    graph_result = self.graph.index(repo_id, graph_sources or {})
                    warnings.extend(graph_result.get("warnings", []))
                except (RuntimeError, sqlite3.Error):
                    logger.exception("Code graph indexing failed for repository snapshot")
                    warnings.append(
                        "Code graph indexing failed; indexed source remains available for retrieval."
                    )
            return {
                "files_indexed": indexed_files,
                "characters_indexed": indexed_characters,
                "graph_backend": graph_result.get("backend"),
                "warnings": list(dict.fromkeys(warnings)),
            }
        except Exception:
            with self.lock, self.connect() as db:
                db.execute("DELETE FROM source_fts WHERE repo_id=?", (staging_id,))
                db.execute("DELETE FROM artifacts WHERE repo_id=?", (staging_id,))
            raise

    def index_stats(self, repo_id: str, path_prefix: str | None = None) -> tuple[int, int]:
        where = "repo_id=?"
        params: tuple = (repo_id,)
        if path_prefix:
            where += " AND substr(ref, 1, ?)=?"
            params = (repo_id, len(path_prefix), path_prefix)
        with self.connect() as db:
            row = db.execute(
                "SELECT count(*), coalesce(sum(length(json_extract(artifact, '$.content'))), 0) "
                f"FROM artifacts WHERE {where}", params,
            ).fetchone()
        return int(row[0]), int(row[1])

    def iter_artifacts(
        self, repo_id: str, path_prefix: str | None = None, *,
        batch_size: int = 100,
    ) -> Iterator[Artifact]:
        if batch_size < 1:
            raise ValueError("Artifact iteration batch size must be positive")
        last_ref = None
        while True:
            where = "repo_id=?"
            params: tuple = (repo_id,)
            if path_prefix:
                where += " AND substr(ref, 1, ?)=?"
                params = (repo_id, len(path_prefix), path_prefix)
            if last_ref is not None:
                where += " AND ref>?"
                params = (*params, last_ref)
            with self.connect() as db:
                rows = db.execute(
                    f"SELECT ref, artifact FROM artifacts WHERE {where} ORDER BY ref LIMIT ?",
                    (*params, batch_size),
                ).fetchall()
            if not rows:
                return
            last_ref = rows[-1]["ref"]
            for row in rows:
                yield Artifact.model_validate_json(row["artifact"])

    @staticmethod
    def _sources(db, repo_id: str) -> dict[str, str]:
        rows = db.execute(
            "SELECT ref, artifact FROM artifacts WHERE repo_id=?", (repo_id,),
        ).fetchall()
        return {row["ref"]: json.loads(row["artifact"])["content"] for row in rows}

    def impact(self, repo_id: str, file: str, depth: int, limit: int) -> dict:
        if self.graph is None:
            raise RuntimeError("Code graph is not configured")
        file_count, character_count = self.index_stats(repo_id)
        if (
            file_count > self.max_graph_files
            or character_count > self.max_graph_characters
        ):
            raise RuntimeError(
                "Code graph queries are disabled above the configured file or character limit"
            )
        with self.lock, self.connect() as db:
            return self.graph.impact(repo_id, file, self._sources(db, repo_id), depth, limit)

    def symbols(self, repo_id: str) -> dict:
        if self.graph is None:
            raise RuntimeError("Code graph is not configured")
        file_count, character_count = self.index_stats(repo_id)
        if (
            file_count > self.max_graph_files
            or character_count > self.max_graph_characters
        ):
            raise RuntimeError(
                "Code graph queries are disabled above the configured file or character limit"
            )
        with self.lock, self.connect() as db:
            return self.graph.symbols(repo_id, self._sources(db, repo_id))

    def rag_retrieve(self, repo_id: str, query: str = "", mode: str = "hybrid",
                     limit: int = 500, path_prefix: str | None = None) -> list[Artifact]:
        if path_prefix:
            return self.retrieve(repo_id, query, limit, path_prefix)
        if self.knowledge is None or not query:
            return self.retrieve(repo_id, query, limit)
        index_files, index_characters = self.index_stats(repo_id)
        fallback_lexical = False
        with self.lock, self.connect() as db:
            snapshot = db.execute(
                "SELECT signature FROM rag_snapshots WHERE scope=?", (repo_id,),
            ).fetchone()
            too_large_for_knowledge = (
                index_files > self.max_knowledge_files
                or index_characters > self.max_knowledge_characters
            )
            signature_changed = (
                snapshot is not None
                and snapshot["signature"] != self.knowledge.embeddings.signature
            )
            if too_large_for_knowledge:
                if signature_changed:
                    raise ValueError(
                        "Embedding configuration changed; this large repository requires "
                        "re-indexing before semantic retrieval"
                    )
                fallback_lexical = True
            elif snapshot is None or signature_changed:
                rows = db.execute(
                    "SELECT ref, artifact FROM artifacts WHERE repo_id=?", (repo_id,),
                ).fetchall()
                documents = []
                for row in rows:
                    artifact = json.loads(row["artifact"])
                    documents.append({
                        "ref": row["ref"], "content": artifact.pop("content"),
                        "metadata": artifact,
                    })
                self.knowledge.index(db, repo_id, documents)
        if fallback_lexical:
            return self.retrieve(repo_id, query, limit)
        result = self.knowledge.search(repo_id, query, mode, min(limit, 100))
        paths = list(dict.fromkeys(node["ref"] for node in result["nodes"]))
        by_path = {
            artifact.filePath: artifact
            for artifact in self.retrieve_refs(repo_id, paths)
        }
        return [by_path[path] for path in paths[:limit] if path in by_path]

    def retrieve_refs(self, repo_id: str, refs: list[str]) -> list[Artifact]:
        if not refs:
            return []
        placeholders = ",".join("?" for _ in refs)
        with self.connect() as db:
            rows = db.execute(
                f"SELECT artifact FROM artifacts WHERE repo_id=? AND ref IN ({placeholders})",
                (repo_id, *refs),
            ).fetchall()
        artifacts = [Artifact.model_validate_json(row["artifact"]) for row in rows]
        by_path = {artifact.filePath: artifact for artifact in artifacts}
        return [by_path[path] for path in refs if path in by_path]

    def retrieve(
        self, repo_id: str, query: str = "", limit: int = 500,
        path_prefix: str | None = None,
    ) -> list[Artifact]:
        tokens = re.findall(r"\w+", query, re.UNICODE)[:40]
        prefix_clause = " AND substr(a.ref, 1, ?)=?" if path_prefix else ""
        prefix_params = (len(path_prefix), path_prefix) if path_prefix else ()
        with self.connect() as db:
            if tokens:
                match = " OR ".join(f'"{token}"' for token in tokens)
                rows = db.execute("""
                    SELECT a.artifact FROM source_fts f
                    JOIN artifacts a ON a.id=f.artifact_id
                    WHERE source_fts MATCH ? AND f.repo_id=?
                """ + prefix_clause + " ORDER BY bm25(source_fts) LIMIT ?",
                    (match, repo_id, *prefix_params, limit),
                ).fetchall()
            else:
                if path_prefix:
                    rows = db.execute(
                        "SELECT artifact FROM artifacts WHERE repo_id=? "
                        "AND substr(ref, 1, ?)=? ORDER BY ref LIMIT ?",
                        (repo_id, len(path_prefix), path_prefix, limit),
                    ).fetchall()
                else:
                    rows = db.execute(
                        "SELECT artifact FROM artifacts WHERE repo_id=? ORDER BY ref LIMIT ?",
                        (repo_id, limit),
                    ).fetchall()
        return [Artifact.model_validate_json(row["artifact"]) for row in rows]

    def metrics(self) -> str:
        with self.connect() as db:
            tasks = db.execute(
                "SELECT json_extract(body,'$.status') status,count(*) n FROM tasks GROUP BY status"
            ).fetchall()
            files = db.execute("SELECT count(*) FROM artifacts").fetchone()[0]
            analyses = db.execute("SELECT count(*) FROM analysis_records").fetchone()[0]
            requirements = db.execute("SELECT count(*) FROM requirements").fetchone()[0]
        lines = ["# TYPE tip_tasks gauge"]
        lines.extend(f'tip_tasks{{status="{row["status"]}"}} {row["n"]}' for row in tasks)
        lines.extend([
            "# TYPE tip_indexed_files gauge", f"tip_indexed_files {files}",
            "# TYPE tip_saved_analyses gauge", f"tip_saved_analyses {analyses}",
            "# TYPE tip_saved_requirements gauge", f"tip_saved_requirements {requirements}",
        ])
        return "\n".join(lines) + "\n"
import json
import hashlib
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .models import Artifact


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, body TEXT NOT NULL, document BLOB
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

    def complete(self, task_id: str, result: dict, document: bytes | None):
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
                db.execute("UPDATE tasks SET body=?, document=? WHERE id=?",
                           (json.dumps(task), document, task_id))

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

    def index(self, repo_id: str, artifacts: list[Artifact], replace: bool = True):
        if not artifacts:
            raise ValueError("No readable code artifacts to index")
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

    def retrieve(self, repo_id: str, query: str = "", limit: int = 500) -> list[Artifact]:
        tokens = re.findall(r"\w+", query, re.UNICODE)[:40]
        with self.connect() as db:
            if tokens:
                match = " OR ".join(f'"{token}"' for token in tokens)
                rows = db.execute("""
                    SELECT a.artifact FROM source_fts f
                    JOIN artifacts a ON a.id=f.artifact_id
                    WHERE source_fts MATCH ? AND f.repo_id=?
                    ORDER BY bm25(source_fts) LIMIT ?
                """, (match, repo_id, limit)).fetchall()
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
"""Persistent chunk/vector retrieval, project memory and conversation storage."""

import hashlib
import json
import math
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryType = Literal["decision", "preference", "experience", "convention", "plan", "note"]


class EmbeddingError(RuntimeError):
    """A selected embedding provider could not be initialized."""


class Memory(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    project_id: str = Field(min_length=1, max_length=200)
    memory_type: MemoryType
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=50000)
    reason: str | None = Field(default=None, max_length=10000)
    tags: list[str] = Field(default_factory=list, max_length=100)
    importance: float = Field(default=0.5, ge=0, le=1)
    related_refs: list[str] = Field(default_factory=list, max_length=100)
    metadata: dict = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    content: str | None = Field(default=None, min_length=1, max_length=50000)
    reason: str | None = Field(default=None, max_length=10000)
    tags: list[str] | None = Field(default=None, max_length=100)
    importance: float | None = Field(default=None, ge=0, le=1)
    related_refs: list[str] | None = Field(default=None, max_length=100)
    metadata: dict | None = None


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class Embeddings:
    def __init__(self, provider: str = "hash", model: str = "", dimension: int = 384):
        self.provider = provider
        self.model = model
        self.dimension = dimension
        self.encoder = None
        self.lock = threading.RLock()
        self.signature = f"{provider}:{model if provider != 'hash' else 'tokens-v2'}:{dimension}"

    def encode(self, texts: list[str]) -> list[list[float]]:
        with self.lock:
            if self.provider == "sentence_transformers":
                if self.encoder is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                    except ModuleNotFoundError as error:
                        raise EmbeddingError(
                            "Semantic embeddings are unavailable; install the backend[semantic] extra"
                        ) from error
                    try:
                        self.encoder = SentenceTransformer(self.model, device="cpu", trust_remote_code=False)
                    except OSError as error:
                        raise EmbeddingError(
                            "The configured semantic embedding model could not be loaded; "
                            "check model path/download connectivity"
                        ) from error
                vectors = self.encoder.encode(texts, normalize_embeddings=True).tolist()
                if any(len(vector) != self.dimension for vector in vectors):
                    raise ValueError("Embedding model dimension differs from TIP_EMBEDDING_DIMENSION")
                return vectors
            if self.provider != "hash":
                raise ValueError(f"Unknown embedding provider: {self.provider}")
            result = []
            for text in texts:
                vector = [0.0] * self.dimension
                identifiers = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
                tokens = re.findall(r"[a-z]+|\d+", identifiers.lower())
                for token in tokens:
                    digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                    position = int.from_bytes(digest[:4], "little") % self.dimension
                    vector[position] += 1 if digest[4] & 1 else -1
                norm = math.sqrt(sum(value * value for value in vector))
                result.append([value / norm if norm else 0.0 for value in vector])
            return result


class LocalKnowledge:
    def __init__(self, path: Path, embeddings: Embeddings, chunk_size: int = 2000):
        self.path = path
        self.embeddings = embeddings
        self.chunk_size = chunk_size
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS rag_snapshots (
                    scope TEXT PRIMARY KEY, digest TEXT NOT NULL, signature TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    id TEXT PRIMARY KEY, scope TEXT NOT NULL, ref TEXT NOT NULL,
                    content TEXT NOT NULL, metadata TEXT NOT NULL, vector TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS rag_scope ON rag_chunks(scope, ref);
                CREATE VIRTUAL TABLE IF NOT EXISTS rag_fts USING fts5(
                    content, ref, chunk_id UNINDEXED, scope UNINDEXED
                );
                CREATE TABLE IF NOT EXISTS project_memories (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, body TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS memory_project ON project_memories(project_id);
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT NOT NULL, project_id TEXT NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(id, project_id)
                );
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT NOT NULL, scope TEXT NOT NULL, labels TEXT NOT NULL,
                    properties TEXT NOT NULL, PRIMARY KEY(id, scope)
                );
                CREATE TABLE IF NOT EXISTS relationships (
                    id TEXT NOT NULL, scope TEXT NOT NULL, source TEXT NOT NULL,
                    target TEXT NOT NULL, type TEXT NOT NULL, properties TEXT NOT NULL,
                    PRIMARY KEY(id, scope)
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

    def index(self, db, scope: str, documents: list[dict], replace: bool = True):
        digest = hashlib.sha256(json.dumps(documents, sort_keys=True).encode()).hexdigest()
        old = db.execute("SELECT digest, signature FROM rag_snapshots WHERE scope=?", (scope,)).fetchone()
        if not replace and old and old["signature"] != self.embeddings.signature:
            raise ValueError("Embedding configuration changed; re-index the complete scope before adding documents")
        if replace and old and tuple(old) == (digest, self.embeddings.signature):
            return
        chunks = []
        for document in documents:
            content = document["content"]
            ref = document["ref"]
            step = self.chunk_size - min(200, self.chunk_size // 5)
            for start in range(0, len(content), step):
                part = content[start:start + self.chunk_size]
                metadata = {
                    **document.get("metadata", {}),
                    "lineStart": content.count("\n", 0, start) + 1,
                    "lineEnd": content.count("\n", 0, start) + max(len(part.splitlines()), 1),
                }
                identity = hashlib.sha256(json.dumps([scope, ref, start]).encode()).hexdigest()
                chunks.append((identity, scope, ref, part, json.dumps(metadata)))
                if start + self.chunk_size >= len(content):
                    break
        vectors = self.embeddings.encode([chunk[3] for chunk in chunks]) if chunks else []
        if replace:
            db.execute("DELETE FROM rag_fts WHERE scope=?", (scope,))
            db.execute("DELETE FROM rag_chunks WHERE scope=?", (scope,))
        else:
            for ref in {document["ref"] for document in documents}:
                db.execute("DELETE FROM rag_fts WHERE scope=? AND ref=?", (scope, ref))
                db.execute("DELETE FROM rag_chunks WHERE scope=? AND ref=?", (scope, ref))
        db.executemany(
            "INSERT INTO rag_chunks VALUES (?, ?, ?, ?, ?, ?)",
            [(*chunk, json.dumps(vector)) for chunk, vector in zip(chunks, vectors, strict=True)],
        )
        db.executemany(
            "INSERT INTO rag_fts(content,ref,chunk_id,scope) VALUES (?, ?, ?, ?)",
            [(chunk[3], chunk[2], chunk[0], scope) for chunk in chunks],
        )
        # A partial upsert invalidates the digest; a full snapshot will reconcile it.
        db.execute(
            "INSERT OR REPLACE INTO rag_snapshots VALUES (?, ?, ?)",
            (scope, digest if replace else "", self.embeddings.signature),
        )

    def add_document(self, scope: str, content: str, title: str, metadata: dict | None = None):
        identity = str(uuid.uuid4())
        with self.connect() as db:
            self.index(db, scope, [{"ref": identity, "content": content,
                                   "metadata": {"title": title, **(metadata or {})}}], replace=False)
        return {"success": True, "document_id": identity, "scope": scope}

    def search(self, scope: str, query: str, mode: str = "hybrid", limit: int = 10) -> dict:
        if mode not in {"keyword", "vector", "hybrid"}:
            raise ValueError("Search mode must be keyword, vector or hybrid")
        if not query.strip() or not 1 <= limit <= 100:
            raise ValueError("Search needs a non-empty query and a limit of 1-100")
        with self.connect() as db:
            snapshot = db.execute(
                "SELECT signature FROM rag_snapshots WHERE scope=?", (scope,),
            ).fetchone()
            if snapshot and snapshot["signature"] != self.embeddings.signature:
                raise ValueError("Embedding configuration changed; re-index this scope before searching")
            rows = db.execute("SELECT * FROM rag_chunks WHERE scope=?", (scope,)).fetchall()
            tokens = re.findall(r"\w+", query)[:40]
            lexical = []
            if mode != "vector" and tokens:
                match = " OR ".join(f'"{token}"' for token in tokens)
                lexical = db.execute(
                    "SELECT chunk_id FROM rag_fts WHERE rag_fts MATCH ? AND scope=? "
                    "ORDER BY bm25(rag_fts) LIMIT 100", (match, scope),
                ).fetchall()
        scores: dict[str, float] = {}
        if mode != "vector":
            scores.update({row["chunk_id"]: 1 / (60 + rank) for rank, row in enumerate(lexical, 1)})
        if mode != "keyword" and rows:
            vector = self.embeddings.encode([query])[0]
            ranked = sorted(
                ((row["id"], sum(a * b for a, b in zip(vector, json.loads(row["vector"]), strict=True)))
                 for row in rows), key=lambda item: (-item[1], item[0]),
            )
            for rank, (identity, similarity) in enumerate(ranked[:100], 1):
                if similarity > 0:
                    scores[identity] = scores.get(identity, 0) + (
                        similarity if mode == "vector" else 1 / (60 + rank)
                    )
        by_id = {row["id"]: row for row in rows}
        ordered = sorted(scores, key=lambda identity: (-scores[identity], identity))[:limit]
        return {
            "scope": scope, "mode": mode, "embedding_provider": self.embeddings.provider,
            "embedding_signature": self.embeddings.signature,
            "semantic": self.embeddings.provider == "sentence_transformers",
            "nodes": [
                {"id": identity, "ref": by_id[identity]["ref"], "text": by_id[identity]["content"],
                 "metadata": json.loads(by_id[identity]["metadata"]), "score": scores[identity]}
                for identity in ordered
            ],
        }

    def add_memory(self, memory: Memory, old_id: str | None = None) -> dict:
        identity = str(uuid.uuid4())
        body = {
            **memory.model_dump(), "id": identity, "created_at": timestamp(),
            "updated_at": timestamp(), "deleted": False, "superseded_by": None,
        }
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if old_id:
                old = self._memory(db, old_id)
                if old["project_id"] != memory.project_id:
                    raise ValueError("Superseding memory must belong to the same project")
                if old["deleted"] or old["superseded_by"]:
                    raise ValueError("Cannot supersede an inactive memory")
                old.update(superseded_by=identity, updated_at=timestamp())
                db.execute("UPDATE project_memories SET body=? WHERE id=?", (json.dumps(old), old_id))
            db.execute(
                "INSERT INTO project_memories VALUES (?, ?, ?)",
                (identity, memory.project_id, json.dumps(body)),
            )
        return {"success": True, "memory_id": identity, "new_memory_id": identity, "memory": body}

    @staticmethod
    def _memory(db, identity: str) -> dict:
        row = db.execute("SELECT body FROM project_memories WHERE id=?", (identity,)).fetchone()
        if row is None:
            raise KeyError(identity)
        return json.loads(row["body"])

    def get_memory(self, identity: str) -> dict:
        with self.connect() as db:
            return {"success": True, "memory": self._memory(db, identity)}

    def update_memory(self, identity: str, update: MemoryUpdate) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            memory = self._memory(db, identity)
            if memory["deleted"] or memory["superseded_by"]:
                raise ValueError("Cannot update an inactive memory")
            changes = update.model_dump(exclude_unset=True)
            if any(changes.get(key, "") is None for key in ("title", "content", "importance", "tags", "related_refs", "metadata")):
                raise ValueError("Required memory fields cannot be null")
            validated = Memory.model_validate({
                key: changes.get(key, memory[key]) for key in Memory.model_fields
            })
            memory.update(validated.model_dump(), updated_at=timestamp())
            db.execute("UPDATE project_memories SET body=? WHERE id=?", (json.dumps(memory), identity))
        return {"success": True, "memory": memory}

    def delete_memory(self, identity: str) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            memory = self._memory(db, identity)
            memory.update(deleted=True, updated_at=timestamp())
            db.execute("UPDATE project_memories SET body=? WHERE id=?", (json.dumps(memory), identity))
        return {"success": True, "memory_id": identity}

    def search_memories(self, project_id: str, query: str = "", memory_type: str | None = None,
                        tags: list[str] | None = None, min_importance: float = 0,
                        limit: int = 20, include_inactive: bool = False) -> dict:
        with self.connect() as db:
            rows = db.execute(
                "SELECT body FROM project_memories WHERE project_id=?", (project_id,),
            ).fetchall()
        tokens = query.lower().split()
        memories = [json.loads(row["body"]) for row in rows]
        memories = [
            memory for memory in memories
            if (include_inactive or not (memory["deleted"] or memory["superseded_by"]))
            and (not memory_type or memory["memory_type"] == memory_type)
            and memory["importance"] >= min_importance
            and (not tags or set(tags).issubset(memory["tags"]))
            and all(token in " ".join(
                [memory["title"], memory["content"], memory["reason"] or "", *memory["tags"]]
            ).lower() for token in tokens)
        ]
        memories.sort(key=lambda memory: (-memory["importance"], memory["created_at"], memory["id"]))
        return {"success": True, "memories": memories[:limit], "total_count": len(memories)}

    def summary(self, project_id: str) -> dict:
        result = self.search_memories(project_id, limit=10000)
        groups = {}
        for memory in result["memories"]:
            groups.setdefault(memory["memory_type"], []).append(memory)
        return {"success": True, "project_id": project_id,
                "summary": {"total_memories": result["total_count"], "by_type": groups}}

    def conversation(self, project_id: str, session_id: str) -> dict:
        with self.connect() as db:
            row = db.execute(
                "SELECT body FROM conversations WHERE id=? AND project_id=?", (session_id, project_id),
            ).fetchone()
        return json.loads(row["body"]) if row else {
            "session_id": session_id, "project_id": project_id, "messages": [],
        }

    def append_conversation(self, project_id: str, session_id: str, question: str, answer: str):
        with self.connect() as db:
            # Serialize read/modify/write across threads and processes.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT body FROM conversations WHERE id=? AND project_id=?", (session_id, project_id),
            ).fetchone()
            conversation = json.loads(row["body"]) if row else {
                "session_id": session_id, "project_id": project_id, "messages": [],
            }
            conversation["messages"].extend([
                {"role": "user", "content": question}, {"role": "assistant", "content": answer},
            ])
            conversation["messages"] = conversation["messages"][-40:]
            db.execute(
                "INSERT OR REPLACE INTO conversations VALUES (?, ?, ?)",
                (session_id, project_id, json.dumps(conversation)),
            )

    def graph_node(self, scope: str, identity: str, labels: list[str], properties: dict) -> dict:
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO entities VALUES (?, ?, ?, ?)",
                       (identity, scope, json.dumps(labels), json.dumps(properties)))
        return {"id": identity, "scope": scope, "labels": labels, "properties": properties}

    def graph_relationship(self, scope: str, source: str, target: str,
                           kind: str, properties: dict) -> dict:
        identity = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for endpoint in (source, target):
                if db.execute("SELECT 1 FROM entities WHERE scope=? AND id=?",
                              (scope, endpoint)).fetchone() is None:
                    raise KeyError(endpoint)
            db.execute("INSERT INTO relationships VALUES (?, ?, ?, ?, ?, ?)",
                       (identity, scope, source, target, kind, json.dumps(properties)))
        return {"id": identity, "scope": scope, "source": source, "target": target,
                "type": kind, "properties": properties}

    def graph_neighbors(self, scope: str, identity: str, depth: int = 1, limit: int = 100) -> dict:
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM entities WHERE scope=? AND id=?",
                              (scope, identity)).fetchone():
                raise KeyError(identity)
            nodes = db.execute("SELECT * FROM entities WHERE scope=?", (scope,)).fetchall()
            links = db.execute("SELECT * FROM relationships WHERE scope=?", (scope,)).fetchall()
        seen = {identity}
        frontier = {identity}
        truncated = False
        for _ in range(depth):
            adjacent = {
                endpoint for link in links if link["source"] in frontier or link["target"] in frontier
                for endpoint in (link["source"], link["target"])
            } - seen
            available = max(0, limit - len(seen))
            if len(adjacent) > available:
                truncated = True
            frontier = set(sorted(adjacent)[:available])
            seen.update(frontier)
        return {
            "nodes": [{"id": row["id"], "labels": json.loads(row["labels"]),
                       "properties": json.loads(row["properties"])} for row in nodes if row["id"] in seen],
            "relationships": [
                {**dict(row), "properties": json.loads(row["properties"])}
                for row in links if row["source"] in seen and row["target"] in seen
            ], "truncated": truncated,
        }

    def delete_graph_node(self, scope: str, identity: str):
        with self.connect() as db:
            if db.execute("DELETE FROM entities WHERE scope=? AND id=?",
                          (scope, identity)).rowcount == 0:
                raise KeyError(identity)
            db.execute("DELETE FROM relationships WHERE scope=? AND (source=? OR target=?)",
                       (scope, identity, identity))
        return {"success": True}

    def delete_relationship(self, scope: str, identity: str):
        with self.connect() as db:
            if db.execute("DELETE FROM relationships WHERE scope=? AND id=?",
                          (scope, identity)).rowcount == 0:
                raise KeyError(identity)
        return {"success": True}

    def statistics(self) -> dict:
        with self.connect() as db:
            return {
                table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in ("rag_chunks", "project_memories", "conversations", "entities", "relationships")
            }

    def clear(self, scope: str, confirmation: str):
        if confirmation != scope:
            raise ValueError("Confirmation must exactly match the scope to clear")
        with self.connect() as db:
            for table, field in (
                ("rag_chunks", "scope"), ("rag_fts", "scope"), ("rag_snapshots", "scope"),
                ("entities", "scope"), ("relationships", "scope"),
            ):
                db.execute(f"DELETE FROM {table} WHERE {field}=?", (scope,))
        return {"success": True, "scope": scope}

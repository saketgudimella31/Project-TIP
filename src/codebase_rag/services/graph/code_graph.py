"""Persistent, repository-scoped import graphs without a Neo4j server."""

import ast
import hashlib
import json
import logging
import re
import sqlite3
import threading
from collections import defaultdict, deque
from pathlib import Path, PurePosixPath
from typing import Literal
from .symbols import extract_symbols

logger = logging.getLogger(__name__)

Backend = Literal["kuzu", "sqlite"]
Edge = tuple[str, str, int]
LIMITATIONS = [
    "Static Python and JavaScript/TypeScript imports and conservatively resolved calls.",
    "Dynamic dispatch, reflection, module aliases and external package implementations may be unresolved.",
    "Unresolved calls are reported, not invented; no static graph proves runtime behavior.",
]


def import_edges(sources: dict[str, str]) -> tuple[list[Edge], list[str]]:
    modules: dict[str, set[str]] = defaultdict(set)
    for path in sources:
        if path.endswith(".py"):
            module = path.removesuffix(".py").removesuffix("/__init__").replace("/", ".")
            modules[module].add(path)
            if module.startswith("src."):
                modules[module[4:]].add(path)

    edges: dict[tuple[str, str], int] = {}
    warnings = []

    def python_target(module: str) -> str | None:
        matches = modules.get(module, set())
        return next(iter(matches)) if len(matches) == 1 else None

    def add(source: str, target: str | None, line: int):
        if target and source != target:
            key = (source, target)
            edges[key] = min(edges.get(key, line), line)

    for path, content in sorted(sources.items()):
        if path.endswith(".py"):
            try:
                tree = ast.parse(content, filename=path)
            except SyntaxError as error:
                warning = f"Python imports could not be parsed in {path} at line {error.lineno}"
                logger.warning(warning)
                warnings.append(warning)
                continue
            package = list(PurePosixPath(path).parent.parts)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        add(path, python_target(alias.name), node.lineno)
                elif isinstance(node, ast.ImportFrom):
                    if node.level > len(package):
                        continue
                    prefix = package[:len(package) - node.level + 1] if node.level else []
                    base = ".".join(prefix + ([node.module] if node.module else []))
                    add(path, python_target(base), node.lineno)
                    for alias in node.names:
                        name = f"{base}.{alias.name}" if base else alias.name
                        add(path, python_target(name), node.lineno)
        elif PurePosixPath(path).suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            # Preserve strings/newlines while masking comments before locating literal imports.
            clean = re.sub(
                r"""("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|//[^\n]*|/\*[\s\S]*?\*/""",
                lambda match: match.group(1) or re.sub(r"[^\n]", " ", match.group()),
                content,
            )
            pattern = (
                r"""(?:\b(?:import|export)\s+(?:[^;'"]*?\s+from\s*)?|\brequire\s*\(\s*)"""
                r"""['"](?P<target>\.[^'"]+)['"]"""
                r"""|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`"""
            )
            for match in re.finditer(pattern, clean):
                if match.group("target") is None:
                    continue
                parts = list(PurePosixPath(path).parent.parts)
                for part in match.group("target").split("/"):
                    if part == "..":
                        if not parts:
                            break
                        parts.pop()
                    elif part not in {"", "."}:
                        parts.append(part)
                else:
                    base = "/".join(parts)
                    candidates = [base]
                    if base.endswith((".js", ".jsx", ".mjs", ".cjs")):
                        stem = str(PurePosixPath(base).with_suffix(""))
                        candidates.extend(stem + ext for ext in (".ts", ".tsx", ".mts", ".cts"))
                    candidates.extend(base + ext for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"))
                    candidates.extend(base + "/index" + ext for ext in (".ts", ".tsx", ".js", ".jsx"))
                    target = next((candidate for candidate in candidates if candidate in sources), None)
                    add(path, target, clean.count("\n", 0, match.start()) + 1)
    return [(source, target, line) for (source, target), line in sorted(edges.items())], warnings


class CodeGraph:
    """A derived graph; source snapshots in the TIP store remain authoritative."""

    def __init__(self, path: Path, backend: Backend = "kuzu"):
        self.backend = backend
        self.lock = threading.RLock()
        self.closed = False
        path.parent.mkdir(parents=True, exist_ok=True)
        self.database = None
        if backend == "kuzu":
            try:
                import kuzu
            except ModuleNotFoundError as error:
                if error.name != "kuzu":
                    raise
                raise RuntimeError(
                    "Kuzu is not installed. Install the backend's [graph] extra "
                    "or explicitly select TIP_GRAPH_BACKEND=sqlite."
                ) from error

            self.database = kuzu.Database(
                str(path), buffer_pool_size=64 * 1024 * 1024, max_num_threads=2,
            )
            self.connection = kuzu.Connection(self.database)
            self._query(
                "CREATE NODE TABLE IF NOT EXISTS SourceFile("
                "id STRING, repo_id STRING, path STRING, PRIMARY KEY(id))"
            )
            self._query(
                "CREATE REL TABLE IF NOT EXISTS IMPORTS("
                "FROM SourceFile TO SourceFile, line INT64)"
            )
            self._query(
                "CREATE NODE TABLE IF NOT EXISTS Symbol("
                "id STRING, repo_id STRING, path STRING, name STRING, kind STRING, "
                "line INT64, end_line INT64, PRIMARY KEY(id))"
            )
            self._query(
                "CREATE REL TABLE IF NOT EXISTS DEFINED_IN(FROM Symbol TO SourceFile)"
            )
            self._query(
                "CREATE REL TABLE IF NOT EXISTS CALLS("
                "FROM SourceFile TO SourceFile, line INT64, caller STRING, callee STRING)"
            )
            self._query(
                "CREATE REL TABLE IF NOT EXISTS SYMBOL_CALLS(FROM Symbol TO Symbol, line INT64)"
            )
            self._query(
                "CREATE NODE TABLE IF NOT EXISTS Snapshot("
                "repo_id STRING, digest STRING, warnings STRING, PRIMARY KEY(repo_id))"
            )
        elif backend == "sqlite":
            self.connection = sqlite3.connect(path, check_same_thread=False)
            self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    repo_id TEXT PRIMARY KEY, digest TEXT NOT NULL, warnings TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS imports (
                    repo_id TEXT NOT NULL, source TEXT NOT NULL, target TEXT NOT NULL,
                    line INTEGER NOT NULL, PRIMARY KEY(repo_id, source, target)
                );
                CREATE INDEX IF NOT EXISTS imports_target ON imports(repo_id, target);
                CREATE TABLE IF NOT EXISTS symbol_snapshots (
                    repo_id TEXT PRIMARY KEY, body TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS calls (
                    repo_id TEXT NOT NULL, source TEXT NOT NULL, target TEXT NOT NULL,
                    line INTEGER NOT NULL, caller TEXT, callee TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS calls_target ON calls(repo_id, target);
            """)
        else:
            raise ValueError(f"Unsupported graph backend: {backend}")

    def _query(self, query: str, parameters: dict | None = None) -> list[list]:
        result = self.connection.execute(query, parameters or {})
        try:
            rows = []
            while result.has_next():
                rows.append(result.get_next())
            return rows
        finally:
            result.close()

    def verify_connectivity(self) -> bool:
        with self.lock:
            if self.closed:
                return False
            try:
                if self.backend == "kuzu":
                    return self._query("RETURN 1") == [[1]]
                return self.connection.execute("SELECT 1").fetchone() == (1,)
            except (RuntimeError, sqlite3.Error):
                logger.exception("Code graph connectivity check failed")
                return False

    def index(self, repo_id: str, sources: dict[str, str]) -> dict:
        digest = hashlib.sha256(
            ("symbols-v1:" + json.dumps(sorted(sources.items()))).encode()
        ).hexdigest()
        with self.lock:
            if self.closed:
                raise RuntimeError("Code graph is closed")
            if self.backend == "kuzu":
                previous = self._query(
                    "MATCH (s:Snapshot {repo_id: $repo}) RETURN s.digest, s.warnings",
                    {"repo": repo_id},
                )
            else:
                previous = self.connection.execute(
                    "SELECT digest, warnings FROM snapshots WHERE repo_id=?", (repo_id,),
                ).fetchall()
            if previous and previous[0][0] == digest:
                return {"backend": self.backend, "warnings": json.loads(previous[0][1])}
            edges, warnings = import_edges(sources)
            code = extract_symbols(sources, edges)
            warnings.extend(code["warnings"])
            if self.backend == "sqlite":
                with self.connection:
                    self.connection.execute("DELETE FROM imports WHERE repo_id=?", (repo_id,))
                    self.connection.executemany(
                        "INSERT INTO imports VALUES (?, ?, ?, ?)",
                        [(repo_id, *edge) for edge in edges],
                    )
                    self.connection.execute(
                        "INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?)",
                        (repo_id, digest, json.dumps(warnings)),
                    )
                    self.connection.execute("DELETE FROM calls WHERE repo_id=?", (repo_id,))
                    self.connection.executemany(
                        "INSERT INTO calls VALUES (?, ?, ?, ?, ?, ?)",
                        [(repo_id, call["source"], call["target"], call["line"],
                          call["caller"], call["callee"]) for call in code["calls"]],
                    )
                    self.connection.execute(
                        "INSERT OR REPLACE INTO symbol_snapshots VALUES (?, ?)",
                        (repo_id, json.dumps(code)),
                    )
            else:
                self._query("BEGIN TRANSACTION")
                try:
                    self._query(
                        "MATCH (s:Symbol) WHERE s.repo_id=$repo DETACH DELETE s",
                        {"repo": repo_id},
                    )
                    self._query(
                        "MATCH (n:SourceFile) WHERE n.repo_id=$repo DETACH DELETE n",
                        {"repo": repo_id},
                    )
                    for path in sorted(sources):
                        self._query(
                            "CREATE (:SourceFile {id: $id, repo_id: $repo, path: $path})",
                            {"id": json.dumps([repo_id, path]), "repo": repo_id, "path": path},
                        )
                    for source, target, line in edges:
                        self._query(
                            "MATCH (s:SourceFile {id: $source}), (t:SourceFile {id: $target}) "
                            "CREATE (s)-[:IMPORTS {line: $line}]->(t)",
                            {"source": json.dumps([repo_id, source]),
                             "target": json.dumps([repo_id, target]), "line": line},
                        )
                    for symbol in code["symbols"]:
                        self._query(
                            "CREATE (:Symbol {id:$id, repo_id:$repo, path:$path, "
                            "name:$name, kind:$kind, line:$line, end_line:$end_line})",
                            {**symbol, "id": json.dumps([repo_id, symbol["id"]]), "repo": repo_id},
                        )
                        self._query(
                            "MATCH (s:Symbol {id:$id}), (f:SourceFile {id:$file}) "
                            "CREATE (s)-[:DEFINED_IN]->(f)",
                            {"id": json.dumps([repo_id, symbol["id"]]),
                             "file": json.dumps([repo_id, symbol["path"]])},
                        )
                    for call in code["calls"]:
                        self._query(
                            "MATCH (s:SourceFile {id:$source}), (t:SourceFile {id:$target}) "
                            "CREATE (s)-[:CALLS {line:$line, caller:$caller, callee:$callee}]->(t)",
                            {"source": json.dumps([repo_id, call["source"]]),
                             "target": json.dumps([repo_id, call["target"]]),
                             "line": call["line"], "caller": call["caller"] or "",
                             "callee": call["callee"]},
                        )
                        if call["caller"]:
                            self._query(
                                "MATCH (s:Symbol {id:$source}), (t:Symbol {id:$target}) "
                                "CREATE (s)-[:SYMBOL_CALLS {line:$line}]->(t)",
                                {"source": json.dumps([repo_id, call["caller"]]),
                                 "target": json.dumps([repo_id, call["callee"]]), "line": call["line"]},
                            )
                    self._query(
                        "MERGE (s:Snapshot {repo_id: $repo}) "
                        "SET s.digest=$digest, s.warnings=$warnings",
                        {"repo": repo_id, "digest": digest, "warnings": json.dumps(warnings)},
                    )
                    self._query("COMMIT")
                except Exception:
                    self._query("ROLLBACK")
                    raise
            return {"backend": self.backend, "warnings": warnings}

    def impact(self, repo_id: str, file: str, sources: dict[str, str],
               depth: int = 2, limit: int = 20) -> dict:
        if not 1 <= depth <= 5 or not 1 <= limit <= 100:
            raise ValueError("Impact depth must be 1-5 and limit must be 1-100")
        if file not in sources:
            raise KeyError(file)
        with self.lock:
            metadata = self.index(repo_id, sources)
            if self.backend == "kuzu":
                edges = self._query(
                    "MATCH (s:SourceFile)-[r:IMPORTS]->(t:SourceFile) "
                    "WHERE s.repo_id=$repo AND t.repo_id=$repo "
                    "RETURN s.path, t.path, r.line, 'IMPORTS'", {"repo": repo_id},
                )
                edges.extend(self._query(
                    "MATCH (s:SourceFile)-[r:CALLS]->(t:SourceFile) "
                    "WHERE s.repo_id=$repo AND t.repo_id=$repo "
                    "RETURN s.path, t.path, r.line, 'CALLS'", {"repo": repo_id},
                ))
            else:
                edges = self.connection.execute(
                    "SELECT source, target, line, 'IMPORTS' FROM imports WHERE repo_id=? "
                    "UNION SELECT source, target, line, 'CALLS' FROM calls WHERE repo_id=?",
                    (repo_id, repo_id),
                ).fetchall()
        reverse: dict[str, set[str]] = defaultdict(set)
        for source, target, _, _ in edges:
            reverse[target].add(source)
        distances = {file: 0}
        queue = deque([file])
        while queue:
            target = queue.popleft()
            if distances[target] >= depth:
                continue
            for source in sorted(reverse[target]):
                if source not in distances:
                    distances[source] = distances[target] + 1
                    queue.append(source)
        paths = sorted((path for path in distances if path != file),
                       key=lambda path: (distances[path], path))
        selected = set(paths[:limit]) | {file}
        return {
            "repo_id": repo_id, "file": file, "depth": depth,
            "backend": self.backend, "warnings": metadata["warnings"],
            "limitations": LIMITATIONS, "truncated": len(paths) > limit,
            "nodes": [
                {"type": "FILE", "path": path, "ref": path, "repoId": repo_id,
                 "relationship": "CALLS" if any(
                     source == path and kind == "CALLS" for source, _, _, kind in edges
                 ) else "IMPORTS", "depth": distances[path],
                 "score": 1 / distances[path]}
                for path in paths[:limit]
            ],
            "relationships": [
                {"source": source, "target": target, "type": kind, "line": line}
                for source, target, line, kind in sorted(edges)
                if source in selected and target in selected
                and distances[source] == distances[target] + 1
            ],
        }

    def symbols(self, repo_id: str, sources: dict[str, str]) -> dict:
        with self.lock:
            self.index(repo_id, sources)
            if self.backend == "sqlite":
                row = self.connection.execute(
                    "SELECT body FROM symbol_snapshots WHERE repo_id=?", (repo_id,),
                ).fetchone()
                return json.loads(row[0])
            # Unresolved calls are diagnostics rather than graph relationships.
            edges, _ = import_edges(sources)
            diagnostics = extract_symbols(sources, edges)
            rows = self._query(
                "MATCH (s:Symbol) WHERE s.repo_id=$repo "
                "RETURN s.path, s.name, s.kind, s.line, s.end_line", {"repo": repo_id},
            )
            diagnostics["symbols"] = [
                {"id": f"{path}::{name}", "path": path, "name": name, "kind": kind,
                 "line": line, "end_line": end}
                for path, name, kind, line, end in rows
            ]
            return diagnostics

    def close(self):
        with self.lock:
            if not self.closed:
                self.connection.close()
                if self.database is not None:
                    self.database.close()
                self.closed = True

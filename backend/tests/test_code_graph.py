import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codebase_rag.services.graph.code_graph import CodeGraph, import_edges
from tip.app import create_app
from tip.config import Settings
from tip.extraction import Extractor
from tip.storage import Store

from .fixtures import sample_result
from .test_workflow import wait_task


@pytest.fixture(params=["kuzu", "sqlite"])
def graph(request, tmp_path):
    service = CodeGraph(tmp_path / "graph", request.param)
    yield service
    service.close()


def test_python_import_resolution_is_scoped_and_static():
    edges, warnings = import_edges({
        "src/pkg/__init__.py": "",
        "src/pkg/utils.py": "def helper(): pass",
        "src/pkg/app.py": "from .utils import helper\nfrom . import utils\n",
        "main.py": "import pkg.app\nfrom pkg import utils\nimport external\n",
        "other.py": "# import pkg.app\ntext = 'import pkg.app'\n",
    })
    assert warnings == []
    assert edges == [
        ("main.py", "src/pkg/__init__.py", 2),
        ("main.py", "src/pkg/app.py", 1),
        ("main.py", "src/pkg/utils.py", 2),
        ("src/pkg/app.py", "src/pkg/__init__.py", 2),
        ("src/pkg/app.py", "src/pkg/utils.py", 1),
    ]


def test_javascript_import_resolution_and_comment_string_exclusion():
    edges, warnings = import_edges({
        "src/app.ts": (
            "import { helper } from './utils.js';\n"
            "export { thing } from './folder';\n"
            "const m = require('../shared');\n"
            "// import './ignored';\n"
            "/* require('./ignored') */\n"
            'const s = "require(\'./ignored\')";\n'
            "const t = `import './ignored'`;\n"
            "import('dynamic');\n"
        ),
        "src/utils.ts": "",
        "src/folder/index.ts": "",
        "shared.js": "",
        "src/ignored.ts": "",
    })
    assert warnings == []
    assert edges == [
        ("src/app.ts", "shared.js", 3),
        ("src/app.ts", "src/folder/index.ts", 2),
        ("src/app.ts", "src/utils.ts", 1),
    ]


def test_python_syntax_errors_are_reported():
    edges, warnings = import_edges({"broken.py": "def broken("})
    assert edges == []
    assert warnings == ["Python imports could not be parsed in broken.py at line 1"]


def test_reverse_traversal_depth_limit_cycles_and_repo_isolation(graph):
    sources = {
        "lib.py": "import main",
        "app.py": "import lib",
        "main.py": "import app",
        "another.py": "import lib",
    }
    graph.index("one", sources)
    graph.index("two", {"lib.py": "", "isolated.py": "import lib"})
    assert graph.verify_connectivity()
    result = graph.impact("one", "lib.py", sources)
    assert [(node["path"], node["depth"]) for node in result["nodes"]] == [
        ("another.py", 1), ("app.py", 1), ("main.py", 2),
    ]
    assert result["relationships"] == [
        {"source": "another.py", "target": "lib.py", "type": "IMPORTS", "line": 1},
        {"source": "app.py", "target": "lib.py", "type": "IMPORTS", "line": 1},
        {"source": "main.py", "target": "app.py", "type": "IMPORTS", "line": 1},
    ]
    assert len(graph.impact("one", "lib.py", sources, depth=1)["nodes"]) == 2
    limited = graph.impact("one", "lib.py", sources, limit=1)
    assert len(limited["nodes"]) == 1
    assert limited["truncated"] is True
    assert "lib.py" not in [node["path"] for node in result["nodes"]]
    with pytest.raises(KeyError):
        graph.impact("two", "app.py", {"lib.py": ""})


def test_snapshot_replacement_deletes_old_edges_and_handles_empty_snapshot(graph):
    original = {"lib.py": "", "app.py": "import lib"}
    graph.index("repo", original)
    assert graph.impact("repo", "lib.py", original)["nodes"]
    changed = {"lib.py": "", "app.py": "# removed import"}
    assert graph.impact("repo", "lib.py", changed)["nodes"] == []
    graph.index("repo", {})
    assert graph.impact("repo", "lib.py", {"lib.py": ""})["nodes"] == []


def test_symbols_and_call_relationships_are_persistent_and_replaced(graph):
    sources = {
        "lib.py": "def helper(): return 1\n",
        "app.py": "from lib import helper\ndef run(): return helper()\n",
    }
    graph.index("repo", sources)
    symbols = graph.symbols("repo", sources)
    assert {symbol["id"] for symbol in symbols["symbols"]} == {"lib.py::helper", "app.py::run"}
    assert symbols["calls"][0]["callee"] == "lib.py::helper"
    impact = graph.impact("repo", "lib.py", sources)
    assert impact["nodes"][0]["relationship"] == "CALLS"
    assert {edge["type"] for edge in impact["relationships"]} == {"IMPORTS", "CALLS"}
    if graph.backend == "kuzu":
        rows = graph._query(
            "MATCH (s:Symbol)-[:SYMBOL_CALLS]->(t:Symbol) "
            "WHERE s.repo_id=$repo RETURN s.name, t.name", {"repo": "repo"},
        )
        assert rows == [["run", "helper"]]
    changed = {"lib.py": sources["lib.py"], "app.py": "def run(): return 2\n"}
    assert graph.impact("repo", "lib.py", changed)["nodes"] == []
    assert graph.symbols("repo", changed)["calls"] == []


@pytest.mark.parametrize("backend", ["kuzu", "sqlite"])
def test_graph_reopens_without_losing_relationships(tmp_path, backend):
    path = tmp_path / "graph"
    sources = {"lib.py": "", "app.py": "import lib"}
    service = CodeGraph(path, backend)
    service.index("repo", sources)
    service.close()
    service.close()
    assert service.verify_connectivity() is False
    reopened = CodeGraph(path, backend)
    try:
        assert reopened.impact("repo", "lib.py", sources)["nodes"][0]["path"] == "app.py"
    finally:
        reopened.close()


def test_authoritative_snapshot_repairs_graph_after_interrupted_commit(tmp_path, graph):
    store = Store(tmp_path / "tip.sqlite3", graph)
    extractor = Extractor(Settings(_env_file=None, data_dir=tmp_path))
    artifacts = extractor.extract("lib.py", b"def helper(): pass")
    artifacts += extractor.extract("app.py", b"import lib")
    store.index("repo", artifacts)
    graph.index("repo", {"lib.py": "", "stale.py": "import lib"})
    result = store.impact("repo", "lib.py", 2, 20)
    assert [node["path"] for node in result["nodes"]] == ["app.py"]


def test_graph_failure_rolls_back_source_snapshot(tmp_path, graph, monkeypatch):
    store = Store(tmp_path / "tip.sqlite3", graph)
    artifacts = Extractor(Settings(_env_file=None)).extract("lib.py", b"original = 1")
    store.index("repo", artifacts)

    def fail(*args):
        raise RuntimeError("synthetic graph failure")

    monkeypatch.setattr(graph, "index", fail)
    changed = Extractor(Settings(_env_file=None)).extract("app.py", b"import lib")
    with pytest.raises(ValueError, match="no source snapshot was committed"):
        store.index("repo", changed)
    assert [artifact.filePath for artifact in store.retrieve("repo")] == ["lib.py"]


@pytest.mark.parametrize("backend", ["kuzu", "sqlite"])
def test_ingestion_search_impact_indexed_analysis_and_restart(tmp_path, backend):
    source = tmp_path / "source"
    source.mkdir()
    (source / "lib.py").write_text("def helper(): return 'ready'")
    (source / "app.py").write_text("from lib import helper\n")
    (source / "main.py").write_text("import app\n")
    config = Settings(
        _env_file=None, data_dir=tmp_path / "data", graph_backend=backend,
        local_source_root=source, gateway_url="https://synthetic.invalid/completions",
    )
    app = create_app(config)
    seen = []

    class SyntheticGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            seen.extend(artifacts)
            return sample_result(target, context, artifacts)

    app.state.manager.gateway = SyntheticGateway()
    with TestClient(app) as client:
        health = client.get("/api/v1/health").json()
        assert health["graph_backend"] == backend
        assert health["services"]["graph_service"] is True
        assert health["services"]["sqlite_connected"] is True
        configuration = client.get("/api/v1/configuration").json()
        assert configuration["graph_backend"] == backend
        assert configuration["retrieval_backend"] == "SQLite FTS5"
        ingest = client.post("/api/v1/ingest/repo", json={"local_path": str(source)})
        assert ingest.status_code == 202
        task = wait_task(client, ingest.json()["task_id"])
        assert task["status"] == "success", task.get("error")
        repo_id = task["result"]["repo_id"]
        response = client.get("/api/v1/graph/impact", params={
            "repoId": repo_id, "file": "lib.py", "depth": 2,
        })
        assert response.status_code == 200
        assert [node["path"] for node in response.json()["nodes"]] == ["app.py", "main.py"]
        context = client.get("/api/v1/context/pack", params={
            "repoId": repo_id, "focus": "helper", "budget": 100,
        }).json()
        assert {item["ref"] for item in context["items"]} == {"app.py", "lib.py"}
        assert context["budget_used"] <= 100
        analysis = client.post("/api/v1/analysis", data={"options": json.dumps({
            "target_application": "Imports", "code_source": "indexed",
            "indexed_repo_id": repo_id, "focus": "helper",
        })})
        assert analysis.status_code == 202, analysis.text
        completed = wait_task(client, analysis.json()["task_id"])
        assert completed["status"] == "success", completed.get("error")
        assert {artifact.filePath for artifact in seen} == {"app.py", "lib.py", "main.py"}
        assert client.get(f"/api/v1/tasks/{completed['task_id']}/document").status_code == 200
        for invalid in [{"depth": 0}, {"depth": 6}, {"limit": 0}, {"limit": 101}]:
            assert client.get("/api/v1/graph/impact", params={
                "repoId": repo_id, "file": "lib.py", **invalid,
            }).status_code == 422
        assert client.get("/api/v1/graph/impact", params={
            "repoId": "unknown", "file": "lib.py",
        }).status_code == 404
    with TestClient(create_app(config)) as client:
        assert client.get("/api/v1/graph/impact", params={
            "repoId": repo_id, "file": "lib.py",
        }).json()["nodes"][0]["path"] == "app.py"


def test_ingestion_indexes_only_selected_subdirectory(tmp_path):
    source = tmp_path / "source"
    selected = source / "packages" / "api"
    selected.mkdir(parents=True)
    (selected / "app.py").write_text("def selected_api(): return 1")
    (source / "other").mkdir()
    (source / "other" / "ignored.py").write_text("def unrelated(): return 2")
    config = Settings(
        _env_file=None, data_dir=tmp_path / "data",
        local_source_root=source, graph_backend="sqlite",
    )
    app = create_app(config)
    with TestClient(app) as client:
        response = client.post("/api/v1/ingest/repo", json={
            "local_path": str(source), "selected_path": "packages/api",
        })
        assert response.status_code == 202
        task = wait_task(client, response.json()["task_id"])
        assert task["status"] == "success", task.get("error")
        artifacts = app.state.store.retrieve(task["result"]["repo_id"])
        assert [artifact.filePath for artifact in artifacts] == ["packages/api/app.py"]


def test_standalone_entry_point_does_not_import_legacy_neo4j():
    result = subprocess.run([
        sys.executable, "-c",
        "from codebase_rag.server.local import create_app; "
        "import tip.app, sys; assert 'neo4j' not in sys.modules; "
        "assert 'llama_index' not in sys.modules",
    ], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_postman_copies_cover_graph_workflow():
    root = Path(__file__).resolve().parents[2]
    collection = root / "postman/tip-integration_postman_TIP.postman_collection.json"
    copy = root / "frontend/tip-integration_postman_TIP.postman_collection.json"
    assert collection.read_bytes() == copy.read_bytes()
    data = json.loads(collection.read_text())
    requests = [item["request"] for item in data["item"]]
    urls = [request["url"] for request in requests]
    assert any("/ingest/repo" in url for url in urls)
    assert any("/graph/impact" in url for url in urls)
    assert any("/graph/related" in url for url in urls)
    assert any("indexed_repo_id" in json.dumps(request) for request in requests)

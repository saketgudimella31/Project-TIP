import asyncio
import base64
import hashlib
import hmac
import io
import json
import os
import socket
import sys
import threading
import time
import zipfile
from pathlib import Path

import httpx
import pytest
import uvicorn
from docx import Document
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import SecretStr

from codebase_rag.services.graph.symbols import extract_symbols
from codebase_rag.services.graph.code_graph import import_edges
from codebase_rag.services.knowledge.local_store import Embeddings, LocalKnowledge, Memory
from tip.app import create_app
from tip.config import Settings
from tip.models import Artifact, InputContext
from .fixtures import sample_result
from .test_workflow import wait_task, workbook_bytes, docx_bytes


def memory(project="repo", **changes):
    return Memory(project_id=project, memory_type="decision", title="Use a local graph",
                  content="Persist source relationships locally", tags=["graph"], **changes)


def test_call_resolution_python_typescript_and_unresolved_dispatch():
    sources = {
        "lib.py": "def helper(): return 1\n",
        "app.py": (
            "from lib import helper as h\n"
            "class Service:\n"
            " def run(self): return self.work()\n"
            " def work(self): return h()\n"
            "def main():\n"
            " unknown.method()\n"
        ),
        "utils.ts": "export function helper(){ return 1; }\n",
        "app.ts": "import {helper as h} from './utils';\nexport const run = () => h();\n",
    }
    imports, _ = import_edges(sources)
    graph = extract_symbols(sources, imports)
    assert {call["callee"] for call in graph["calls"]} == {
        "lib.py::helper", "app.py::Service.work", "utils.ts::helper",
    }
    assert graph["unresolved_calls"] == [{"path": "app.py", "line": 6, "name": "unknown.method"}]
    assert any(symbol["name"] == "run" for symbol in graph["symbols"] if symbol["path"] == "app.ts")


def test_call_resolution_does_not_invent_import_edges_for_shadowed_parameters():
    sources = {
        "lib.py": "def helper(): pass",
        "app.py": "from lib import helper\ndef run(helper): return helper()\n",
        "lib.ts": "export function helper() {}",
        "app.ts": "import {helper} from './lib';\nfunction run(helper: Function){ helper(); }\n",
    }
    imports, _ = import_edges(sources)
    graph = extract_symbols(sources, imports)
    assert graph["calls"] == []
    assert {call["path"] for call in graph["unresolved_calls"]} == {"app.py", "app.ts"}


def test_vector_search_chunking_reopen_scope_and_provider_mismatch(tmp_path):
    path = tmp_path / "knowledge.sqlite3"
    knowledge = LocalKnowledge(path, Embeddings(), chunk_size=200)
    knowledge.add_document("one", "payments settlement reconciliation " * 20, "Payments")
    knowledge.add_document("two", "payments settlement other project", "Other")
    for mode in ("keyword", "vector", "hybrid"):
        result = knowledge.search("one", "settlement reconciliation", mode)
        assert result["nodes"]
        assert result["semantic"] is False
        assert all(len(node["text"]) <= 200 for node in result["nodes"])
        assert all(node["metadata"]["title"] == "Payments" for node in result["nodes"])
    reopened = LocalKnowledge(path, Embeddings())
    assert reopened.search("one", "settlement", "vector")["nodes"]
    different = LocalKnowledge(path, Embeddings(dimension=128))
    with pytest.raises(ValueError, match="re-index"):
        different.search("one", "settlement")
    with pytest.raises(ValueError, match="re-index"):
        different.add_document("one", "settlement", "New")
    with pytest.raises(ValueError):
        knowledge.search("one", "settlement", "invalid")


def test_semantic_encoder_contract_without_downloading_a_model(tmp_path):
    class Encoder:
        def encode(self, texts, normalize_embeddings):
            assert normalize_embeddings is True
            return self

        def tolist(self):
            return [[1.0, 0.0]]

    embeddings = Embeddings("sentence_transformers", "test-model", dimension=2)
    embeddings.encoder = Encoder()
    assert embeddings.encode(["test"]) == [[1, 0]]
    embeddings.dimension = 3
    with pytest.raises(ValueError, match="dimension"):
        embeddings.encode(["test"])


@pytest.mark.parametrize("backend", ["kuzu", "sqlite"])
def test_memory_graph_conversation_and_search_rest_lifecycle(tmp_path, backend):
    config = Settings(_env_file=None, data_dir=tmp_path, graph_backend=backend)
    with TestClient(create_app(config)) as client:
        assert client.get("/api/v1/tasks/stats").status_code == 200
        added = client.post("/api/v1/memory/add", json=memory().model_dump())
        assert added.status_code == 201
        identity = added.json()["memory_id"]
        assert client.get("/api/v1/memory/search", params={"project_id": "other"}).json()["memories"] == []
        found = client.get("/api/v1/memory/search", params={
            "project_id": "repo", "tags": "graph", "min_importance": 0.4,
        }).json()
        assert found["memories"][0]["id"] == identity
        assert client.patch(f"/api/v1/memory/{identity}", json={"importance": 1.5}).status_code == 422
        assert client.patch(f"/api/v1/memory/{identity}", json={"title": "Kuzu graph"}).status_code == 200
        superseded = client.post(f"/api/v1/memory/{identity}/supersede", json=memory().model_dump())
        assert superseded.status_code == 200
        replacement = superseded.json()["new_memory_id"]
        assert client.get(f"/api/v1/memory/{identity}").json()["memory"]["superseded_by"] == replacement
        assert client.get("/api/v1/memory/summary/repo").json()["summary"]["total_memories"] == 1
        assert client.delete(f"/api/v1/memory/{replacement}").status_code == 200
        assert client.get("/api/v1/memory/search", params={"project_id": "repo"}).json()["memories"] == []
        assert client.get(f"/api/v1/memory/{replacement}").json()["memory"]["deleted"] is True
        assert client.get("/api/v1/memory/missing").status_code == 404
        assert client.post("/api/v1/conversations/session", params={"project_id": "repo"}, json={
            "question": "Why use Kuzu?", "answer": "It is embedded.",
        }).status_code == 200
        assert len(client.get("/api/v1/conversations/session", params={"project_id": "repo"}).json()["messages"]) == 2
        for identity in ("table", "column"):
            assert client.post("/api/v1/graph/nodes", json={
                "scope": "schema", "id": identity, "labels": ["Table"], "properties": {"name": identity},
            }).status_code == 201
        assert client.post("/api/v1/graph/relationships", json={
            "scope": "schema", "source": "table", "target": "column", "type": "HAS_COLUMN",
        }).status_code == 201
        assert len(client.get("/api/v1/graph/neighbors", params={
            "scope": "schema", "id": "table",
        }).json()["nodes"]) == 2
        assert client.get("/api/v1/graph/neighbors", params={
            "scope": "other", "id": "table",
        }).status_code == 404
        assert client.delete("/api/v1/graph/nodes/column", params={"scope": "schema"}).status_code == 200
        assert client.get("/api/v1/graph/neighbors", params={
            "scope": "schema", "id": "table",
        }).json()["relationships"] == []
        document = client.post("/api/v1/knowledge/documents", json={
            "scope": "schema", "title": "Payments", "content": "Payments settlement reconciliation",
        })
        assert document.status_code == 201
        assert client.get("/api/v1/knowledge/search", params={
            "scope": "schema", "query": "settlement", "mode": "vector",
        }).json()["nodes"]
        assert client.post("/api/v1/knowledge/clear", json={
            "scope": "schema", "confirmation": "wrong",
        }).status_code == 422
        assert client.post("/api/v1/knowledge/clear", json={
            "scope": "schema", "confirmation": "schema",
        }).status_code == 200
    with TestClient(create_app(config)) as client:
        assert len(client.get("/api/v1/conversations/session", params={"project_id": "repo"}).json()["messages"]) == 2
        assert client.get(f"/api/v1/memory/{identity}").status_code == 404  # graph IDs are not memory IDs


def test_memory_supersession_is_atomic_and_project_scoped(tmp_path):
    knowledge = LocalKnowledge(tmp_path / "memory.sqlite3", Embeddings())
    old = knowledge.add_memory(memory())["memory_id"]
    with pytest.raises(ValueError, match="same project"):
        knowledge.add_memory(memory("other"), old)
    assert knowledge.get_memory(old)["memory"]["superseded_by"] is None
    replacement = knowledge.add_memory(memory(), old)["memory_id"]
    with pytest.raises(ValueError, match="inactive"):
        knowledge.add_memory(memory(), old)
    assert knowledge.search_memories("repo")["memories"][0]["id"] == replacement


@pytest.fixture
def running_server():
    running = []

    def start(app):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="on"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        for _ in range(100):
            if server.started:
                running.append((server, thread, sock))
                return f"http://127.0.0.1:{sock.getsockname()[1]}"
            time.sleep(0.02)
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        raise AssertionError("Server did not start")

    yield start
    for server, thread, sock in reversed(running):
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        assert not thread.is_alive()


def synthetic_gateway_app(seen, diagram_enabled=False):
    gateway = FastAPI()

    @gateway.post("/ai-gateway/v1/chat/completions")
    async def complete(request: Request):
        raw = await request.body()
        headers = request.headers
        signature = (
            headers["api-key"] + headers["Client-Request-Id"] + headers["Timestamp"]
        ).encode() + raw
        assert headers["api-key"] == "synthetic-consumer"
        assert headers["Authorization"] == base64.b64encode(
            hmac.new(b"synthetic-secret", signature, hashlib.sha256).digest(),
        ).decode()
        data = json.loads(raw)
        assert data["stream"] is False
        payload = json.loads(data["messages"][1]["content"].split("\n", 1)[-1]) if "Target_Application" in data["messages"][1]["content"] else json.loads(data["messages"][1]["content"])
        seen.append((payload, headers["Client-Request-Id"], headers["Timestamp"]))
        if "Target_Application" in payload:
            artifacts = [
                Artifact.model_validate(artifact)
                for key in ("Codebase_Data", "Design_Document_Data", "Jira_User_Stories_Data", "Raw_Requirements_Data")
                for artifact in payload[key]
            ]
            result = sample_result(
                payload["Target_Application"], InputContext.model_validate(payload["Input_Context"]),
                artifacts, with_diagram=diagram_enabled,
            ).model_dump()
        elif "sources" in payload:
            result = {"answer": "Settlement is documented in the supplied source.",
                      "citations": [payload["sources"][0]["id"]]}
        else:
            result = {"memories": [memory(payload["project_id"]).model_dump()]}
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(result)}}]}

    return gateway


@pytest.mark.parametrize("source_kind", ["upload", "archive", "folder", "repository", "local", "story"])
@pytest.mark.parametrize("with_uml", [False, True])
def test_real_http_signed_gateway_rag_to_word(tmp_path, running_server, monkeypatch, source_kind, with_uml):
    seen = []
    gateway_url = running_server(synthetic_gateway_app(seen, diagram_enabled=with_uml))
    source = tmp_path / "source"
    source.mkdir()
    (source / "orders.py").write_text("def order_status(): return 'ready'")
    selected_source = source / "packages" / "api"
    selected_source.mkdir(parents=True)
    (selected_source / "orders.py").write_text("def order_status(): return 'ready'")
    if source_kind == "repository":
        from contextlib import contextmanager

        @contextmanager
        def repository_source(settings, **kwargs):
            assert kwargs["repo_url"] == "https://gitlab.com/example/orders"
            assert kwargs["selected_path"] == "packages/api"
            yield selected_source

        monkeypatch.setattr("tip.service.source_directory", repository_source)
    config = Settings(
        _env_file=None, data_dir=tmp_path / "data", graph_backend="sqlite",
        local_source_root=source, gateway_url=gateway_url + "/ai-gateway/v1/chat/completions",
        gateway_app_consumer_key=SecretStr("synthetic-consumer"),
        gateway_hmac_secret=SecretStr("synthetic-secret"),
    )
    with TestClient(create_app(config)) as client:
        options = {"target_application": "Orders"}
        files = []
        if source_kind in {"upload", "folder"}:
            name = "orders.py" if source_kind == "upload" else "folder/orders.py"
            options["upload_kind"] = "LOCAL_FILES" if source_kind == "upload" else "LOCAL_FOLDER"
            files = [("code_files", (name, b"def order_status(): return 'ready'", "text/plain")),
                     ("design_files", ("design.docx", docx_bytes(), "application/octet-stream")),
                     ("requirements_files", ("requirements.xlsx", workbook_bytes(), "application/octet-stream"))]
        elif source_kind == "archive":
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr("src/orders.py", "def order_status(): return 'ready'")
            files = [("code_files", ("code.zip", stream.getvalue(), "application/zip"))]
        elif source_kind == "repository":
            options.update(
                code_source="repository",
                repo_url="https://gitlab.com/example/orders",
                selected_path="packages/api",
            )
        elif source_kind == "local":
            options.update(code_source="local", local_path=str(source))
        else:
            options["manual_stories"] = [{
                "id": "US-1", "title": "Order status", "description": "Display order status.",
            }]
        response = client.post("/api/v1/analysis", data={"options": json.dumps(options)}, files=files)
        assert response.status_code == 202, response.text
        task = wait_task(client, response.json()["task_id"])
        assert task["status"] == "success", task.get("error")
        assert task["result"]["rag_scope"].startswith("analysis:")
        assert client.get("/api/v1/knowledge/search", params={
            "scope": task["result"]["rag_scope"], "query": "order", "mode": "vector",
        }).json()["nodes"]
        document = client.get(f"/api/v1/tasks/{task['task_id']}/document")
        assert document.status_code == 200
        assert "attachment" in document.headers["content-disposition"]
        parsed = Document(io.BytesIO(document.content))
        paragraphs = "\n".join(paragraph.text for paragraph in parsed.paragraphs)
        assert "High-Level Functional Requirements" in paragraphs
        assert "Requirements-to-Source-and-Design Traceability" in paragraphs
        assert "Draft for Human Validation" in paragraphs
        assert "HLR-001" in paragraphs
        if with_uml:
            with zipfile.ZipFile(io.BytesIO(document.content)) as archive:
                assert any(name.startswith("word/media/") for name in archive.namelist())
                assert "@startuml" not in archive.read("word/document.xml").decode()
        assert len(seen) == 1
        if source_kind == "repository":
            assert seen[0][0]["Input_Context"]["sourceProvider"] == "GITLAB"
        assert seen[0][2] != "1793876274193"


def test_rag_answer_conversation_and_extraction_use_signed_http(tmp_path, running_server):
    seen = []
    gateway_url = running_server(synthetic_gateway_app(seen))
    app = create_app(Settings(
        _env_file=None, data_dir=tmp_path, graph_backend="sqlite",
        gateway_url=gateway_url + "/ai-gateway/v1/chat/completions",
        gateway_app_consumer_key=SecretStr("synthetic-consumer"),
        gateway_hmac_secret=SecretStr("synthetic-secret"),
    ))
    with TestClient(app) as client:
        client.post("/api/v1/knowledge/documents", json={
            "scope": "repo", "title": "Settlement", "content": "Payments settlement reconciliation",
        }).raise_for_status()
        first = client.post("/api/v1/knowledge/query", json={
            "scope": "repo", "question": "What is settlement?",
        })
        assert first.status_code == 200, first.text
        session = first.json()["session_id"]
        assert first.json()["citations"]
        second = client.post("/api/v1/knowledge/query", json={
            "scope": "repo", "question": "Explain settlement", "session_id": session,
        })
        assert second.status_code == 200, second.text
        assert len(seen[1][0]["history"]) == 2
        extracted = client.post("/api/v1/memory/extract", json={
            "project_id": "repo", "content": "We decided to use a local graph.", "auto_save": True,
        })
        assert extracted.status_code == 200, extracted.text
        assert extracted.json()["total_extracted"] == 1
        assert len(client.get("/api/v1/memory/search", params={"project_id": "repo"}).json()["memories"]) == 1
        assert len({identity for _, identity, _ in seen}) == len(seen)


def test_invalid_model_citations_and_wrong_project_memory_are_not_published(tmp_path, monkeypatch):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path, graph_backend="sqlite"))
    with TestClient(app) as client:
        client.post("/api/v1/knowledge/documents", json={
            "scope": "repo", "title": "Settlement", "content": "Payments settlement",
        }).raise_for_status()
        monkeypatch.setattr(app.state.manager.gateway, "complete_json", lambda *args: {
            "answer": "Unsupported answer", "citations": ["invented-source"],
        })
        answer = client.post("/api/v1/knowledge/query", json={
            "scope": "repo", "question": "settlement", "session_id": "session",
        })
        assert answer.status_code == 502
        assert app.state.knowledge.conversation("repo", "session")["messages"] == []
        monkeypatch.setattr(app.state.manager.gateway, "complete_json", lambda *args: {
            "memories": [memory("different-project").model_dump()],
        })
        extracted = client.post("/api/v1/memory/extract", json={
            "project_id": "repo", "content": "A decision", "auto_save": True,
        })
        assert extracted.status_code == 502
        assert app.state.knowledge.search_memories("different-project")["memories"] == []


def test_actual_mcp_stdio_roundtrip_against_running_api(tmp_path, running_server):
    api_url = running_server(create_app(Settings(_env_file=None, data_dir=tmp_path, graph_backend="sqlite")))

    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "codebase_rag", "--mcp", "--api-url", api_url + "/api/v1"],
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) >= 31
                resources = await session.list_resources()
                assert len(resources.resources) == 2
                added = await session.call_tool("add_memory", {
                    "project_id": "repo", "memory_type": "decision",
                    "title": "Local storage", "content": "Use embedded storage",
                })
                assert not added.isError
                searched = await session.call_tool("search_memories", {"project_id": "repo"})
                assert not searched.isError
                assert "Local storage" in str(searched.content)
                stats = await session.call_tool("get_queue_stats", {})
                assert not stats.isError
                schema = await session.read_resource("tip://schema")
                assert "CALLS" in str(schema.contents)
                document = await session.call_tool("add_document", {
                    "scope": "repo", "title": "Payments", "content": "Payments settlement",
                })
                assert not document.isError
                results = await session.call_tool("search_similar_nodes", {
                    "scope": "repo", "query": "settlement",
                })
                assert not results.isError
                assert "Payments settlement" in str(results.content)
    asyncio.run(run())

import base64
import hashlib
import hmac
import io
import json
import os
import sqlite3
import struct
import subprocess
import threading
import time
import zipfile
import zlib
from pathlib import Path

import httpx
import openpyxl
import pytest
import xlwt
from docx import Document
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from tip.app import create_app
from tip.config import Settings
from tip.documents import (
    create_business_document,
    create_document,
    ensure_source_component_diagram,
    mermaid_renderer_configured,
    mermaid_renderer_issue,
    render_diagram,
    render_generated_diagrams,
)
from tip.extraction import Extractor, jira_stories, source_directory
from tip.gateway import Gateway, GatewayError, model_body, signed_headers
from tip.models import AnalysisOptions, InputContext, ManualStory, SupportingInputs
from tip.storage import Store
from tip.validation import INVALID_DIAGRAM_WARNING, validate_mermaid, validate_result
from codebase_rag.services.knowledge.local_store import Embeddings, LocalKnowledge

from .fixtures import sample_result

def png_chunk(kind, data):
    return (
        struct.pack(">I", len(data)) + kind + data
        + struct.pack(">I", zlib.crc32(kind + data))
    )


TEST_PNG = b"\x89PNG\r\n\x1a\n" + b"".join((
    png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)),
    png_chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff")),
    png_chunk(b"IEND", b""),
))

def settings(tmp_path, **values):
    defaults = {
        "gateway_url": "",
        "gateway_api_key": SecretStr(""),
        "gateway_app_consumer_key": SecretStr(""),
        "gateway_hmac_secret": SecretStr(""),
        "gateway_headers_json": SecretStr(json.dumps({
            "api-key": "{api_key}",
            "Timestamp": "{timestamp}",
            "Client-Request-Id": "{request_id}",
            "Authorization": "{signature}",
            "Accept": "application/json",
        })),
        "gateway_signature_template": (
            "{api_key}{request_id}{timestamp}{body}"
        ),
        "analysis_batch_concurrency": 2,
    }

    defaults.update(values)

    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        **defaults,
    )

def test_store_migrates_business_document_column(tmp_path):
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as db:
        db.execute(
            "CREATE TABLE tasks (id TEXT PRIMARY KEY, body TEXT NOT NULL, document BLOB)"
        )
        db.execute(
            "INSERT INTO tasks(id, body) VALUES (?, ?)",
            (
                "legacy-task",
                json.dumps({
                    "task_id": "legacy-task", "status": "failed",
                    "created_at": "2026-01-01T00:00:00+00:00",
                }),
            ),
        )
    store = Store(database_path)
    task = store.create({"kind": "test"})
    store.complete(task["task_id"], {"test": True}, b"technical", b"business")
    assert store.document(task["task_id"]) == b"technical"
    assert store.business_document(task["task_id"]) == b"business"
    assert store.list_tasks("failed", include_result=False)["tasks"][0]["task_id"] == "legacy-task"
    with store.connect() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(tasks)")}
    assert {"business_document", "status", "created_at"}.issubset(columns)


def test_task_history_can_omit_large_results(tmp_path):
    app = create_app(settings(tmp_path))
    store = app.state.store
    completed = store.create({"kind": "analysis", "target_application": "Large"})
    store.complete(completed["task_id"], {"large_output": "x" * 50_000}, b"doc")
    failed = store.create({"kind": "analysis", "target_application": "Failed"})
    store.update(
        failed["task_id"], status="failed", progress=100, message="Failed",
        error="Renderer failure",
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/tasks", params={"include_result": "false"})
        full_response = client.get("/api/v1/tasks")

    assert response.status_code == 200
    history = response.json()
    assert history["total_count"] == 2
    assert {item["status"] for item in history["tasks"]} == {"success", "failed"}
    assert all("result" not in item for item in history["tasks"])
    completed_task = next(
        item for item in full_response.json()["tasks"] if item["status"] == "success"
    )
    assert completed_task["result"]["large_output"] == "x" * 50_000


def test_gateway_repairs_missing_functional_capability_and_warns(tmp_path, monkeypatch):
    settings_value = settings(
        tmp_path, gateway_url="https://gateway.example/completions",
    )
    gateway = Gateway(settings_value)
    artifact = Extractor(settings_value).extract(
        "orders.py", b"def order_status(): return 'ready'",
    )
    model_output = sample_result(
        "Orders", input_context(), artifact,
    ).model_dump()
    del model_output["highLevelRequirements"][0]["capability"]
    monkeypatch.setattr(gateway, "_send", lambda body: model_output)

    result = gateway.analyze("Orders", input_context(), artifact)

    assert result.highLevelRequirements[0].capability == "display order status"
    assert any("derived one or more missing" in warning for warning in result.warnings)


def input_context(**changes):
    return InputContext(
        analysisMode=changes.get("analysisMode", "INCREMENTAL"),
        inputType="LOCAL_FILES", sourceProvider=None, repository=None, branch=None,
        selectedPath=None, supportingInputs=SupportingInputs(
            designDocumentsProvided=False, jiraUserStoriesProvided=False, rawRequirementsProvided=False,
        ),
    )


def test_input_context_accepts_miscased_jira_story_flag():
    context = input_context().model_dump()
    supporting_inputs = context["supportingInputs"]
    supporting_inputs["jiraUserstoriesProvided"] = supporting_inputs.pop(
        "jiraUserStoriesProvided",
    )

    parsed = InputContext.model_validate(context)

    assert parsed.supportingInputs.jiraUserStoriesProvided is False
    assert "jiraUserStoriesProvided" in parsed.supportingInputs.model_dump()


def workbook_bytes():
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Orders"
    sheet.append(["ID", "Requirement"])
    sheet.append(["REQ-1", "The system shall display order status."])
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def docx_bytes():
    document = Document()
    document.add_heading("Orders design", 1)
    document.add_paragraph("The Orders component displays order status.")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Capability"
    table.cell(0, 1).text = "Display order status"
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()


def wait_task(client, task_id, timeout=30.0):
    deadline = time.monotonic() + timeout
    last_task = None

    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200

        last_task = response.json()

        if last_task["status"] not in {"pending", "running"}:
            return last_task

        time.sleep(0.05)

    status = last_task.get("status", "unknown") if last_task else "unknown"
    message = (
        last_task.get("message", "unavailable")
        if last_task
        else "unavailable"
    )

    raise AssertionError(
        f"Task did not complete within {timeout:.1f} seconds; "
        f"last status={status}; message={message}"
    )

def test_office_extraction_preserves_provenance(tmp_path):
    extractor = Extractor(settings(tmp_path))
    requirements = extractor.extract("requirements.xlsx", workbook_bytes(), "RAW_REQUIREMENT")
    assert len(requirements) == 2
    assert requirements[1].worksheet == "Orders"
    assert requirements[1].row == 2
    assert json.loads(requirements[1].content)["A"] == "REQ-1"
    designs = extractor.extract("design.docx", docx_bytes(), "DESIGN_DOCUMENT")
    assert "Orders design" in designs[0].content
    assert "Capability | Display order status" in designs[0].content


def test_legacy_xls_preserves_sheet_and_physical_row(tmp_path):
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("Legacy")
    sheet.write(0, 0, "ID")
    sheet.write(2, 0, "REQ-2")
    sheet.write(2, 1, "The system shall display order status.")
    stream = io.BytesIO()
    workbook.save(stream)
    artifacts = Extractor(settings(tmp_path)).extract(
        "legacy.xls", stream.getvalue(), "RAW_REQUIREMENT"
    )
    assert artifacts[1].worksheet == "Legacy"
    assert artifacts[1].row == 3
    assert json.loads(artifacts[1].content)["A"] == "REQ-2"


@pytest.mark.parametrize("filename", ["../escape.py", "/root/app.py", "C:\\app.py", "a/../../b.py"])
def test_archive_rejects_traversal(tmp_path, filename):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(filename, "code")
    with pytest.raises(ValueError, match="Unsafe"):
        Extractor(settings(tmp_path)).extract("code.zip", stream.getvalue())


def test_code_zip_streaming_applies_archive_limits_separately(tmp_path):
    config = settings(tmp_path, max_files=1, max_archive_files=2, max_archive_entries=2)
    archive_data = io.BytesIO()
    with zipfile.ZipFile(archive_data, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("src/orders.py", "#" * 100_000)
        archive.writestr("src/payments.py", "#" * 100_000)

    class TrackingZipStream(io.BytesIO):
        def __init__(self, value):
            super().__init__(value)
            self.unbounded_read_positions = []

        def read(self, size=-1):
            if size < 0:
                self.unbounded_read_positions.append(self.tell())
            return super().read(size)

    extractor = Extractor(config)
    source = TrackingZipStream(archive_data.getvalue())
    artifacts = list(extractor.iter_file(
        "source.zip", source, file_size=len(archive_data.getvalue()),
    ))
    artifacts.extend(extractor.iter_file(
        "extra.py", io.BytesIO(b"value = 1"), file_size=len(b"value = 1"),
    ))

    assert [item.filePath for item in artifacts] == [
        "src/orders.py", "src/payments.py", "extra.py",
    ]
    assert all(
        position >= len(archive_data.getvalue()) - 70_000
        for position in source.unbounded_read_positions
    )
    assert extractor.file_count == 3
    assert extractor.file_counts == {"archive": 2, "upload": 1}


def test_code_zip_rejects_entry_count_over_limit(tmp_path):
    archive_data = io.BytesIO()
    with zipfile.ZipFile(archive_data, "w") as archive:
        archive.writestr("one.py", "one = 1")
        archive.writestr("two.py", "two = 2")
    extractor = Extractor(settings(tmp_path, max_archive_entries=1))

    with pytest.raises(ValueError, match="too many entries"):
        extractor.extract("source.zip", archive_data.getvalue())


def test_secrets_and_unsupported_sources_are_not_analyzed(tmp_path):
    extractor = Extractor(settings(tmp_path))
    assert extractor.extract("private.key", b"private") == []
    assert extractor.extract("node_modules/lib/index.js", b"generated") == []
    assert extractor.extract("image.png", b"\x89PNG") == []
    assert extractor.unsupported_files == ["image.png"]


def test_empty_and_placeholder_input_rejected(tmp_path):
    extractor = Extractor(settings(tmp_path))
    with pytest.raises(ValueError, match="No readable"):
        extractor.artifact("CODE", "app.txt", "{{Codebase_Data}}")
    with pytest.raises(ValidationError):
        ManualStory(id="US-1", title=" ", description="story")
    assert settings(tmp_path, local_source_root="").local_source_root is None


def test_store_index_retrieval_and_persistence(tmp_path):
    store = Store(tmp_path / "test.sqlite3")
    artifacts = Extractor(settings(tmp_path)).extract("orders.py", b"def order_status(): return 'ready'")
    store.index("repo", artifacts)
    assert store.retrieve("repo", "order_status")[0].filePath == "orders.py"
    assert store.retrieve("different-repo", "order_status") == []
    store.index("repo", artifacts)
    assert len(Store(tmp_path / "test.sqlite3").retrieve("repo")) == 1
    task = store.create({"kind": "test"})
    store.recover()
    assert store.get(task["task_id"])["status"] == "failed"


def test_batched_index_keeps_previous_snapshot_when_source_read_fails(tmp_path):
    store = Store(tmp_path / "test.sqlite3")
    config = settings(tmp_path)
    original = Extractor(config).extract("original.py", b"def original(): pass")
    store.index("repo", original)
    replacement = Extractor(config).extract("replacement.py", b"def replacement(): pass")[0]

    def interrupted_source():
        yield replacement
        raise RuntimeError("synthetic source read failure")

    with pytest.raises(RuntimeError, match="source read failure"):
        store.index_batches("repo", interrupted_source(), batch_size=1)
    assert [item.filePath for item in store.retrieve("repo")] == ["original.py"]
    with store.connect() as db:
        assert db.execute(
            "SELECT count(*) FROM artifacts WHERE repo_id LIKE 'repo:staging:%'"
        ).fetchone()[0] == 0


def test_repository_limits_are_separate_and_failed_index_does_not_publish(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "first.py").write_text("first = 1", encoding="utf-8")
    (source / "second.py").write_text("second = 2", encoding="utf-8")
    config = Settings(
        _env_file=None, data_dir=tmp_path / "data", max_files=1,
        max_repository_files=2,
    )
    assert len(list(Extractor(config).iter_directory(source))) == 2
    limited_config = Settings(
        _env_file=None, data_dir=tmp_path / "limited-data",
        max_repository_files=1,
    )
    extractor = Extractor(limited_config)
    store = Store(config.data_dir / "tip.sqlite3")
    original = Extractor(config).extract("original.py", b"original = 1")
    store.index("repo", original)
    with pytest.raises(ValueError, match="Too many source files"):
        store.index_batches("repo", extractor.iter_directory(source), batch_size=1)
    assert [item.filePath for item in store.retrieve("repo")] == ["original.py"]

    byte_limited = Settings(
        _env_file=None, data_dir=tmp_path / "byte-data",
        max_repository_bytes=10, max_upload_bytes=100,
    )
    byte_source = tmp_path / "byte-source"
    byte_source.mkdir()
    (byte_source / "large.py").write_text("value = 123456", encoding="utf-8")
    byte_store = Store(byte_limited.data_dir / "tip.sqlite3")
    byte_store.index("repo", original)
    with pytest.raises(ValueError, match="Combined expanded artifacts"):
        byte_store.index_batches(
            "repo", Extractor(byte_limited).iter_directory(byte_source), batch_size=1,
        )
    assert [item.filePath for item in byte_store.retrieve("repo")] == ["original.py"]

    per_file_source = tmp_path / "per-file-source"
    per_file_source.mkdir()
    (per_file_source / "large.py").write_text("value = 123456", encoding="utf-8")
    (per_file_source / "small.py").write_text("x=1", encoding="utf-8")
    per_file_config = Settings(
        _env_file=None, data_dir=tmp_path / "per-file-data",
        max_repository_file_bytes=8,
    )
    per_file_extractor = Extractor(per_file_config)
    per_file_result = Store(per_file_config.data_dir / "tip.sqlite3").index_batches(
        "repo", per_file_extractor.iter_directory(per_file_source), batch_size=1,
    )
    assert per_file_result["files_indexed"] == 1
    assert per_file_extractor.unsupported_count == 1
    assert "large.py" in per_file_extractor.unsupported_files


def test_repository_stream_indexes_more_than_50000_files_with_bounded_retrieval(tmp_path):
    assert Settings(_env_file=None).max_repository_files == 1_000_000
    assert Settings(_env_file=None).max_repository_bytes == 10_000_000_000
    source = tmp_path / "large-source"
    source.mkdir()
    for index in range(50_000):
        (source / f"item-{index:05}.py").write_text(
            f"def item_{index:05}(): return {index}\n", encoding="utf-8",
        )
    (source / "zz-target.py").write_text(
        "def ultraspecificneedle(): return 'indexed'\n", encoding="utf-8",
    )
    config = Settings(
        _env_file=None, data_dir=tmp_path / "large-data",
        max_repository_files=60_000, max_repository_bytes=100_000_000,
        embedding_dimension=32,
    )
    index_path = config.data_dir / "tip.sqlite3"
    knowledge = LocalKnowledge(index_path, Embeddings("hash", "", 32))
    store = Store(
        index_path, knowledge=knowledge,
        max_knowledge_files=500, max_knowledge_characters=5_000_000,
    )
    extractor = Extractor(config)
    result = store.index_batches(
        "large-repo", extractor.iter_directory(source), batch_size=500,
    )
    assert result["files_indexed"] == 50_001
    assert store.index_stats("large-repo")[0] == 50_001
    assert any("Semantic chunk/vector indexing was skipped" in item for item in result["warnings"])
    retrieved = store.rag_retrieve("large-repo", "ultraspecificneedle", limit=1)
    assert [item.filePath for item in retrieved] == ["zz-target.py"]
    assert extractor.file_count == 50_001


def test_repository_extractor_enforces_configured_file_limit(tmp_path, monkeypatch):
    extractor = Extractor(Settings(
        _env_file=None, data_dir=tmp_path, max_repository_files=500_000,
    ))
    filenames = [f"ignored-{index:06}.bin" for index in range(500_001)]
    fake_stat = type("FakeStat", (), {"st_size": 1})()
    monkeypatch.setattr(
        "tip.extraction.os.walk",
        lambda root, **_kwargs: iter([(str(root), [], filenames)]),
    )
    monkeypatch.setattr(Path, "is_symlink", lambda _self: False)
    monkeypatch.setattr(Path, "stat", lambda _self, **_kwargs: fake_stat)
    monkeypatch.setattr(Path, "read_bytes", lambda _self: b"x")

    with pytest.raises(ValueError, match="Too many source files"):
        list(extractor.iter_directory(tmp_path))
    assert extractor.file_count == 500_001


def test_repository_character_limit_avoids_semantic_backfill(tmp_path):
    config = Settings(_env_file=None, data_dir=tmp_path, embedding_dimension=32)
    index_path = config.data_dir / "tip.sqlite3"
    knowledge = LocalKnowledge(index_path, Embeddings("hash", "", 32))
    store = Store(
        index_path, knowledge=knowledge, max_knowledge_files=10,
        max_knowledge_characters=5,
    )
    artifact = Extractor(config).extract("small.py", b"value = 7")
    result = store.index_batches("repo", iter(artifact), batch_size=1)
    assert any("Semantic chunk/vector indexing was skipped" in item for item in result["warnings"])
    assert [item.filePath for item in store.rag_retrieve("repo", "value", limit=1)] == ["small.py"]
    with store.connect() as db:
        assert db.execute(
            "SELECT count(*) FROM rag_snapshots WHERE scope='repo'"
        ).fetchone()[0] == 0


def test_model_body_and_fresh_signature(tmp_path, monkeypatch):
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    system_prompt = Path(__file__).parents[1] / "tip" / "prompts" / "system.txt"
    (prompt_dir / "system.txt").write_text(system_prompt.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr("tip.gateway.PROMPTS", prompt_dir)
    config = settings(
        tmp_path, gateway_api_key=SecretStr("test-key"),
        gateway_hmac_secret=SecretStr("test-secret"),
        gateway_signature_template="{api_key}{request_id}{timestamp}{body}",
        gateway_headers_json=SecretStr(json.dumps({
            "api-key": "{api_key}", "Timestamp": "{timestamp}",
            "Client-Request-Id": "{request_id}", "Authorization": "{signature}",
            "Accept": "application/json",
        })),
    )
    artifact = Extractor(config).extract("orders.py", b"def order_status(): pass")
    body = model_body("Orders", input_context(), artifact, config)
    data = json.loads(body)
    assert data["model"] == "azure-openai-5-2"
    assert data["max_tokens"] == 12000
    assert data["response_format"] == {"type": "json_object"}
    assert data["stream"] is False
    payload = json.loads(data["messages"][1]["content"].split("\n", 1)[1])
    assert payload["Codebase_Data"][0]["filePath"] == "orders.py"
    assert payload["Raw_Requirements_Data"] == []
    coverage = {
        "indexedCodeFiles": 10, "retrievedCodeFiles": 1,
        "retrievedCharacters": len(artifact[0].content),
        "selectionMethod": "focused indexed retrieval",
    }
    covered = json.loads(model_body(
        "Orders", input_context(), artifact, config, coverage,
    ))
    covered_payload = json.loads(covered["messages"][1]["content"].split("\n", 1)[1])
    assert covered_payload["Repository_Coverage"] == coverage
    headers = signed_headers(config, body)
    message = (
        "test-key" + headers["Client-Request-Id"] + headers["Timestamp"] + body.decode()
    ).encode()
    expected = base64.b64encode(hmac.new(b"test-secret", message, hashlib.sha256).digest()).decode()
    assert headers["Authorization"] == expected
    assert headers["api-key"] == "test-key"
    assert headers["Accept"] == "application/json"
    assert signed_headers(config, body)["Client-Request-Id"] != headers["Client-Request-Id"]


def test_gateway_known_headers_require_credentials(tmp_path):
    config = settings(tmp_path)
    assert not config.gateway_auth_configured
    with pytest.raises(ValueError, match="CONSUMER_KEY"):
        signed_headers(config, b'{"test":true}')


def test_postman_consumer_key_is_api_key_and_signed_body_is_exact(tmp_path, monkeypatch):
    monkeypatch.setattr("tip.gateway.time.time", lambda: 1793876400.123)
    monkeypatch.setattr("tip.gateway.uuid.uuid4", lambda: "211a7807-34ed-4dbd-877f-f9da095b0790")
    config = settings(
        tmp_path, gateway_app_consumer_key=SecretStr("synthetic-key"),
        gateway_hmac_secret=SecretStr("synthetic-secret"),
    )
    body = '{"messages":[{"role":"user","content":"café"}]}'.encode("utf-8")
    headers = signed_headers(config, body)
    expected = base64.b64encode(hmac.new(
        b"synthetic-secret",
        b"synthetic-key211a7807-34ed-4dbd-877f-f9da095b07901793876400123" + body,
        hashlib.sha256,
    ).digest()).decode()
    assert expected == "nkUFtS23uLh+v9i9BTRP5PfAyqIyygct/fx/ajJLUhI="
    assert headers["api-key"] == "synthetic-key"
    assert headers["Timestamp"] == "1793876400123"
    assert headers["Authorization"] == expected
    assert config.gateway_auth_configured
    assert signed_headers(config, body + b" ")["Authorization"] != expected
    assert signed_headers(config, b"")["Authorization"] != expected
    conflict = settings(
        tmp_path, gateway_app_consumer_key=SecretStr("one"),
        gateway_api_key=SecretStr("two"), gateway_hmac_secret=SecretStr("secret"),
    )
    with pytest.raises(ValueError, match="must match"):
        signed_headers(conflict, body)


def test_model_context_limit_does_not_silently_truncate(tmp_path):
    config = settings(tmp_path, max_model_characters=100)
    artifact = Extractor(config).extract("orders.py", b"def order_status(): pass")
    with pytest.raises(ValueError, match="no evidence was silently truncated"):
        model_body("Orders", input_context(), artifact, config)


def test_gateway_http_contract_and_truncated_output(tmp_path, monkeypatch):
    config = settings(
        tmp_path, gateway_url="https://gateway.example/chat/completions",
        gateway_app_consumer_key=SecretStr("synthetic-key"),
        gateway_hmac_secret=SecretStr("synthetic-secret"),
    )
    artifacts = Extractor(config).extract("orders.py", b"def order_status(): pass")
    expected = sample_result("Orders", input_context(), artifacts)
    seen = []

    def handle(request):
        assert str(request.url) == "https://gateway.example/chat/completions"
        assert request.headers["api-key"] == "synthetic-key"
        raw_signature = (
            "synthetic-key" + request.headers["Client-Request-Id"]
            + request.headers["Timestamp"]
        ).encode() + request.content
        assert request.headers["Authorization"] == base64.b64encode(
            hmac.new(b"synthetic-secret", raw_signature, hashlib.sha256).digest()
        ).decode()
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "stop", "message": {"content": expected.model_dump_json()}}]
        })

    client_type = httpx.Client
    monkeypatch.setattr("tip.gateway.httpx.Client",
                        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs))
    actual = Gateway(config).analyze("Orders", input_context(), artifacts)
    assert actual == expected
    assert seen[0]["messages"][0]["role"] == "system"

    def truncated(request):
        return httpx.Response(200, json={"choices": [{"finish_reason": "length"}]})

    monkeypatch.setattr("tip.gateway.httpx.Client",
                        lambda **kwargs: client_type(transport=httpx.MockTransport(truncated), **kwargs))
    with pytest.raises(ValueError, match="truncated"):
        Gateway(config).analyze("Orders", input_context(), artifacts)

    def timeout(request):
        return httpx.Response(504)

    monkeypatch.setattr("tip.gateway.httpx.Client",
                        lambda **kwargs: client_type(transport=httpx.MockTransport(timeout), **kwargs))
    with pytest.raises(GatewayError, match="HTTP 504") as error:
        Gateway(config).analyze("Orders", input_context(), artifacts)
    assert error.value.status_code == 504

    def rate_limited(request):
        return httpx.Response(
            429,
            headers={"Retry-After": "2"},
            json={"error": {"code": "rate_limit_exceeded"}},
        )

    monkeypatch.setattr("tip.gateway.httpx.Client",
                        lambda **kwargs: client_type(transport=httpx.MockTransport(rate_limited), **kwargs))
    with pytest.raises(GatewayError, match="HTTP 429") as error:
        Gateway(config).analyze("Orders", input_context(), artifacts)
    assert error.value.status_code == 429
    assert error.value.retry_after == 2
    assert error.value.error_code == "rate_limit_exceeded"

    def rate_limited_milliseconds(request):
        return httpx.Response(
            429,
            headers={"retry-after-ms": "1500"},
            json={"error": {"type": "insufficient_quota"}},
        )

    monkeypatch.setattr("tip.gateway.httpx.Client",
                        lambda **kwargs: client_type(transport=httpx.MockTransport(rate_limited_milliseconds), **kwargs))
    with pytest.raises(GatewayError, match="HTTP 429") as error:
        Gateway(config).analyze("Orders", input_context(), artifacts)
    assert error.value.retry_after == 1.5
    assert error.value.error_code == "insufficient_quota"


def test_validation_rejects_unknown_evidence_and_false_implementation(tmp_path):
    extractor = Extractor(settings(tmp_path))
    artifact = extractor.story(ManualStory(
        id="US-1", title="Order status", description="The system shall display order status."
    ))
    result = sample_result("Orders", input_context(), [artifact])
    validate_result(result, [artifact], input_context(), "Orders")
    result.highLevelRequirements[0].implementationEvidenceStatus = "IMPLEMENTATION_EVIDENCED"
    with pytest.raises(ValueError, match="without cited code"):
        validate_result(result, [artifact], input_context(), "Orders")


@pytest.mark.parametrize("directive", [
    "%%{init: {securityLevel: 'loose'}}%%",
    'click A "https://example.com"',
    "A --> B: https://example.com",
    "A --> B: <script>alert(1)</script>",
])
def test_mermaid_blocks_external_content(directive):
    with pytest.raises(ValueError, match="not allowed"):
        validate_mermaid(f"flowchart LR\n  A --> B\n{directive}")


def test_mermaid_validation_requires_supported_declaration():
    with pytest.raises(ValueError, match="supported diagram"):
        validate_mermaid("graphical output")


def test_mermaid_rendering_reports_missing_node(tmp_path, monkeypatch):
    artifacts = Extractor(settings(tmp_path)).extract("orders.py", b"def order_status(): pass")
    result = sample_result("Orders", input_context(), artifacts, with_diagram=True)
    monkeypatch.setattr("tip.documents.shutil.which", lambda _: None)

    with pytest.raises(ValueError, match="Node.js"):
        render_diagram(result.umlDiagrams.componentDiagram)


def test_missing_mermaid_script_has_actionable_configuration_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tip.documents._renderer_paths",
        lambda: (tmp_path, tmp_path / "render-mermaid.mjs"),
    )
    monkeypatch.setattr("tip.documents.shutil.which", lambda _: "/usr/bin/node")

    issue = mermaid_renderer_issue()

    assert issue is not None
    assert "missing from backend/tip" in issue
    assert "Sync the current backend files" in issue


def test_mermaid_renderer_error_reports_native_panic_cause(tmp_path, monkeypatch):
    artifacts = Extractor(settings(tmp_path)).extract("orders.py", b"def order_status(): pass")
    result = sample_result("Orders", input_context(), artifacts, with_diagram=True)
    monkeypatch.setattr("tip.documents.mermaid_renderer_issue", lambda: None)
    monkeypatch.setattr("tip.documents.shutil.which", lambda _: "/usr/bin/node")
    monkeypatch.setattr(
        "tip.documents.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["node"], returncode=134, stdout=b"",
            stderr=(
                b"thread '<unnamed>' panicked at resvg/src/geom.rs:27:61:\n"
                b"called `Option::unwrap()` on a `None` value\n"
                b"note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace\n"
            ),
        ),
    )

    with pytest.raises(ValueError) as error:
        render_diagram(result.umlDiagrams.componentDiagram)

    assert "Option::unwrap()" in str(error.value)
    assert "RUST_BACKTRACE" not in str(error.value)


def test_missing_mermaid_renderer_rejects_generated_diagrams(tmp_path, monkeypatch):
    artifacts = Extractor(settings(tmp_path)).extract("orders.py", b"def order_status(): pass")
    result = sample_result("Orders", input_context(), artifacts, with_diagram=True)
    monkeypatch.setattr("tip.documents.shutil.which", lambda _: None)

    with pytest.raises(ValueError, match="Local Mermaid rendering is unavailable"):
        render_generated_diagrams(result)
    with pytest.raises(ValueError, match="has no rendered PNG"):
        create_document(result, {"componentDiagram": None})
    with pytest.raises(ValueError, match="has no rendered PNG"):
        create_business_document(result, {"componentDiagram": None})


def test_business_document_uses_stakeholder_format_without_inventing_context(tmp_path):
    artifacts = Extractor(settings(tmp_path)).extract(
        "orders.py", b"def order_status(): pass",
    )
    result = sample_result("Orders", input_context(), artifacts, with_diagram=True)
    document = Document(io.BytesIO(create_business_document(
        result, {"componentDiagram": TEST_PNG},
    )))
    text = "\n".join(
        [paragraph.text for paragraph in document.paragraphs]
        + [
            cell.text for table in document.tables
            for row in table.rows for cell in row.cells
        ]
    )

    for section in (
        "Functional Requirements Specification (FRS)",
        "Document Use and Audience",
        "1. Executive Summary",
        "2. Business Problem and Objectives",
        "2.1 Business Objectives",
        "3. Scope",
        "3.1 Current State and Future State",
        "4. Business Capabilities, Processes, Modules, and Interfaces",
        "4.1 Business Process Overview",
        "4.2 Modules, Components, and Interfaces",
        "4.3 UML Process and System Diagrams",
        "5. Business Rules and Policy Considerations",
        "6. Audience, Stakeholders, and Responsibilities",
        "7. Benefits and Risks",
        "7.1 Business Risks and Controls",
        "8. Success Measures",
        "9. Acceptance Criteria",
        "10. Dependencies and Open Decisions",
        "11. Requirements Matrix and Details",
        "11.1 Requirements Matrix",
        "11.2 Detailed Requirements",
        "12. Evidence Classification and Traceability",
        "Appendix A: Analysis Coverage",
        "13. Review and Approval",
        "Synthetic order-status component",
    ):
        assert section in text
    assert "Implementation-derived; not approved business intent" in text
    assert "The system will display order status." in text
    assert "No Jira user stories or raw business requirements were supplied" in text
    assert "orders.py" not in text


def test_missing_model_uml_gets_source_component_map_in_both_reports(tmp_path, monkeypatch):
    artifacts = Extractor(settings(tmp_path)).extract(
        "src/orders.py", b"def order_status(): pass",
    )
    result = sample_result("Orders", input_context(), artifacts)
    result.analysisScope.analyzedCodeFiles = 1

    assert ensure_source_component_diagram(result)
    diagram = result.umlDiagrams.componentDiagram
    assert diagram.generated
    assert "src/orders.py" in diagram.mermaid
    assert "analysis covered 1 eligible code file" in diagram.description
    assert diagram.sourceEvidence[0].filePath == "src/orders.py"
    assert any("source component diagram" in warning for warning in result.warnings)
    monkeypatch.setattr("tip.documents.render_diagram", lambda _: TEST_PNG)
    rendered = render_generated_diagrams(result)

    documents = [
        Document(io.BytesIO(create_document(result, rendered))),
        Document(io.BytesIO(create_business_document(result, rendered))),
    ]
    texts = [
        "\n".join(
            [paragraph.text for paragraph in document.paragraphs]
            + [
                cell.text for table in document.tables
                for row in table.rows for cell in row.cells
            ]
        )
        for document in documents
    ]
    assert all("Source Component Diagram" in text for text in texts)
    assert "src/orders.py" in texts[0]
    assert "src/orders.py" not in texts[1]


def test_code_analysis_is_rejected_without_mermaid_renderer(tmp_path, monkeypatch):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))
    monkeypatch.setattr("tip.documents.shutil.which", lambda _: None)
    with TestClient(app) as client:
        configuration = client.get("/api/v1/configuration").json()
        assert configuration["diagram_renderer_configured"] is False
        assert "Node.js" in configuration["diagram_renderer_issue"]
        response = client.post(
            "/api/v1/analysis",
            data={"options": '{"target_application":"Orders"}'},
            files={"code_files": ("orders.py", b"def order_status(): pass", "text/plain")},
        )
        assert response.status_code == 503
        assert "requires embedded UML images" in response.json()["detail"]
        assert "Node.js" in response.json()["detail"]
        assert client.get("/api/v1/tasks").json()["total_count"] == 0


def test_mermaid_rendering_and_word_embedding(tmp_path):
    if not mermaid_renderer_configured():
        pytest.skip("Install Node.js and run npm install in frontend to exercise Mermaid rendering")
    artifacts = Extractor(settings(tmp_path)).extract("orders.py", b"def order_status(): pass")
    result = sample_result("Orders", input_context(), artifacts, with_diagram=True)
    result.umlDiagrams.classDiagram = result.umlDiagrams.componentDiagram.model_copy(update={
        "title": "Unsupported class diagram", "mermaid": "unsupportedDiagram",
    })
    validate_result(result, artifacts, input_context(), "Orders")
    assert not result.umlDiagrams.classDiagram.generated
    assert INVALID_DIAGRAM_WARNING in result.warnings
    rendered = render_generated_diagrams(result)
    assert rendered["componentDiagram"].startswith(b"\x89PNG")
    data = create_document(result, rendered)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert any(
            name.startswith("word/media/") and name.endswith(".png")
            for name in archive.namelist()
        )
        xml = archive.read("word/document.xml").decode()
        assert "flowchart LR" not in xml
        assert "<w:drawing>" in xml
        assert "Graphical rendering is unavailable" not in xml
        assert "Draft for Human Validation" in xml
    business_data = create_business_document(result, rendered)
    with zipfile.ZipFile(io.BytesIO(business_data)) as archive:
        assert any(
            name.startswith("word/media/") and name.endswith(".png")
            for name in archive.namelist()
        )
        xml = archive.read("word/document.xml").decode()
        assert "Functional Requirements Specification (FRS)" in xml
        assert "<w:drawing>" in xml
        assert "Graphical rendering is unavailable" not in xml
        assert "How to read it" in xml

def test_labeled_class_diagram_renders_without_native_resvg_panic(
    tmp_path,
    monkeypatch,
):
    if not mermaid_renderer_configured():
        pytest.skip(
            "Install Node.js and run npm install in frontend "
            "to exercise Mermaid rendering"
        )

    artifacts = Extractor(settings(tmp_path)).extract(
        "glreport.py",
        b"class GLReportService: pass\nclass ReportBuilder: pass",
    )

    result = sample_result(
        "GL Report Generation",
        input_context(),
        artifacts,
    )

    source = (
        "classDiagram\n"
        "class GLReportService {\n"
        "  +generate(report: dict): bytes\n"
        "}\n"
        "class ReportBuilder\n"
        "GLReportService --> ReportBuilder : creates"
    )

    result.umlDiagrams.classDiagram = (
        result.umlDiagrams.classDiagram.model_copy(
            update={
                "generated": True,
                "title": "Class Diagram - GL Report Generation (glreport package)",
                "description": "Test class diagram with a labeled relationship.",
                "mermaid": source,
                "sourceEvidence": (
                    result.highLevelRequirements[0].sourceEvidence
                ),
                "reason": "",
            }
        )
    )

    rendered_sources = []
    actual_render_diagram = render_diagram

    def capture_render_source(diagram):
        rendered_sources.append(diagram.mermaid)
        return actual_render_diagram(diagram)

    monkeypatch.setattr(
        "tip.documents.render_diagram",
        capture_render_source,
    )

    rendered = render_generated_diagrams(result)

    assert rendered["classDiagram"].startswith(
        b"\x89PNG\r\n\x1a\n"
    )

    assert "GLReportService --> ReportBuilder" in rendered_sources[0]
    assert ": creates" not in rendered_sources[0]
    assert "+generate(report: dict): bytes" not in rendered_sources[0]
    assert "class GLReportService" in rendered_sources[0]

    assert result.umlDiagrams.classDiagram.mermaid == source

    assert any(
        "Class member details and relationship captions were omitted"
        in item
        for item in result.warnings
    )

    assert zipfile.is_zipfile(
        io.BytesIO(create_document(result, rendered))
    )

    assert zipfile.is_zipfile(
        io.BytesIO(create_business_document(result, rendered))
    )


def test_component_diagram_retries_with_safe_mermaid_source(
    tmp_path,
    monkeypatch,
):
    artifacts = Extractor(settings(tmp_path)).extract(
        "server.py",
        b"def delegate_to_rag(): pass\n",
    )

    result = sample_result(
        "Local RAG Server",
        input_context(),
        artifacts,
    )

    source = (
        "flowchart LR\n"
        '  ENTRY["Local RAG Server<br/>Entrypoint"]\n'
        '  SERVICE["Delegation <b>Service</b>"]\n'
        "  ENTRY -->|delegates incoming request| SERVICE\n"
    )

    diagram = result.umlDiagrams.componentDiagram.model_copy(
        update={
            "generated": True,
            "title": (
                "Component View - "
                "Local RAG Server Entrypoint Delegation"
            ),
            "description": "Local RAG delegation flow.",
            "mermaid": source,
            "sourceEvidence": (
                result.highLevelRequirements[0].sourceEvidence
            ),
            "reason": "",
        }
    )

    result.umlDiagrams.componentDiagram = diagram

    attempts = []

    def fake_render(candidate):
        attempts.append(candidate.mermaid)

        if len(attempts) == 1:
            raise ValueError(
                "Local Mermaid rendering failed: "
                "thread '<unnamed>' panicked at "
                "resvg/src/geom.rs:27:61; "
                "called `Option::unwrap()` on a `None` value"
            )

        return b"\x89PNG\r\n\x1a\nsafe-render"

    monkeypatch.setattr(
        "tip.documents.render_diagram",
        fake_render,
    )

    rendered = render_generated_diagrams(result)

    assert rendered["componentDiagram"].startswith(
        b"\x89PNG\r\n\x1a\n"
    )

    assert len(attempts) == 2

    # First attempt contains the original Mermaid.
    assert "<br/>" in attempts[0]
    assert "<b>" in attempts[0]
    assert "|delegates incoming request|" in attempts[0]

    # Retry uses the renderer-safe Mermaid source.
    assert "<br/>" not in attempts[1]
    assert "<b>" not in attempts[1]
    assert "|delegates incoming request|" not in attempts[1]

def test_jira_integration_extracts_adf_and_custom_acceptance(tmp_path, monkeypatch):
    config = settings(
        tmp_path, jira_base_url="https://jira.example", jira_email="test@example.com",
        jira_token=SecretStr("test-token"), jira_acceptance_field="customfield_10001",
    )
    client_type = httpx.Client

    def handle(request):
        assert request.url.path == "/rest/api/3/issue/TIP-1"
        assert request.headers["authorization"].startswith("Basic ")
        return httpx.Response(200, json={
            "key": "TIP-1", "fields": {
                "summary": "Display order status",
                "description": {"type": "doc", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Status is visible"}]}
                ]},
                "customfield_10001": "An order status is visible",
            },
        })
    monkeypatch.setattr("tip.extraction.httpx.Client",
                        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs))
    artifacts = jira_stories(["TIP-1"], config, Extractor(config))
    assert artifacts[0].externalId == "TIP-1"
    assert json.loads(artifacts[0].content)["acceptanceCriteria"] == "An order status is visible"


def test_server_paths_and_repository_hosts_are_restricted(tmp_path):
    config = settings(tmp_path)
    with pytest.raises(ValueError, match="disabled"):
        with source_directory(config, local_path=str(tmp_path)):
            pass
    with pytest.raises(ValueError, match="allowed host"):
        with source_directory(config, repo_url="https://unapproved.example/repo"):
            pass


def test_self_hosted_repository_host_can_be_explicitly_allowlisted(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "TIP_REPOSITORY_HOSTS",
        "github.com,gitlab.com,bitbucket.org,gitlab.onefiserv.net",
    )
    config = Settings(_env_file=None, data_dir=tmp_path)

    def clone(command, **_kwargs):
        Path(command[-1]).mkdir()
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("tip.extraction.subprocess.run", clone)
    with source_directory(
        config,
        repo_url="https://gitlab.onefiserv.net/F5P12YO/fsams-domestic",
        branch="master",
    ) as root:
        assert root.is_dir()


def test_company_gitlab_repository_host_is_allowed_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("TIP_REPOSITORY_HOSTS", raising=False)
    config = Settings(_env_file=None, data_dir=tmp_path)

    def clone(command, **_kwargs):
        Path(command[-1]).mkdir()
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("tip.extraction.subprocess.run", clone)
    with source_directory(
        config,
        repo_url=(
            "https://gitlab.onefiserv.net/na/gbs/platform-product-risk-ops/"
            "global-settlement-balancing/setops/FSAMS/fsams-domestic"
        ),
    ) as root:
        assert root.is_dir()


def test_repository_subdirectory_uses_blobless_sparse_checkout(tmp_path, monkeypatch):
    config = settings(tmp_path)
    calls = []

    def git(command, **kwargs):
        calls.append((command, kwargs))
        if "clone" in command:
            Path(command[-1]).mkdir()
        elif command[3] == "checkout":
            (Path(command[2]) / "packages" / "api").mkdir(parents=True)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("tip.extraction.subprocess.run", git)
    with source_directory(
        config,
        repo_url="https://github.com/acme/project.git",
        branch="main",
        selected_path="packages/api",
    ) as root:
        assert root.name == "api"
        assert root.is_dir()

    clone_command = calls[0][0]
    assert "--depth=1" in clone_command
    assert "--single-branch" in clone_command
    assert "--filter=blob:none" in clone_command
    assert "--no-checkout" in clone_command
    assert clone_command[clone_command.index("--branch") + 1] == "main"
    assert any("sparse-checkout" in command for command, _ in calls)
    assert all(
        kwargs["timeout"] == config.repository_clone_timeout_seconds
        for _, kwargs in calls
    )


def test_full_analysis_upload_poll_download_and_reload(tmp_path, monkeypatch):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))
    monkeypatch.setattr("tip.app.mermaid_renderer_configured", lambda: True)
    monkeypatch.setattr("tip.app.mermaid_renderer_issue", lambda: None)
    monkeypatch.setattr("tip.documents.render_diagram", lambda _: TEST_PNG)
    seen = []

    class TestGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            seen.extend(artifacts)
            return sample_result(target, context, artifacts)
    app.state.manager.gateway = TestGateway()
    with TestClient(app) as client:
        configuration = client.get("/api/v1/configuration").json()
        assert configuration["persistence_backend"] == "SQLite"
        assert configuration["persistence_configured"] is True
        assert configuration["max_upload_bytes"] == 5_000_000_000
        assert configuration["max_extracted_bytes"] == 10_000_000_000
        assert configuration["max_archive_files"] == 50_000
        assert configuration["max_archive_entries"] == 100_000
        assert configuration["max_repository_files"] == 1_000_000
        assert configuration["max_repository_bytes"] == 10_000_000_000
        assert configuration["max_repository_file_bytes"] == 100_000_000
        assert configuration["repository_clone_timeout_seconds"] == 1800
        assert configuration["analysis_batch_concurrency"] == 2
        assert configuration["diagram_renderer_configured"] is True
        assert configuration["diagram_renderer_issue"] is None
        assert "neo4j_configured" not in configuration
        options = {
            "target_application": "Orders", "manual_stories": [{
                "id": "US-1", "title": "Order status",
                "description": "The system shall display order status.",
            }],
        }
        response = client.post("/api/v1/analysis", data={"options": json.dumps(options)}, files=[
            ("code_files", ("orders.py", b"def order_status(): return 'ready'", "text/plain")),
            ("design_files", ("design.docx", docx_bytes(), "application/octet-stream")),
            ("requirements_files", ("requirements.xlsx", workbook_bytes(), "application/octet-stream")),
        ])
        assert response.status_code == 202, response.text
        task_id = response.json()["task_id"]
        task = wait_task(client, task_id)
        assert task["status"] == "success", task.get("error")
        with app.state.store.connect() as db:
            assert db.execute(
                "SELECT count(*) FROM analysis_records WHERE task_id=?", (task_id,)
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM requirements WHERE task_id=?", (task_id,)
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM evidence WHERE task_id=?", (task_id,)
            ).fetchone()[0] == len(task["result"]["analysis"]["highLevelRequirements"][0]["sourceEvidence"])
            assert db.execute(
                "SELECT count(*) FROM requirement_evidence WHERE task_id=?", (task_id,)
            ).fetchone()[0] == len(task["result"]["analysis"]["highLevelRequirements"][0]["sourceEvidence"])
            assert db.execute(
                "SELECT evidence_description FROM requirement_evidence WHERE task_id=? LIMIT 1",
                (task_id,),
            ).fetchone()[0] == "Synthetic test evidence for displaying order status."
        assert {a.sourceType for a in seen} == {
            "CODE", "DESIGN_DOCUMENT", "JIRA_USER_STORY", "RAW_REQUIREMENT",
        }
        analysis = client.get(f"/api/v1/tasks/{task_id}/analysis")
        assert analysis.status_code == 200
        analysis_result = analysis.json()
        assert analysis_result["umlDiagrams"]["componentDiagram"]["generated"]
        assert any("source component diagram" in warning for warning in analysis_result["warnings"])
        assert "attachment" in analysis.headers["content-disposition"]
        assert f"TIP-analysis-{task_id}.json" in analysis.headers["content-disposition"]
        document = client.get(f"/api/v1/tasks/{task_id}/document")
        assert document.status_code == 200
        assert zipfile.is_zipfile(io.BytesIO(document.content))
        assert "attachment" in document.headers["content-disposition"]
        business_document = client.get(
            f"/api/v1/tasks/{task_id}/business-document",
        )
        assert business_document.status_code == 200
        for content, includes_source_paths in (
            (document.content, True), (business_document.content, False),
        ):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                report_xml = archive.read("word/document.xml").decode()
                assert any(
                    name.startswith("word/media/") and name.endswith(".png")
                    for name in archive.namelist()
                )
                assert "<w:drawing>" in report_xml
            assert "Source Component Diagram" in report_xml
            assert "Graphical rendering is unavailable" not in report_xml
            assert ("orders.py" in report_xml) is includes_source_paths
        indexed_repo = task["result"]["repo_id"]
        related = client.get("/api/v1/graph/related",
                             params={"repoId": indexed_repo, "query": "order_status"})
        assert related.json()["nodes"][0]["path"] == "orders.py"
        context = client.get("/api/v1/context/pack", params={"repoId": indexed_repo, "budget": 100})
        assert context.json()["budget_used"] <= 100
        impact = client.get("/api/v1/graph/impact", params={"repoId": indexed_repo, "file": "orders.py"})
        assert impact.status_code == 200
        assert impact.json()["backend"] == "sqlite"        
        assert impact.json()["nodes"] == []
        assert client.get("/api/v1/metrics").status_code == 200
    new_app = create_app(settings(tmp_path))
    with TestClient(new_app) as client:
        assert client.get(f"/api/v1/tasks/{task_id}/document").content == document.content
        assert client.get("/api/v1/tasks").json()["total_count"] == 1


def test_browser_upload_limit_is_enforced_without_queuing(tmp_path):
    app = create_app(settings(
        tmp_path, max_upload_bytes=3,
        gateway_url="https://synthetic.example/completions",
    ))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            data={"options": json.dumps({"target_application": "Orders"})},
            files={"code_files": ("orders.py", b"four", "text/plain")},
        )

        assert response.status_code == 413
        assert "configured size limit" in response.json()["detail"]
        assert client.get("/api/v1/tasks").json()["total_count"] == 0

def test_large_repository_analysis_batches_every_eligible_file(tmp_path):
    source_root = tmp_path / "allowed"
    repository = source_root / "orders"
    repository.mkdir(parents=True)

    (repository / "orders.py").write_text(
        "def order_status(): return 'ready'\n",
        encoding="utf-8",
    )
    (repository / "payments.py").write_text(
        "def authorize_payment(): return True\n",
        encoding="utf-8",
    )
    (repository / "inventory.py").write_text(
        "def item_count(): return 1\n",
        encoding="utf-8",
    )

    app = create_app(
        Settings(
            _env_file=None,
            data_dir=tmp_path / "data",
            local_source_root=source_root,
            graph_backend="sqlite",
            gateway_url="https://synthetic.example/completions",
            max_analysis_files=1,
            analysis_batch_files=1,
        )
    )

    seen = {
        "paths": [],
        "coverage": [],
        "content_lengths": [],
    }

    class CoverageGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            code_artifacts = [
                artifact
                for artifact in artifacts
                if artifact.sourceType == "CODE"
            ]

            seen["paths"].extend(
                artifact.filePath
                for artifact in code_artifacts
            )

            seen["content_lengths"].extend(
                len(artifact.content)
                for artifact in code_artifacts
            )

            seen["coverage"].append(coverage)

            return sample_result(
                target,
                context,
                artifacts,
            )

    app.state.manager.gateway = CoverageGateway()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            data={
                "options": json.dumps(
                    {
                        "target_application": "Orders",
                        "code_source": "local",
                        "local_path": str(repository),
                        "focus": "order status",
                    }
                )
            },
        )

        assert response.status_code == 202, response.text

        task = wait_task(
            client,
            response.json()["task_id"],
        )

        assert task["status"] == "success", task.get("error")

        assert sorted(seen["paths"]) == [
            "inventory.py",
            "orders.py",
            "payments.py",
        ]

        actual_coverage = sorted(
            (
                item["indexedCodeFiles"],
                item["retrievedCodeFiles"],
                item["retrievedCharacters"],
            )
            for item in seen["coverage"]
        )

        expected_coverage = sorted(
            (
                3,
                1,
                content_length,
            )
            for content_length in seen["content_lengths"]
        )

        assert actual_coverage == expected_coverage

        assert sorted(
            item["batchRequestNumber"]
            for item in seen["coverage"]
        ) == [1, 2, 3]

        assert task["result"]["files_indexed"] == 3
        assert task["result"]["files_analyzed"] == 3

        assert task["result"]["repository_coverage"] == {
            "indexedCodeFiles": 3,
            "retrievedCodeFiles": 3,
            "retrievedCharacters": sum(
                seen["content_lengths"]
            ),
            "selectionMethod": (
                "all-file bounded batch analysis"
            ),
            "analysisBatchCount": 3,
        }

        assert len(
            task["result"]["analysis"]["codebaseInventory"]
        ) == 3

        assert (
            task["result"]["analysis"][
                "analysisScope"
            ]["analyzedCodeFiles"]
            == 3
        )

        assert not any(
            "remaining files were not analyzed" in warning
            for warning in task["result"]["analysis"]["warnings"]
        )

def test_uploaded_zip_batches_every_readable_member(tmp_path):
    app = create_app(Settings(
        _env_file=None, data_dir=tmp_path, graph_backend="sqlite",
        gateway_url="https://synthetic.example/completions",
        analysis_batch_files=1,
    ))
    seen = []

    class ArchiveGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            seen.extend(item.filePath for item in artifacts if item.sourceType == "CODE")
            return sample_result(target, context, artifacts)

    app.state.manager.gateway = ArchiveGateway()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("src/orders.py", "def order_status(): return 'ready'\n")
        bundle.writestr("src/payments.py", "def authorize(): return True\n")
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            data={"options": json.dumps({"target_application": "Orders"})},
            files={"code_files": ("source.zip", archive.getvalue(), "application/zip")},
        )
        assert response.status_code == 202, response.text
        task = wait_task(client, response.json()["task_id"])
        assert task["status"] == "success", task.get("error")
        assert seen == ["src/orders.py", "src/payments.py"]
        assert task["result"]["files_analyzed"] == 2
        assert task["result"]["repository_coverage"]["analysisBatchCount"] == 2
        assert task["result"]["analysis"]["inputContext"]["inputType"] == "ARCHIVE"


def test_large_artifact_is_split_with_original_line_numbers(tmp_path):
    app = create_app(Settings(
        _env_file=None, data_dir=tmp_path, graph_backend="sqlite",
        gateway_url="https://synthetic.example/completions",
        analysis_batch_characters=12,
    ))
    content = "a = 1\nb = 2\nc = 3\nd = 4\n"
    offsets = []

    class ChunkGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            artifact = next(item for item in artifacts if item.sourceType == "CODE")
            offsets.append(artifact.lineOffset)
            result = sample_result(target, context, artifacts)
            for requirement in result.highLevelRequirements:
                for evidence in requirement.sourceEvidence:
                    evidence.lineStart = artifact.lineOffset + 1
                    evidence.lineEnd = artifact.lineOffset + 1
            for trace in result.requirementsToDesignTraceability:
                trace.sourceEvidence = result.highLevelRequirements[0].sourceEvidence
            return result

    app.state.manager.gateway = ChunkGateway()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            data={"options": '{"target_application":"Orders"}'},
            files={"code_files": ("src/orders.py", content.encode(), "text/plain")},
        )
        assert response.status_code == 202
        task = wait_task(client, response.json()["task_id"])
        assert task["status"] == "success", task.get("error")
        assert sorted(offsets) == [0, 2]
        assert task["result"]["files_analyzed"] == 1
        assert task["result"]["repository_coverage"]["analysisBatchCount"] == 2
        evidence = task["result"]["analysis"]["highLevelRequirements"][0]["sourceEvidence"]
        assert [item["lineStart"] for item in evidence] == [1, 3]


def test_gateway_504_splits_batches_and_merges_all_results(tmp_path):
    app = create_app(Settings(
        _env_file=None, data_dir=tmp_path, graph_backend="sqlite",
        gateway_url="https://synthetic.example/completions",
        analysis_batch_files=4, analysis_batch_characters=10_000,
    ))
    calls = []

    class SplitGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            paths = [item.filePath for item in artifacts if item.sourceType == "CODE"]
            calls.append(paths)
            if len(artifacts) > 1:
                raise GatewayError("AI gateway returned HTTP 504", status_code=504)
            return sample_result(target, context, artifacts)

    app.state.manager.gateway = SplitGateway()
    files = [
        ("code_files", (f"src/{name}.py", f"def {name}(): pass".encode(), "text/plain"))
        for name in ("accounts", "orders", "payments", "users")
    ]
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            data={"options": json.dumps({"target_application": "TIP"})},
            files=files,
        )
        assert response.status_code == 202, response.text
        task = wait_task(client, response.json()["task_id"])
        assert task["status"] == "success", task.get("error")
        assert sorted(map(tuple, calls)) == sorted((
            ("src/accounts.py", "src/orders.py", "src/payments.py", "src/users.py"),
            ("src/accounts.py", "src/orders.py"),
            ("src/payments.py", "src/users.py"),
            ("src/accounts.py",),
            ("src/orders.py",),
            ("src/payments.py",),
            ("src/users.py",),
        ))
        assert task["result"]["files_analyzed"] == 4
        assert task["result"]["repository_coverage"]["analysisBatchCount"] == 4
        analysis = task["result"]["analysis"]
        assert len(analysis["codebaseInventory"]) == 4
        assert len(analysis["highLevelRequirements"][0]["sourceEvidence"]) == 4


def test_gateway_504_splits_a_single_large_file_content_chunk(tmp_path):
    app = create_app(Settings(
        _env_file=None, data_dir=tmp_path, graph_backend="sqlite",
        gateway_url="https://synthetic.example/completions",
        analysis_batch_characters=5_000,
        analysis_batch_concurrency=2,
    ))
    seen_lengths = []
    active = 0
    max_active = 0
    active_lock = threading.Lock()
    two_calls_started = threading.Event()

    class ChunkSplitGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            nonlocal active, max_active
            artifact = next(item for item in artifacts if item.sourceType == "CODE")
            seen_lengths.append(len(artifact.content))
            if len(artifact.content) > 1_500:
                raise GatewayError("AI gateway returned HTTP 504", status_code=504)
            with active_lock:
                active += 1
                max_active = max(max_active, active)
                if active == 2:
                    two_calls_started.set()
            try:
                assert two_calls_started.wait(timeout=3), "split batches did not run in parallel"
                return sample_result(target, context, artifacts)
            finally:
                with active_lock:
                    active -= 1

    app.state.manager.gateway = ChunkSplitGateway()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            data={"options": '{"target_application":"Orders"}'},
            files={"code_files": ("src/large.py", b"x" * 3_000, "text/plain")},
        )
        assert response.status_code == 202
        task = wait_task(client, response.json()["task_id"])
        assert task["status"] == "success", task.get("error")
        assert seen_lengths == [3_000, 1_500, 1_500]
        assert max_active == 2
        assert task["result"]["files_analyzed"] == 1
        assert task["result"]["repository_coverage"]["analysisBatchCount"] == 2


def test_smallest_batch_504_retries_until_gateway_recovers(tmp_path):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))
    calls = 0

    class RecoveringGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise GatewayError("AI gateway returned HTTP 504", status_code=504)
            return sample_result(target, context, artifacts, coverage=coverage)

    app.state.manager.gateway = RecoveringGateway()
    app.state.manager._wait_for_gateway_retry = lambda task_id, delay: None
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            data={"options": '{"target_application":"Orders"}'},
            files={"code_files": ("orders.py", b"def order_status(): pass", "text/plain")},
        )
        assert response.status_code == 202
        task_id = response.json()["task_id"]
        task = wait_task(client, task_id)
        assert task["status"] == "success", task.get("error")
        assert calls == 3
        technical_document = client.get(f"/api/v1/tasks/{task_id}/document")
        business_document = client.get(f"/api/v1/tasks/{task_id}/business-document")
        assert technical_document.status_code == 200
        assert business_document.status_code == 200
        assert zipfile.is_zipfile(io.BytesIO(technical_document.content))
        assert zipfile.is_zipfile(io.BytesIO(business_document.content))
        with app.state.store.connect() as db:
            assert db.execute(
                "SELECT count(*) FROM analysis_records WHERE task_id=?", (task_id,)
            ).fetchone()[0] == 1


def test_single_batch_429_fails_fast_and_reduces_parallelism(tmp_path):
    app = create_app(settings(
        tmp_path, gateway_url="https://gateway.example/completions",
        analysis_batch_concurrency=8,
    ))
    calls = 0

    class RateLimitedGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            nonlocal calls
            calls += 1
            raise GatewayError(
                "AI gateway returned HTTP 429",
                status_code=429,
                retry_after=0.01,
            )

    app.state.manager.gateway = RateLimitedGateway()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            data={"options": '{"target_application":"Orders"}'},
            files={"code_files": ("orders.py", b"def order_status(): pass", "text/plain")},
        )
        task = wait_task(client, response.json()["task_id"])
        assert task["status"] == "failed"
        assert "HTTP 429" in task["error"]
        assert "not the number of uploaded files" in task["error"]
        assert "instead of retrying automatically" in task["error"]
        assert "0.01 seconds" in task["error"]
        assert calls == 1
        assert app.state.manager.gateway_slots.limit == 1


def test_gateway_exhausted_quota_fails_without_retrying(tmp_path):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))
    calls = 0

    class QuotaGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            nonlocal calls
            calls += 1
            raise GatewayError(
                "AI gateway returned HTTP 429",
                status_code=429,
                error_code="insufficient_quota",
            )

    app.state.manager.gateway = QuotaGateway()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            data={"options": '{"target_application":"Orders"}'},
            files={"code_files": ("orders.py", b"def order_status(): pass", "text/plain")},
        )
        task = wait_task(client, response.json()["task_id"])
        assert task["status"] == "failed"
        assert "exhausted model quota" in task["error"]
        assert "reducing parallelism cannot resolve it" in task["error"]
        assert calls == 1


def test_generic_rate_limit_includes_error_code_without_retrying(tmp_path):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))
    calls = 0

    class InstantLimiter:
        limit = 1

        def acquire(self, check):
            check()

        def release(self, *, success, retry_after=None):
            return None

    class RateLimitedGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            nonlocal calls
            calls += 1
            raise GatewayError(
                "AI gateway returned HTTP 429",
                status_code=429,
                error_code="rate_limit_exceeded",
            )

    app.state.manager.gateway_slots = InstantLimiter()
    app.state.manager.gateway = RateLimitedGateway()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            data={"options": '{"target_application":"Orders"}'},
            files={"code_files": ("orders.py", b"def order_status(): pass", "text/plain")},
        )
        task = wait_task(client, response.json()["task_id"])
        assert task["status"] == "failed"
        assert "HTTP 429 (rate_limit_exceeded)" in task["error"]
        assert "request/token rate limit" in task["error"]
        assert calls == 1


def test_smallest_batch_504_retry_can_be_cancelled(tmp_path):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))
    gateway_called = threading.Event()

    class UnavailableGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            gateway_called.set()
            raise GatewayError("AI gateway returned HTTP 504", status_code=504)

    app.state.manager.gateway = UnavailableGateway()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            data={"options": '{"target_application":"Orders"}'},
            files={"code_files": ("orders.py", b"def order_status(): pass", "text/plain")},
        )
        task_id = response.json()["task_id"]
        assert gateway_called.wait(timeout=3)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            task = client.get(f"/api/v1/tasks/{task_id}").json()
            if "retrying in" in task["message"]:
                break
            time.sleep(0.02)
        assert "retrying in" in task["message"]
        assert client.post(f"/api/v1/tasks/{task_id}/cancel").status_code == 200
        assert wait_task(client, task_id)["status"] == "cancelled"
        assert client.get(f"/api/v1/tasks/{task_id}/document").status_code == 409
        assert client.get(f"/api/v1/tasks/{task_id}/business-document").status_code == 409


def test_supporting_only_does_not_claim_implementation(tmp_path):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))
    app.state.manager.gateway = type("TestGateway", (), {
        "analyze": staticmethod(sample_result)
    })()
    with TestClient(app) as client:
        response = client.post("/api/v1/analysis", data={"options": json.dumps({
            "target_application": "Orders", "manual_stories": [{
                "id": "US-1", "title": "Order status", "description": "Display order status",
            }],
        })})
        task = wait_task(client, response.json()["task_id"])
        assert task["status"] == "success", task.get("error")
        analysis = task["result"]["analysis"]
        assert analysis["highLevelRequirements"][0]["implementationEvidenceStatus"] == "IMPLEMENTATION_NOT_EVIDENCED"
        assert any("No code implementation" in warning for warning in analysis["warnings"])


def test_failed_model_and_cancel_never_publish_documents(tmp_path):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))
    waiting = threading.Event()
    release = threading.Event()

    class TestGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            waiting.set()
            release.wait(timeout=5)
            return sample_result(target, context, artifacts)
    app.state.manager.gateway = TestGateway()
    with TestClient(app) as client:
        response = client.post("/api/v1/analysis", data={"options": '{"target_application":"Orders"}'},
                               files={"code_files": ("orders.py", b"pass", "text/plain")})
        task_id = response.json()["task_id"]
        assert waiting.wait(timeout=3)
        assert client.post(f"/api/v1/tasks/{task_id}/cancel").status_code == 200
        release.set()
        assert wait_task(client, task_id)["status"] == "cancelled"
        assert client.get(f"/api/v1/tasks/{task_id}/document").status_code == 409
        assert client.post(f"/api/v1/tasks/{task_id}/cancel").status_code == 409


def test_api_validation_missing_gateway_and_cross_site_protection(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        assert client.post("/api/v1/analysis").status_code == 503
        assert client.get("/api/v1/health", headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.get("/api/v1/health", headers={"Host": "evil.example"}).status_code == 403
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))
    with TestClient(app) as client:
        empty = client.post("/api/v1/analysis", data={"options": '{"target_application":"Orders"}'})
        assert empty.status_code == 422
        assert client.get("/api/v1/tasks/not-found").status_code == 404
        response = client.post("/api/v1/analysis", data={"options": '{"target_application":"Orders"}'},
                               files={"code_files": ("../escape.py", b"pass", "text/plain")})
        assert response.status_code == 422
    with pytest.raises(ValidationError):
        AnalysisOptions(target_application="Orders", analysis_mode="FULL", selected_path="src")


def test_missing_system_prompt_is_reported_before_analysis_submission(tmp_path, monkeypatch):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))
    monkeypatch.setattr("tip.gateway.PROMPTS", tmp_path / "missing-prompts")
    with TestClient(app) as client:
        configuration = client.get("/api/v1/configuration").json()
        assert configuration["analysis_prompts_configured"] is False
        assert "backend/tip/prompts/system.txt" in configuration["analysis_prompt_issue"]
        response = client.post(
            "/api/v1/analysis",
            data={"options": '{"target_application":"Orders"}'},
            files={"code_files": ("orders.py", b"pass", "text/plain")},
        )
        assert response.status_code == 503
        assert "backend/tip/prompts/system.txt" in response.json()["detail"]
        assert client.get("/api/v1/tasks").json()["total_count"] == 0


def test_file_not_found_failure_reports_only_missing_basename(tmp_path):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))

    class MissingFileGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            raise FileNotFoundError(2, "No such file or directory", str(tmp_path / "request.json"))

    app.state.manager.gateway = MissingFileGateway()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            data={"options": '{"target_application":"Orders"}'},
            files={"code_files": ("orders.py", b"pass", "text/plain")},
        )
        assert response.status_code == 202
        task = wait_task(client, response.json()["task_id"])
        assert task["status"] == "failed"
        assert task["error"] == "Required file or executable not found: request.json"
        assert str(tmp_path) not in task["error"]


def test_remote_protocol_failure_reports_actionable_connectivity_error(tmp_path, caplog):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))

    class DisconnectedGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")

    app.state.manager.gateway = DisconnectedGateway()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            data={"options": '{"target_application":"Orders"}'},
            files={"code_files": ("orders.py", b"pass", "text/plain")},
        )
        task = wait_task(client, response.json()["task_id"])
        assert task["status"] == "failed"
        assert task["error"] == (
            "Remote service closed the connection without a valid HTTP response "
            "(RemoteProtocolError); verify the configured endpoint, request signing, "
            "and network/proxy/VPN connectivity."
        )
        assert "network/proxy/VPN connectivity" in caplog.text


def test_existing_rag_selects_actual_indexed_code_not_summary(tmp_path, monkeypatch):
    config = settings(tmp_path, rag_base_url="https://rag.example/api/v1")
    app = create_app(config)
    artifacts = Extractor(config).extract("orders.py", b"def order_status(): return 'ready'")
    app.state.store.index("existing-rag-repo", artifacts)
    client_type = httpx.Client
    returned_path = ["orders.py"]

    def handle(request):
        assert request.url.params["repoId"] == "existing-rag-repo"
        return httpx.Response(200, json={
            "items": [{"ref": returned_path[0], "summary": "THIS IS NOT SOURCE CODE",
                       "extra": {"path": returned_path[0]}}]
        })

    monkeypatch.setattr("tip.service.httpx.Client",
                        lambda **kwargs: client_type(transport=httpx.MockTransport(handle), **kwargs))
    result = app.state.manager.retrieve("existing-rag-repo", "order status")
    assert result[0].content == artifacts[0].content
    assert "THIS IS NOT SOURCE CODE" not in result[0].content
    returned_path[0] = "unknown.py"
    with pytest.raises(ValueError, match="unknown source paths"):
        app.state.manager.retrieve("existing-rag-repo", "order status")
    app.state.manager.close()


def test_schema_failure_is_explicit_and_never_produces_a_document(tmp_path):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))

    class InvalidGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            result = sample_result(target, context, artifacts)
            result.highLevelRequirements[0].sourceEvidence[0].filePath = "invented.py"
            return result
    app.state.manager.gateway = InvalidGateway()
    with TestClient(app) as client:
        response = client.post("/api/v1/analysis", data={"options": '{"target_application":"Orders"}'},
                               files={"code_files": ("orders.py", b"pass", "text/plain")})
        task_id = response.json()["task_id"]
        task = wait_task(client, task_id)
        assert task["status"] == "failed"
        assert "unknown evidence" in task["error"]
        with app.state.store.connect() as db:
            assert db.execute(
                "SELECT count(*) FROM analysis_records WHERE task_id=?", (task_id,)
            ).fetchone()[0] == 0
        assert client.get(f"/api/v1/tasks/{task_id}/document").status_code == 409

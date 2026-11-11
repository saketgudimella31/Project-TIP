import base64
import hashlib
import hmac
import io
import json
import os
import sqlite3
import subprocess
import threading
import time
import zipfile
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
    mermaid_renderer_configured,
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


def settings(tmp_path, **values):
    return Settings(_env_file=None, data_dir=tmp_path, **values)


def test_store_migrates_business_document_column(tmp_path):
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as db:
        db.execute(
            "CREATE TABLE tasks (id TEXT PRIMARY KEY, body TEXT NOT NULL, document BLOB)"
        )
    store = Store(database_path)
    task = store.create({"kind": "test"})
    store.complete(task["task_id"], {"test": True}, b"technical", b"business")
    assert store.document(task["task_id"]) == b"technical"
    assert store.business_document(task["task_id"]) == b"business"
    with store.connect() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(tasks)")}
    assert "business_document" in columns


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


def wait_task(client, task_id):
    for _ in range(500):
        response = client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        task = response.json()
        if task["status"] not in {"pending", "running"}:
            return task
        time.sleep(0.01)
    raise AssertionError("Task did not complete")


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
    assert Settings(_env_file=None).max_repository_files == 500_000
    assert Settings(_env_file=None).max_repository_bytes == 5_000_000_000
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


def test_repository_extractor_enforces_500000_file_default(tmp_path, monkeypatch):
    extractor = Extractor(Settings(_env_file=None, data_dir=tmp_path))
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


def test_missing_mermaid_renderer_falls_back_without_blocking_documents(tmp_path, monkeypatch):
    artifacts = Extractor(settings(tmp_path)).extract("orders.py", b"def order_status(): pass")
    result = sample_result("Orders", input_context(), artifacts, with_diagram=True)
    monkeypatch.setattr("tip.documents.shutil.which", lambda _: None)

    rendered = render_generated_diagrams(result)
    assert rendered["componentDiagram"] is None
    assert any("structured text version" in warning for warning in result.warnings)

    technical = Document(io.BytesIO(create_document(result, rendered)))
    business = Document(io.BytesIO(create_business_document(result, rendered)))
    technical_text = "\n".join(
        [paragraph.text for paragraph in technical.paragraphs]
        + [cell.text for table in technical.tables for row in table.rows for cell in row.cells]
    )
    business_text = "\n".join(
        [paragraph.text for paragraph in business.paragraphs]
        + [cell.text for table in business.tables for row in table.rows for cell in row.cells]
    )
    assert "Mermaid source:" in technical_text
    assert "Orders component" in technical_text
    assert "From / element" in business_text
    assert "Orders component" in business_text


def test_analysis_publishes_both_documents_without_mermaid_renderer(tmp_path, monkeypatch):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))
    monkeypatch.setattr("tip.documents.shutil.which", lambda _: None)

    class TestGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            return sample_result(target, context, artifacts, with_diagram=True, coverage=coverage)

    app.state.manager.gateway = TestGateway()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analysis",
            data={"options": '{"target_application":"Orders"}'},
            files={"code_files": ("orders.py", b"def order_status(): pass", "text/plain")},
        )
        task = wait_task(client, response.json()["task_id"])
        assert task["status"] == "success", task.get("error")
        assert any(
            "structured text version" in warning
            for warning in task["result"]["analysis"]["warnings"]
        )
        for endpoint in ("document", "business-document"):
            document = client.get(f"/api/v1/tasks/{task['task_id']}/{endpoint}")
            assert document.status_code == 200
            assert zipfile.is_zipfile(io.BytesIO(document.content))


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
    assert render_diagram(result.umlDiagrams.componentDiagram).startswith(b"\x89PNG")
    data = create_document(result)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert any(name.startswith("word/media/") for name in archive.namelist())
        xml = archive.read("word/document.xml").decode()
        assert "flowchart LR" not in xml
        assert "Draft for Human Validation" in xml
    business_data = create_business_document(result)
    with zipfile.ZipFile(io.BytesIO(business_data)) as archive:
        assert any(name.startswith("word/media/") for name in archive.namelist())
        xml = archive.read("word/document.xml").decode()
        assert "Business Requirements" in xml
        assert "How to read it" in xml


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


def test_full_analysis_upload_poll_download_and_reload(tmp_path):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))
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
        assert configuration["repository_clone_timeout_seconds"] == 600
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
        assert analysis.json()["warnings"]
        assert "attachment" in analysis.headers["content-disposition"]
        assert f"TIP-analysis-{task_id}.json" in analysis.headers["content-disposition"]
        document = client.get(f"/api/v1/tasks/{task_id}/document")
        assert document.status_code == 200
        assert zipfile.is_zipfile(io.BytesIO(document.content))
        assert "attachment" in document.headers["content-disposition"]
        indexed_repo = task["result"]["repo_id"]
        related = client.get("/api/v1/graph/related",
                             params={"repoId": indexed_repo, "query": "order_status"})
        assert related.json()["nodes"][0]["path"] == "orders.py"
        context = client.get("/api/v1/context/pack", params={"repoId": indexed_repo, "budget": 100})
        assert context.json()["budget_used"] <= 100
        impact = client.get("/api/v1/graph/impact", params={"repoId": indexed_repo, "file": "orders.py"})
        assert impact.status_code == 200
        assert impact.json()["backend"] == "kuzu"
        assert impact.json()["nodes"] == []
        assert client.get("/api/v1/metrics").status_code == 200
    new_app = create_app(settings(tmp_path))
    with TestClient(new_app) as client:
        assert client.get(f"/api/v1/tasks/{task_id}/document").content == document.content
        assert client.get("/api/v1/tasks").json()["total_count"] == 1


def test_large_repository_analysis_batches_every_eligible_file(tmp_path):
    source_root = tmp_path / "allowed"
    repository = source_root / "orders"
    repository.mkdir(parents=True)
    (repository / "orders.py").write_text(
        "def order_status(): return 'ready'\n", encoding="utf-8",
    )
    (repository / "payments.py").write_text(
        "def authorize_payment(): return True\n", encoding="utf-8",
    )
    (repository / "inventory.py").write_text(
        "def item_count(): return 1\n", encoding="utf-8",
    )
    app = create_app(Settings(
        _env_file=None, data_dir=tmp_path / "data",
        local_source_root=source_root, graph_backend="sqlite",
        gateway_url="https://synthetic.example/completions",
        max_analysis_files=1, analysis_batch_files=1,
    ))
    seen = {"paths": [], "coverage": []}

    class CoverageGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            seen["paths"].extend(
                artifact.filePath for artifact in artifacts if artifact.sourceType == "CODE"
            )
            seen["coverage"].append(coverage)
            return sample_result(target, context, artifacts)

    app.state.manager.gateway = CoverageGateway()
    with TestClient(app) as client:
        response = client.post("/api/v1/analysis", data={"options": json.dumps({
            "target_application": "Orders", "code_source": "local",
            "local_path": str(repository), "focus": "order status",
        })})
        assert response.status_code == 202, response.text
        task = wait_task(client, response.json()["task_id"])
        assert task["status"] == "success", task.get("error")
        assert seen["paths"] == ["inventory.py", "orders.py", "payments.py"]
        assert seen["coverage"] == [{
            "indexedCodeFiles": 3,
            "retrievedCodeFiles": 1,
            "retrievedCharacters": len("def item_count(): return 1\n"),
            "selectionMethod": "all-file bounded batch analysis",
            "batchRequestNumber": 1,
        }, {
            "indexedCodeFiles": 3,
            "retrievedCodeFiles": 1,
            "retrievedCharacters": len("def order_status(): return 'ready'\n"),
            "selectionMethod": "all-file bounded batch analysis",
            "batchRequestNumber": 2,
        }, {
            "indexedCodeFiles": 3,
            "retrievedCodeFiles": 1,
            "retrievedCharacters": len("def authorize_payment(): return True\n"),
            "selectionMethod": "all-file bounded batch analysis",
            "batchRequestNumber": 3,
        }]
        assert task["result"]["files_indexed"] == 3
        assert task["result"]["files_analyzed"] == 3
        assert task["result"]["repository_coverage"] == {
            "indexedCodeFiles": 3,
            "retrievedCodeFiles": 3,
            "retrievedCharacters": sum(map(len, [
                "def item_count(): return 1\n",
                "def order_status(): return 'ready'\n",
                "def authorize_payment(): return True\n",
            ])),
            "selectionMethod": "all-file bounded batch analysis",
            "analysisBatchCount": 3,
        }
        assert len(task["result"]["analysis"]["codebaseInventory"]) == 3
        assert task["result"]["analysis"]["analysisScope"]["analyzedCodeFiles"] == 3
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
        assert offsets == [0, 2]
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
        assert [len(call) for call in calls] == [4, 2, 1, 1, 2, 1, 1]
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
    ))
    seen_lengths = []

    class ChunkSplitGateway:
        def analyze(self, target, context, artifacts, coverage=None):
            artifact = next(item for item in artifacts if item.sourceType == "CODE")
            seen_lengths.append(len(artifact.content))
            if len(artifact.content) > 1_500:
                raise GatewayError("AI gateway returned HTTP 504", status_code=504)
            return sample_result(target, context, artifacts)

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

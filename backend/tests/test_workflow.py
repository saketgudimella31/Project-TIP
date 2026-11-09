import base64
import hashlib
import hmac
import io
import json
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
from tip.documents import create_document, render_diagram
from tip.extraction import Extractor, jira_stories, source_directory
from tip.gateway import Gateway, model_body, signed_headers
from tip.models import AnalysisOptions, InputContext, ManualStory, SupportingInputs
from tip.storage import Store
from tip.validation import validate_plantuml, validate_result

from .fixtures import sample_result


def settings(tmp_path, **values):
    return Settings(_env_file=None, data_dir=tmp_path, **values)


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
    assert settings(tmp_path, local_source_root="", plantuml_jar="").local_source_root is None


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


def test_model_body_and_fresh_signature(tmp_path):
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
    "!include /etc/passwd", "!includeurl https://example.com/a",
    'note "%getenv(\\"HOME\\")" as N', "Alice -> Bob: [[https://example.com]]",
])
def test_uml_blocks_external_content(directive):
    with pytest.raises(ValueError, match="not allowed"):
        validate_plantuml(f"@startuml\ntitle Bad\n{directive}\n@enduml")


def test_real_uml_rendering_and_word_embedding(tmp_path):
    jar = Path("/usr/share/plantuml/plantuml.jar")
    if not jar.is_file():
        pytest.skip("Install Java, Graphviz and PlantUML to exercise the real renderer")
    config = settings(tmp_path, plantuml_jar=jar)
    artifacts = Extractor(config).extract("orders.py", b"def order_status(): pass")
    result = sample_result("Orders", input_context(), artifacts, with_diagram=True)
    validate_result(result, artifacts, input_context(), "Orders")
    assert render_diagram(result.umlDiagrams.componentDiagram, config).startswith(b"\x89PNG")
    data = create_document(result, config)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert any(name.startswith("word/media/") for name in archive.namelist())
        xml = archive.read("word/document.xml").decode()
        assert "@startuml" not in xml
        assert "Draft for Human Validation" in xml


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


def test_full_analysis_upload_poll_download_and_reload(tmp_path):
    app = create_app(settings(tmp_path, gateway_url="https://gateway.example/completions"))
    seen = []

    class TestGateway:
        def analyze(self, target, context, artifacts):
            seen.extend(artifacts)
            return sample_result(target, context, artifacts)
    app.state.manager.gateway = TestGateway()
    with TestClient(app) as client:
        configuration = client.get("/api/v1/configuration").json()
        assert configuration["persistence_backend"] == "SQLite"
        assert configuration["persistence_configured"] is True
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
        assert client.get("/api/v1/graph/impact", params={"repoId": indexed_repo, "file": "orders.py"}).status_code == 501
        assert client.get("/api/v1/metrics").status_code == 200
    new_app = create_app(settings(tmp_path))
    with TestClient(new_app) as client:
        assert client.get(f"/api/v1/tasks/{task_id}/document").content == document.content
        assert client.get("/api/v1/tasks").json()["total_count"] == 1


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
        def analyze(self, target, context, artifacts):
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
        AnalysisOptions(target_application="Orders", analysis_mode="FULL", focus="orders")


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
        def analyze(self, target, context, artifacts):
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

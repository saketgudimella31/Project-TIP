import json

import httpx
import pytest
from fastapi.testclient import TestClient

from tip import qtest
from tip.app import create_app
from tip.config import Settings
from tip.storage import Store


FIELDS = [
    {"id": 1, "label": "Description", "is_active": True},
    {"id": 2, "label": "Status", "allowed_values": [
        {"label": "New", "value": 11, "is_active": True},
    ]},
    {"id": 3, "label": "Type", "allowed_values": [
        {"label": "Functional", "value": 12, "is_active": True},
        {"label": "Non-functional", "value": 13, "is_active": True},
    ]},
    {"id": 4, "label": "Priority", "allowed_values": [
        {"label": "Must have", "value": 14, "is_active": True},
    ]},
]


def requirement(identifier, parent=None):
    return {
        "requirementId": identifier, "parentRequirementId": parent,
        "name": identifier, "description": "Ensure <b>safe</b> behavior",
        "type": "FUNCTIONAL", "priority": "Must have",
        "acceptanceCriteria": ["It works"], "evidenceReferences": [],
    }


def use_qtest_server(monkeypatch, handler):
    client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(qtest.httpx, "Client", lambda **kwargs: client(transport=transport, **kwargs))


def test_upload_maps_fields_keeps_parent_and_skips_duplicates(tmp_path, monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=FIELDS)
        return httpx.Response(201, json={"id": 100 + len(requests)})

    store = Store(tmp_path / "tip.sqlite")
    use_qtest_server(monkeypatch, handler)
    records = [requirement("REQ-1"), requirement("REQ-1.1", "REQ-1")]
    result = qtest.upload_requirements(store, "https://qtest.example", "task", 7, "token-one", records, 5)
    posts = [request for request in requests if request.method == "POST"]
    assert result["success"] and len(result["created"]) == 2
    assert all(request.headers["Authorization"] == "Bearer token-one" for request in requests)
    assert posts[0].url.params["parentId"] == "5"
    properties = {item["field_id"]: item["field_value"] for item in json.loads(posts[1].content)["properties"]}
    assert properties[2] == "11" and properties[3] == "12" and properties[4] == "14"
    assert "TIP parent requirement: REQ-1" in properties[1]
    assert "&lt;b&gt;" not in properties[1]
    again = qtest.upload_requirements(store, "https://qtest.example", "task", 7, "token-two", records, 5)
    assert len(again["already_uploaded"]) == 2
    assert len([request for request in requests if request.method == "POST"]) == 2
    assert requests[-1].headers["Authorization"] == "Bearer token-two"
    with store.connect() as db:
        rows = [dict(row) for row in db.execute("SELECT * FROM qtest_uploads")]
    assert "token-one" not in repr(rows) and "token-two" not in repr(rows)


def test_preflight_invalid_fields_writes_nothing(tmp_path, monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=FIELDS + [{"id": 5, "label": "Region", "required": True}])

    use_qtest_server(monkeypatch, handler)
    with pytest.raises(qtest.QTestError, match="Region"):
        qtest.upload_requirements(Store(tmp_path / "tip.sqlite"), "https://qtest.example", "task", 1, "token", [requirement("REQ-1")], None)
    assert [request.method for request in requests] == ["GET"]


def test_partial_upload_does_not_retry_uncertain_result(tmp_path, monkeypatch):
    posts = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=FIELDS)
        posts.append(request)
        return httpx.Response(201, json={"id": 20}) if len(posts) == 1 else httpx.Response(500)

    use_qtest_server(monkeypatch, handler)
    store = Store(tmp_path / "tip.sqlite")
    records = [requirement("REQ-1"), requirement("REQ-2")]
    result = qtest.upload_requirements(store, "https://qtest.example", "task", 1, "token", records, None)
    assert not result["success"] and result["created"] == [{"requirement_id": "REQ-1", "qtest_id": "20"}]
    again = qtest.upload_requirements(store, "https://qtest.example", "task", 1, "token", records, None)
    assert not again["success"] and "uncertain" in again["message"]
    assert again["already_uploaded"] == [{"requirement_id": "REQ-1", "qtest_id": "20"}]
    assert len(posts) == 2


def test_endpoint_requires_confirmation_and_does_not_expose_tokens(tmp_path, monkeypatch):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path, qtest_base_url="https://qtest.example"))
    task = app.state.store.create({"kind": "analysis"})
    app.state.store.complete(task["task_id"], {}, b"", canonical_json=json.dumps({"requirements": [requirement("REQ-1")]}).encode())
    seen = []

    def upload(store, base, task_id, project, token, records, module):
        seen.append(token)
        return {"success": True, "message": "done", "created": [], "already_uploaded": []}

    monkeypatch.setattr("tip.app.upload_requirements", upload)
    with TestClient(app) as client:
        path = f"/api/v1/tasks/{task['task_id']}/qtest-upload"
        rejected = client.post(path, json={"project_id": 1, "token": "private-token", "confirmed": False})
        assert rejected.status_code == 400 and "private-token" not in rejected.text and not seen
        response = client.post(path, json={"project_id": 1, "token": "Bearer private-token", "confirmed": True})
        assert response.status_code == 200 and "private-token" not in response.text
        assert seen == ["private-token"]
        invalid = client.post(path, json={"project_id": 1, "token": "private-token\nother", "confirmed": True})
        assert invalid.status_code == 400 and "private-token" not in invalid.text
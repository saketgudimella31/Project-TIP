"""Publish validated requirements to a configured qTest server."""

import html
import sqlite3
from urllib.parse import urlsplit, urlunsplit

import httpx

from .outputs import _plain_description, _qtest_priority
from .storage import Store


class QTestError(ValueError):
    pass


def _server_key(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def _properties(fields: list, requirement: dict) -> list:
    labels = {
        "description": _plain_description(requirement),
        "status": "New",
        "type": "Functional" if requirement["type"] == "FUNCTIONAL" else "Non-functional",
        "priority": _qtest_priority(requirement.get("priority"), requirement["requirementId"]),
    }
    if requirement.get("parentRequirementId"):
        labels["description"] += f"\n\nTIP parent requirement: {requirement['parentRequirementId']}"
    labels["description"] = html.escape(labels["description"]).replace("\n", "<br/>")
    by_label = {}
    for field in fields:
        if not isinstance(field, dict) or not isinstance(field.get("label"), str):
            raise QTestError("qTest returned invalid field definitions; no requirements were uploaded.")
        if field.get("is_active") is False:
            continue
        label = field["label"].strip().casefold()
        if label in by_label:
            raise QTestError("qTest returned ambiguous field labels; no requirements were uploaded.")
        by_label[label] = field
    for name in ("description", "status", "type"):
        if name not in by_label:
            raise QTestError(f"qTest project is missing the {name} field; no requirements were uploaded.")
    if labels["priority"] and "priority" not in by_label:
        raise QTestError("qTest project is missing the priority field; no requirements were uploaded.")
    properties = []
    for label, field in by_label.items():
        if label == "name":
            continue
        value = labels.get(label)
        if value is None or value == "":
            if field.get("required") and not field.get("default_value"):
                raise QTestError(
                    f"qTest requires a value for field {field['label']}; "
                    "configure or supply it before uploading."
                )
            continue
        if not isinstance(field.get("id"), int):
            raise QTestError(f"qTest field {field['label']} has no valid ID.")
        allowed = field.get("allowed_values") or []
        if allowed:
            matches = [
                item for item in allowed
                if isinstance(item, dict) and item.get("is_active") is not False
                and str(item.get("label", "")).casefold() == value.casefold()
            ]
            if len(matches) != 1 or matches[0].get("value") is None:
                raise QTestError(f"qTest field {field['label']} does not allow {value!r}.")
            value = str(matches[0]["value"])
        elif field.get("constrained") or label in {"status", "type", "priority"}:
            raise QTestError(f"qTest field {field['label']} has no available allowed values.")
        properties.append({"field_id": field["id"], "field_value": value})
    return properties


def upload_requirements(
    store: Store, base_url: str, task_id: str, project_id: int,
    token: str, requirements: list[dict], module_id: int | None,
) -> dict:
    if not base_url:
        raise QTestError("Configure TIP_QTEST_BASE_URL on the backend before uploading.")
    server = _server_key(base_url)
    endpoint = f"{server}/api/v3/projects/{project_id}"
    if not requirements:
        raise QTestError("This analysis has no requirements to upload.")
    if len({item["requirementId"] for item in requirements}) != len(requirements):
        raise QTestError("The analysis has duplicate requirement IDs; no requirements were uploaded.")
    if any(not isinstance(item.get("name"), str) or not 1 <= len(item["name"]) <= 500
           for item in requirements):
        raise QTestError("Every requirement must have a name of 1–500 characters.")
    with httpx.Client(
        timeout=30, follow_redirects=False,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    ) as client:
        try:
            fields_response = client.get(f"{endpoint}/settings/requirements/fields")
        except httpx.RequestError as error:
            raise QTestError("Could not reach qTest field settings; no requirements were uploaded.") from error
        if fields_response.status_code != 200:
            raise QTestError(
                f"qTest field settings returned HTTP {fields_response.status_code}; "
                "check the token, project ID, and privileges. No requirements were uploaded."
            )
        try:
            fields = fields_response.json()
        except ValueError as error:
            raise QTestError("qTest returned invalid field settings; no requirements were uploaded.") from error
        if not isinstance(fields, list):
            raise QTestError("qTest returned invalid field settings; no requirements were uploaded.")
        try:
            prepared = [
                (item, {"name": item["name"], "properties": _properties(fields, item)})
                for item in requirements
            ]
        except ValueError as error:
            raise QTestError(str(error)) from error
        created = []
        skipped = []

        def stopped(message: str) -> dict:
            return {"success": False, "message": message,
                    "created": created, "already_uploaded": skipped}

        for item, payload in prepared:
            identity = (task_id, server, project_id, item["requirementId"])
            with store.connect() as db:
                row = db.execute(
                    "SELECT state, remote_id FROM qtest_uploads "
                    "WHERE task_id=? AND server=? AND project_id=? AND requirement_id=?",
                    identity,
                ).fetchone()
                if row and row["state"] == "created":
                    skipped.append({"requirement_id": identity[3], "qtest_id": row["remote_id"]})
                    continue
                if row and row["state"] == "pending":
                    return stopped(
                        f"Upload outcome for {identity[3]} is uncertain. Check qTest before "
                        "retrying; TIP will not risk creating a duplicate."
                    )
                try:
                    db.execute(
                        "INSERT INTO qtest_uploads VALUES (?, ?, ?, ?, 'pending', NULL)",
                        identity,
                    )
                except sqlite3.IntegrityError:
                    return stopped("A qTest upload is already in progress.")
            try:
                response = client.post(
                    f"{endpoint}/requirements",
                    params={"parentId": module_id} if module_id is not None else None,
                    json=payload,
                )
            except httpx.RequestError:
                return stopped(
                    f"Connection failed while uploading {identity[3]}; the outcome is uncertain. "
                    "Check qTest before retrying."
                )
            if not 200 <= response.status_code < 300:
                if 400 <= response.status_code < 500 and response.status_code not in {408, 429}:
                    with store.connect() as db:
                        db.execute(
                            "DELETE FROM qtest_uploads WHERE task_id=? AND server=? "
                            "AND project_id=? AND requirement_id=? AND state='pending'", identity,
                        )
                return stopped(
                    f"qTest returned HTTP {response.status_code} while uploading {identity[3]}. "
                    f"{len(created)} requirements were created in this attempt; check qTest "
                    "before retrying, especially after server errors."
                )
            try:
                remote = response.json()
                remote_id = remote["id"]
                if not isinstance(remote_id, int) or isinstance(remote_id, bool):
                    raise ValueError("Invalid qTest ID")
            except (ValueError, KeyError, TypeError):
                return stopped(
                    f"qTest accepted {identity[3]} but returned no valid ID; the outcome is "
                    "uncertain. Check qTest before retrying."
                )
            with store.connect() as db:
                db.execute(
                    "UPDATE qtest_uploads SET state='created', remote_id=? "
                    "WHERE task_id=? AND server=? AND project_id=? AND requirement_id=?",
                    (str(remote_id), *identity),
                )
            created.append({"requirement_id": identity[3], "qtest_id": str(remote_id)})
    return {"success": True, "message": "Upload complete.",
            "created": created, "already_uploaded": skipped}

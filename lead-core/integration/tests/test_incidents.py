"""Incident correlation, lifecycle, authorization and export coverage."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import time

import pytest

from addons import auth
from addons.incident_engine import IncidentService, validate_note

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def event(event_id, host="host-a", technique_id="T1046", technique_name="Network Service Discovery", severity="LOW", ts="2026-11-05T12:00:00Z"):
    return {
        "event_id": event_id,
        "ts": ts,
        "host": host,
        "packet_id": None,
        "anomaly": True,
        "risk_score": 35.0 if severity == "LOW" else 65.0 if severity == "MEDIUM" else 90.0,
        "severity": severity,
        "explanation": "Scripted security activity in the simulation.",
        "technique_id": technique_id,
        "technique_name": technique_name,
        "source": "scripted",
    }


def incident_service(ctx):
    return ctx["hooks"].get("incidents").service


def start_replay(client, scenario_id, speed=40):
    response = client.post("/api/x/replay/start", json={"scenario_id": scenario_id, "speed": speed})
    assert response.status_code == 200, response.get_data(as_text=True)


def wait_for(client, predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get("/api/x/state").get_json()
        if predicate(state):
            return state
        time.sleep(0.01)
    raise AssertionError("The replay did not reach the expected state.")


def test_correlation_rules_and_non_rules(ctx, world):
    service = incident_service(ctx)
    service.reset()
    service._session_id = "ses-rule-test"
    base = {
        "incident_id": "INC-0001",
        "session_id": "ses-rule-test",
        "status": "open",
        "affected_hosts": ["host-a"],
        "last_alert_at": "2026-11-05T12:00:00Z",
        "techniques": [{"technique_id": "T1046", "tactics": ["discovery"]}],
    }

    same_host = event("evt-000002", host="host-a", technique_id="T1046", ts="2026-11-05T12:00:20Z")
    assert "already in this incident" in service.correlation_reason(same_host, base)

    one_hop = event("evt-000003", host="file-server", technique_id="T1046", ts="2026-11-05T12:00:20Z")
    assert "one feasible hop" in service.correlation_reason(one_hop, base)

    tactic_chain = event("evt-000004", host="domain-controller", technique_id="T1021", technique_name="Remote Services", ts="2026-11-05T13:00:00Z")
    assert "ATT&CK tactic chain" in service.correlation_reason(tactic_chain, base)

    outside_window = event("evt-000005", host="host-a", technique_id="T1046", ts="2026-11-05T13:00:00Z")
    assert service.correlation_reason(outside_window, base) is None

    other_session = dict(base, session_id="ses-other")
    assert service.correlation_reason(same_host, other_session) is None
    closed = dict(base, status="closed")
    assert service.correlation_reason(same_host, closed) is None
    contained = dict(base, status="contained")
    assert service.correlation_reason(same_host, contained) is None


def test_correlation_is_idempotent_deterministic_and_rolls_up_severity(ctx, world):
    service = incident_service(ctx)
    world.reset()
    first = event("evt-000001", severity="LOW", ts="2026-11-05T12:00:00Z")
    second = event("evt-000002", host="host-a", severity="HIGH", ts="2026-11-05T12:00:05Z")

    service.reset()
    created = service.ingest_alert(first)
    service.ingest_alert(first)  # duplicate delivery is ignored
    merged = service.ingest_alert(second)
    normalized_one = service.get(created["incident_id"])
    assert merged["incident_id"] == "INC-0001"
    assert normalized_one["alert_ids"] == ["evt-000001", "evt-000002"]
    assert normalized_one["severity"] == "HIGH"
    assert normalized_one["affected_hosts"] == ["host-a"]
    assert len(normalized_one["correlation_reasons"]) == 2

    service.reset()
    service.ingest_alert(first)
    service.ingest_alert(second)
    normalized_two = service.get("INC-0001")
    assert normalized_one == normalized_two


@pytest.mark.parametrize("body", ["", "  ", "x" * 2001, "bad\x00text", "<script>alert(1)</script>"])
def test_incident_note_plain_text_validation(body):
    with pytest.raises(ValueError):
        validate_note(body)


def test_incident_status_transitions_and_reason_rules(ctx, world):
    service = incident_service(ctx)
    service.reset()
    service.ingest_alert(event("evt-000001"))
    with pytest.raises(ValueError, match="Confirm"):
        service.change_status("INC-0001", "closed", "Reviewed", False, "analyst", "analyst")
    with pytest.raises(ValueError, match="required"):
        service.change_status("INC-0001", "closed", "", True, "analyst", "analyst")
    closed = service.change_status("INC-0001", "closed", "Replay reviewed", True, "analyst", "analyst")
    assert closed["status"] == "closed" and closed["closed_reason"] == "Replay reviewed"
    reopened = service.change_status("INC-0001", "reopened", "New related evidence", True, "admin", "admin")
    assert reopened["status"] == "reopened" and reopened["closed_reason"] is None
    with pytest.raises(ValueError, match="cannot move"):
        service.change_status("INC-0001", "reopened", "again", True, "admin", "admin")


def test_role_accounts_login_and_viewer_is_read_only(client, ctx, world):
    response = client.post("/api/x/login", json={"username": "analyst", "password": "test-analyst-password"})
    assert response.status_code == 200 and response.get_json()["role"] == "analyst"
    assert client.get("/api/x/me").get_json()["read_only"] is False

    service = incident_service(ctx)
    service.reset()
    world.reset()
    service.ingest_alert(event("evt-000001"))
    note = client.post("/api/x/incidents/INC-0001/notes", json={"body": "Review the simulated scan."})
    assert note.status_code == 201

    viewer = client.application.test_client()
    login = viewer.post("/api/x/login", json={"username": "viewer", "password": "test-viewer-password"})
    assert login.status_code == 200 and login.get_json()["role"] == "viewer"
    assert viewer.post("/api/x/incidents/INC-0001/notes", json={"body": "A viewer note."}, headers={"X-Precog-Request": "1"}).status_code == 403
    assert viewer.post("/api/x/incidents/INC-0001/status", json={"status": "closed", "reason": "x", "confirm": True}, headers={"X-Precog-Request": "1"}).status_code == 403
    assert viewer.post("/api/x/replay/start", json={"scenario_id": "golden-path"}, headers={"X-Precog-Request": "1"}).status_code == 403
    assert viewer.post("/api/x/containment/propose", json={"target_host": "server-b"}, headers={"X-Precog-Request": "1"}).status_code == 403


def test_write_requires_json_and_same_origin_request_header(client, world):
    assert client.post("/api/x/login", json={"username": "admin", "password": ADMIN_PASSWORD}).status_code == 200
    missing = client.post("/api/x/incidents/INC-0001/notes", json={"body": "No custom header."}, headers={"X-Precog-Request": ""})
    assert missing.status_code == 403 and missing.get_json()["error"]["code"] == "csrf_rejected"
    wrong_type = client.post("/api/x/incidents/INC-0001/notes", data="body=x", content_type="text/plain", headers={"X-Precog-Request": "1"})
    assert wrong_type.status_code == 415
    wrong_origin = client.post("/api/x/incidents/INC-0001/notes", json={"body": "Cross origin."}, headers={"X-Precog-Request": "1", "Origin": "https://attacker.example"})
    assert wrong_origin.status_code == 403


def test_write_size_limit_and_fetch_metadata_reject_cross_site(client, world):
    assert client.post("/api/x/login", json={"username": "admin", "password": ADMIN_PASSWORD}).status_code == 200
    too_large = client.post(
        "/api/x/incidents/INC-0001/notes",
        json={"body": "x" * 33000},
    )
    assert too_large.status_code == 413
    cross_site = client.post(
        "/api/x/incidents/INC-0001/notes",
        json={"body": "cross-site attempt"},
        headers={"X-Precog-Request": "1", "Sec-Fetch-Site": "cross-site"},
    )
    assert cross_site.status_code == 403


def test_incident_routes_filter_page_export_and_audit(client, ctx, world):
    assert client.post("/api/x/login", json={"username": "analyst", "password": "test-analyst-password"}).status_code == 200
    service = incident_service(ctx)
    service.reset()
    world.reset()
    service.ingest_alert(event("evt-000001", host="host-a", severity="HIGH"))
    service.ingest_alert(event("evt-000002", host="host-a", technique_id="T1110", technique_name="Brute Force", severity="HIGH", ts="2026-11-05T12:00:10Z"))
    service.ingest_alert(event("evt-000003", host="db-server", severity="LOW", ts="2026-11-05T13:00:00Z"))

    first = client.get("/api/x/incidents?sort=created_asc&limit=1")
    assert first.status_code == 200
    page_one = first.get_json()
    assert page_one["total"] == 2 and len(page_one["items"]) == 1
    page_two = client.get("/api/x/incidents?sort=created_asc&limit=1&cursor=" + page_one["next_cursor"]).get_json()
    assert len(page_two["items"]) == 1 and page_two["items"][0]["incident_id"] != page_one["items"][0]["incident_id"]
    high = client.get("/api/x/incidents?severity=HIGH&host=host-a&technique=T1110").get_json()
    assert high["total"] == 1
    assert client.get("/api/x/incidents?severity=critical").status_code == 400
    assert client.get("/api/x/incidents/INC-ABCD").status_code == 400

    incident_id = page_one["items"][0]["incident_id"]
    note = client.post("/api/x/incidents/%s/notes" % incident_id, json={"body": "Analyst reviewed the evidence."})
    assert note.status_code == 201
    assert client.post("/api/x/incidents/%s/status" % incident_id, json={"status": "closed", "reason": "Investigation complete", "confirm": True}).status_code == 200
    timeline = client.get("/api/x/incidents/%s/timeline" % incident_id)
    assert timeline.status_code == 200
    types = [entry["type"] for entry in timeline.get_json()]
    assert "note" in types and "status_change" in types

    json_export = client.get("/api/x/incidents/%s/export" % incident_id)
    assert json_export.status_code == 200 and json_export.headers["Content-Disposition"].endswith(".json\"")
    assert json_export.get_json()["incident"]["incident_id"] == incident_id
    markdown = client.get("/api/x/incidents/%s/export?format=markdown" % incident_id)
    assert markdown.status_code == 200 and "text/markdown" in markdown.content_type
    assert b"SIMULATION" in markdown.data and b"Analyst reviewed the evidence." in markdown.data
    assert client.get("/api/x/incidents/%s/export?format=exe" % incident_id).status_code == 400

    audit = service.audit_log.read_all()
    assert [entry["type"] for entry in audit[-2:]] == ["note", "status_change"]
    assert audit[-2]["text"] == "Analyst reviewed the evidence."
    assert audit[-1]["reason"] == "Investigation complete"
    assert not list(service.audit_log.path.parent.glob(".incident-audit-*.tmp"))


def test_feed_versions_are_domain_scoped_and_since_is_validated(logged_in, ctx, world):
    first = logged_in.get("/api/x/feed").get_json()
    unchanged = logged_in.get("/api/x/feed?since=%d" % first["revision"]).get_json()
    assert unchanged["changed"] is False and unchanged["versions"] == first["versions"]
    service = incident_service(ctx)
    service.reset()
    world.reset()
    service.ingest_alert(event("evt-000001"))
    changed = logged_in.get("/api/x/feed?since=%d" % first["revision"]).get_json()
    assert changed["changed"] is True and changed["versions"]["incidents"] > first["versions"]["incidents"]
    assert logged_in.get("/api/x/feed?since=-1").status_code == 400
    assert logged_in.get("/api/x/feed?since=nope").status_code == 400


def test_export_rate_limit_is_in_memory(client, ctx, world):
    assert client.post("/api/x/login", json={"username": "admin", "password": ADMIN_PASSWORD}).status_code == 200
    service = incident_service(ctx)
    service.reset()
    world.reset()
    service.ingest_alert(event("evt-000001"))
    with auth._RATE_LOCK:
        auth._RATE_BUCKETS.clear()
    replies = [client.get("/api/x/incidents/INC-0001/export") for _ in range(12)]
    assert all(reply.status_code == 200 for reply in replies)
    assert client.get("/api/x/incidents/INC-0001/export").status_code == 429

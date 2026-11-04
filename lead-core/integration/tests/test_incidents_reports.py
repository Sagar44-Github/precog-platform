import copy

import pytest

from addons.loader import ROLE_PACKAGES, AddonContext, _load_role_packages


@pytest.fixture()
def incident_roles(flask_app, monkeypatch):
    """Re-register real roles because API fixtures may leave the shared hook registry empty."""
    monkeypatch.setenv("PUSH_WATCHER", "0")
    shared = flask_app.extensions["precog"]
    context = AddonContext(shared["world"], shared["hooks"], shared["config"], shared["contracts"], shared["nids"], flask_app)
    shared["hooks"]._items.clear()
    report = _load_role_packages(context, ROLE_PACKAGES)
    assert all(report.get(name) == "registered" for name in ROLE_PACKAGES)
    yield shared
    replay = shared["hooks"].get("replay")
    if replay is not None:
        replay.stop()
    containment = shared["hooks"].get("containment")
    if containment is not None:
        containment.shutdown()
    shared["hooks"]._items.clear()


def test_incidents_group_sample_session_evidence_and_filter(logged_in):
    response = logged_in.get("/api/x/incidents")
    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 1
    incident = body["items"][0]
    assert incident["incident_id"] == "inc-ses-000001"
    assert incident["status"] == "open"
    assert incident["alert_count"] == 2
    assert set(incident["hosts"]) == {"host-a", "server-b"}
    assert {entry["kind"] for entry in incident["timeline"]} == {"detection", "forecast", "containment"}

    filtered = logged_in.get("/api/x/incidents?q=host-a&severity=HIGH&status=open").get_json()
    assert filtered["total"] == 1
    assert logged_in.get("/api/x/incidents?status=invalid").status_code == 400
    assert logged_in.get("/api/x/incidents?cursor=-1").status_code == 400
    assert logged_in.get("/api/x/incidents/not-a-case").status_code == 404


def test_incident_notes_status_and_audit_survive_session_archive(logged_in, world, incident_roles, monkeypatch, tmp_path):
    monkeypatch.setattr(incident_roles["hooks"].get("events").audit, "path", tmp_path / "incident-audit.jsonl")
    incident_id = "inc-ses-000001"
    note_response = logged_in.post("/api/x/incidents/%s/notes" % incident_id, json={"text": "Reviewed the scripted login sequence."})
    assert note_response.status_code == 201
    note = note_response.get_json()
    assert note["author"] == "admin" and note["text"].startswith("Reviewed")
    assert logged_in.post("/api/x/incidents/%s/notes" % incident_id, json={"text": " "}).status_code == 400
    assert logged_in.post("/api/x/incidents/%s/notes" % incident_id, json={"text": "x" * 2001}).status_code == 400

    changed = logged_in.patch("/api/x/incidents/%s/status" % incident_id, json={"status": "closed"})
    assert changed.status_code == 200
    assert changed.get_json()["status"] == "closed"
    assert changed.get_json()["notes"][0]["note_id"] == note["note_id"]
    assert logged_in.patch("/api/x/incidents/%s/status" % incident_id, json={"status": "resolved"}).status_code == 400

    world.archive_session()
    world.reset()
    archived = logged_in.get("/api/x/incidents/%s" % incident_id).get_json()
    assert archived["status"] == "closed"
    assert archived["notes"][0]["text"] == "Reviewed the scripted login sequence."
    audit = logged_in.get("/api/x/audit?type=incident").get_json()
    assert audit["total"] == 2
    assert all(item["type"] == "incident" for item in audit["items"])


def test_report_calculates_session_only_forecast_metrics(logged_in, world):
    forecast = copy.deepcopy(world.forecasts()[0])
    world.resolve_forecast(forecast["forecast_id"], "hit", {"attempted_host": "server-b", "rank_hit": 1, "blocked": False})

    index = logged_in.get("/api/x/reports")
    assert index.status_code == 200
    assert index.get_json()["total"] == 1
    assert index.get_json()["items"][0]["forecasts_resolved"] == 1

    response = logged_in.get("/api/x/reports/ses-000001")
    report = response.get_json()
    assert response.status_code == 200
    assert report["metrics"]["hit_rate"] == 1
    assert report["metrics"]["precision_at_1"] == 1
    assert report["metrics"]["precision_at_3"] == 1
    assert "Session counter, not the model's overall accuracy" in report["metrics"]["honesty_note"]
    assert logged_in.get("/api/x/reports/missing").status_code == 404


def test_incident_and_report_endpoints_require_login(client):
    for method, path in (
        ("get", "/api/x/incidents"),
        ("get", "/api/x/incidents/inc-ses-000001"),
        ("post", "/api/x/incidents/inc-ses-000001/notes"),
        ("patch", "/api/x/incidents/inc-ses-000001/status"),
        ("get", "/api/x/reports"),
        ("get", "/api/x/reports/ses-000001"),
    ):
        response = getattr(client, method)(path, json={}) if method != "get" else client.get(path)
        assert response.status_code == 401, path
        assert response.get_json()["error"]["code"] == "not_logged_in"

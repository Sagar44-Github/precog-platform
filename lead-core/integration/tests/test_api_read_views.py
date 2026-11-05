import copy

import pytest

from addons.loader import ROLE_PACKAGES, AddonContext, _load_role_packages


@pytest.fixture()
def role_stack(flask_app, monkeypatch):
    """The API fixture intentionally empties shared hooks; restore real roles for these read-view checks."""
    monkeypatch.setenv("PUSH_WATCHER", "0")
    shared = flask_app.extensions["precog"]
    original = dict(shared["hooks"]._items)
    context = AddonContext(shared["world"], shared["hooks"], shared["config"], shared["contracts"], shared["nids"], flask_app)
    shared["hooks"]._items.clear()
    report = _load_role_packages(context, ROLE_PACKAGES)
    missing = [name for name in ROLE_PACKAGES if report.get(name) != "registered"]
    assert not missing, "roles did not register: %s" % ", ".join(missing)
    yield shared
    replay = shared["hooks"].get("replay")
    if replay is not None:
        replay.stop()
    containment = shared["hooks"].get("containment")
    if containment is not None:
        containment.shutdown()
    shared["hooks"]._items.clear()
    shared["hooks"]._items.update(original)


def _event(world, event_id, host, severity, technique, risk, explanation, ts="2026-10-03T10:00:01Z"):
    event = copy.deepcopy(world.alerts(1)[0])
    event.update({
        "event_id": event_id, "host": host, "severity": severity,
        "technique_id": technique, "technique_name": "Test technique",
        "risk_score": risk, "explanation": explanation, "ts": ts,
    })
    world.add_alert(event)


def test_alert_search_filters_sorts_and_pages(logged_in, world):
    _event(world, "evt-search-1", "host-a", "HIGH", "T1110", 72, "sentinel search alpha")
    _event(world, "evt-search-2", "host-b", "MEDIUM", "T1078", 95, "sentinel search beta")
    _event(world, "evt-search-3", "host-a", "HIGH", "T1110", 91, "sentinel search gamma")
    query = "q=sentinel&severity=high&host=host-a&technique=T1110&from=2026-10-03&to=2026-10-03&sort=risk_score&order=desc&limit=1"

    first = logged_in.get("/api/x/alerts/search?" + query).get_json()
    assert first["total"] == 2
    assert first["items"][0]["event_id"] == "evt-search-3"
    assert first["next_cursor"] == "1"
    assert first["filters"]["severity"] == "HIGH"

    second = logged_in.get("/api/x/alerts/search?" + query + "&cursor=1").get_json()
    assert [row["event_id"] for row in second["items"]] == ["evt-search-1"]
    assert second["next_cursor"] is None


def test_alert_search_rejects_bad_filters_and_cursors(logged_in):
    assert logged_in.get("/api/x/alerts/search?severity=urgent").status_code == 400
    assert logged_in.get("/api/x/alerts/search?from=yesterday").status_code == 400
    assert logged_in.get("/api/x/alerts/search?cursor=-1").status_code == 400
    assert logged_in.get("/api/x/alerts/search?sort=source").status_code == 400


def test_assets_include_simulated_weaknesses_and_state_history(logged_in, world, role_stack):
    graph = world.graph()
    host_a = next(host for host in graph["hosts"] if host["host_id"] == "host-a")
    previous_state = host_a["state"]
    host_a["state"] = "contained"
    world.set_graph(graph)

    reply = logged_in.get("/api/x/assets")
    assert reply.status_code == 200
    body = reply.get_json()
    assert body["total"] == 6
    asset = next(item for item in body["items"] if item["host_id"] == "host-a")
    assert asset["state"] == "contained"
    assert asset["reachable_hosts"] == ["host-b", "server-b", "file-server"]
    assert all(weakness["simulated"] and weakness["id"].startswith("DEMO-") for weakness in asset["weaknesses"])
    assert asset["state_history"][-1]["from_state"] == previous_state
    assert asset["state_history"][-1]["state"] == "contained"


def test_audit_page_filters_and_reports_malformed_log_lines(logged_in, ctx, role_stack, monkeypatch, tmp_path):
    audit = ctx["hooks"].get("events").audit
    monkeypatch.setattr(audit, "path", tmp_path / "audit.jsonl")
    audit.record("detection", "evt-audit-1", "high alert on host-a", ts="2026-10-03T10:00:01Z")
    audit.record("containment", "act-audit-1", "contained host-a", ts="2026-10-03T10:00:02Z")
    with audit.path.open("a", encoding="utf-8") as handle:
        handle.write("{damaged line}\n")

    page = logged_in.get("/api/x/audit?type=containment&ref_id=act-audit&limit=1").get_json()
    assert page["total"] == 1
    assert page["items"][0]["ref_id"] == "act-audit-1"
    assert page["filters"]["type"] == "containment"
    assert logged_in.get("/api/x/audit?type=unknown").status_code == 400
    assert logged_in.get("/api/x/audit?cursor=not-a-number").status_code == 400


def test_system_status_reports_runtime_and_module_health(logged_in):
    response = logged_in.get("/api/x/system")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok" and body["data_mode"] == "sample"
    assert body["versions"]["python"] and body["versions"]["flask"] and body["versions"]["sqlite"]
    assert body["modules"]["detect_events"] == "registered"
    assert body["checks"]["contract_validation"] is True


def test_new_read_endpoints_require_login(client):
    for path in ("/api/x/alerts/search", "/api/x/assets", "/api/x/audit", "/api/x/system"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.get_json()["error"]["code"] == "not_logged_in"

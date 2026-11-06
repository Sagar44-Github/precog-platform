"""End-to-end coverage for the bounded, read-only dataset event stream."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import time
import tracemalloc
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]


def wait_for_state(service, states, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = service.status()
        if status["state"] in states:
            return status
        time.sleep(0.01)
    raise AssertionError("pipeline did not reach %s; last status: %r" % (states, service.status()))


def _activate_workspace(logged_in, flask_app, workspace_id):
    manager = flask_app.extensions["precog_workspaces"]
    pipeline = flask_app.extensions["precog_pipeline"]
    pipeline.stop()
    if manager.active.pack_id != "demo-6":
        manager.activate("demo-6")
    response = logged_in.post("/api/x/workspaces/%s/activate" % workspace_id, json={"confirm": True})
    assert response.status_code == 200, response.get_data(as_text=True)


@pytest.fixture
def active_synthetic(logged_in, flask_app):
    _activate_workspace(logged_in, flask_app, "synth-enterprise-30")
    yield logged_in, flask_app
    pipeline = flask_app.extensions["precog_pipeline"]
    manager = flask_app.extensions["precog_workspaces"]
    pipeline.stop()
    if manager.active.pack_id != "demo-6":
        manager.activate("demo-6")


@pytest.fixture
def active_large(logged_in, flask_app):
    _activate_workspace(logged_in, flask_app, "synth-enterprise-300")
    yield logged_in, flask_app
    pipeline = flask_app.extensions["precog_pipeline"]
    manager = flask_app.extensions["precog_workspaces"]
    pipeline.stop()
    if manager.active.pack_id != "demo-6":
        manager.activate("demo-6")


def _run_to_completion(client, flask_app, *, mode="labels", decision_point_limit=0, batch_size=256):
    pipeline = flask_app.extensions["precog_pipeline"]
    pipeline.start(detector_mode=mode, speed=1000, batch_size=batch_size,
                   decision_point_limit=decision_point_limit)
    pipeline._worker.join(30)
    assert not pipeline._worker.is_alive()
    status = pipeline.status()
    assert status["state"] == "finished", status
    return status


def test_pipeline_and_feed_contracts_are_available(logged_in, flask_app):
    status = logged_in.get("/api/x/pipeline")
    assert status.status_code == 200
    assert status.get_json()["workspace_id"] == "demo-6"
    feed = logged_in.get("/api/x/feed").get_json()
    assert "pipeline" in feed["versions"]
    assert feed["versions"]["pipeline"] == flask_app.extensions["precog_pipeline"].revision


def test_viewer_cannot_start_a_stream(client, flask_app):
    login = client.post("/api/x/login", json={"username": "viewer", "password": "test-viewer-password"})
    assert login.status_code == 200
    denied = client.post("/api/x/pipeline/start", json={})
    assert denied.status_code == 403


def test_pipeline_writes_keep_json_and_same_origin_header_checks(logged_in):
    no_json = logged_in.post("/api/x/pipeline/pause", data="{}", content_type="text/plain",
                             headers={"X-Precog-Request": "1"})
    assert no_json.status_code == 415
    no_csrf_header = logged_in.post("/api/x/pipeline/pause", json={}, headers={"X-Precog-Request": "0"})
    assert no_csrf_header.status_code == 403


def test_pipeline_validates_bounds_modes_and_keeps_demo_nids_route(active_synthetic):
    client, flask_app = active_synthetic
    from addons.errors import ApiError
    service = flask_app.extensions["precog_pipeline"]
    for options in ({"batch_size": 10001}, {"speed": 1001}, {"detector_mode": "model"}):
        with pytest.raises(ApiError):
            service.start(**options)
    manager = flask_app.extensions["precog_workspaces"]
    manager.activate("demo-6")
    with pytest.raises(ApiError):
        service.start()


def test_streaming_labels_incidents_forecasts_and_confirmed_counterfactual(active_large):
    client, flask_app = active_large
    pack = flask_app.extensions["precog_workspaces"].active.pack_path
    before = hashlib.sha256((pack / "pack.sqlite").read_bytes()).hexdigest()
    connection = sqlite3.connect("file:%s?mode=ro" % (pack / "pack.sqlite").as_posix(), uri=True)
    try:
        first_technique = connection.execute(
            "SELECT t FROM events WHERE kind='technique' ORDER BY t,event_id LIMIT 1"
        ).fetchone()[0]
        next_attempt = connection.execute(
            "SELECT event_id, src, dst, t FROM events WHERE kind='attempt' AND t >= ? ORDER BY t,event_id LIMIT 1",
            (first_technique,),
        ).fetchone()
    finally:
        connection.close()
    status_response = client.post("/api/x/pipeline/start", json={
        "speed": 1000, "batch_size": 128, "start_t": first_technique, "end_t": next_attempt[3],
    })
    assert status_response.status_code == 202
    service = flask_app.extensions["precog_pipeline"]
    waiting = wait_for_state(service, {"waiting_for_decision"})
    assert waiting["decision_point"]["event_id"] == next_attempt[0]
    assert waiting["decision_point"]["to_host"] == next_attempt[2]
    forecast = flask_app.extensions["precog"]["world"].current_forecast()
    proposal = client.post("/api/x/containment/propose", json={
        "target_host": next_attempt[2], "forecast_id": forecast["forecast_id"], "requested_by": "console",
    })
    assert proposal.status_code == 200, proposal.get_data(as_text=True)
    action_id = proposal.get_json()["action_id"]
    confirmed = client.post("/api/x/containment/confirm", json={"action_id": action_id})
    assert confirmed.status_code == 200, confirmed.get_data(as_text=True)
    service._worker.join(30)
    assert not service._worker.is_alive()
    final = service.status()
    assert final["state"] == "finished"
    assert final["blocked_events"] >= 1
    assert final["recent_counterfactual"][-1]["result"] == "blocked"
    assert final["simulation_note"] == "Simulated what-if on recorded data. Recorded events are immutable."
    assert any(item["status"] == "executed" for item in flask_app.extensions["precog"]["world"].actions())
    assert flask_app.extensions["precog"]["world"].forecasts()
    incidents = flask_app.extensions["precog"]["hooks"].require("incidents").snapshot_records()
    assert incidents
    assert any(event["source"] == "recorded_counterfactual" for event in flask_app.extensions["precog"]["world"].alerts(200))
    after = hashlib.sha256((pack / "pack.sqlite").read_bytes()).hexdigest()
    assert after == before
    state_response = client.get("/api/x/state")
    assert len(state_response.data) <= 200 * 1024


def test_graph_novelty_is_distinct_from_trivial_label_playback(active_synthetic):
    client, flask_app = active_synthetic
    status = _run_to_completion(client, flask_app, mode="graph-novelty", batch_size=512)
    alerts = flask_app.extensions["precog"]["world"].alerts(200)
    assert status["alerts"] > 0
    assert alerts
    assert {item["source"] for item in alerts} == {"graph_novelty"}
    assert "20% warm-up" in status["detector_note"]


@pytest.mark.parametrize("workspace_id", ("synth-enterprise-120", "synth-datacenter-300"))
def test_additional_installed_workspaces_run_to_completion(logged_in, flask_app, workspace_id):
    manager = flask_app.extensions["precog_workspaces"]
    pipeline = flask_app.extensions["precog_pipeline"]
    pipeline.stop()
    if manager.active.pack_id != "demo-6":
        manager.activate("demo-6")
    activated = logged_in.post("/api/x/workspaces/%s/activate" % workspace_id, json={"confirm": True})
    assert activated.status_code == 200, activated.get_data(as_text=True)
    expected_events = manager.active.manifest["counts"]["events"]
    try:
        status = _run_to_completion(logged_in, flask_app, mode="labels", batch_size=512)
        assert status["state"] == "finished", status
        assert status["processed_events"] == expected_events
        assert status["alerts"] > 0
        assert status["simulation_note"]
    finally:
        pipeline.stop()
        manager.activate("demo-6")


def test_recorded_whatif_playbook_and_action_use_the_same_counterfactual_rule(active_synthetic):
    client, flask_app = active_synthetic
    assert flask_app.extensions["precog_lab"].dataset_context.pack_id == "synth-enterprise-30"
    graph = flask_app.extensions["precog"]["hooks"].require("graph")
    source = graph.topology.host_ids()[0]
    target = graph.topology.connections(source)[0]
    graph.mark_compromised(source)
    forecast = flask_app.extensions["precog"]["hooks"].require("precog").on_compromise(source)
    whatif = client.post("/api/x/whatif", json={
        "from_host": source, "host_states": {}, "contain_hosts": [target],
    })
    assert whatif.status_code == 200, whatif.get_data(as_text=True)
    assert "simulated what-if on recorded data" in whatif.get_json()["basis"]
    governance = flask_app.extensions["precog_governance"]
    preview = governance.preview("contain-host", "analyst", host_id=target, forecast_id=forecast["forecast_id"])
    assert any("simulated what-if on recorded data" in text for text in preview["side_effects"])
    proposed = client.post("/api/x/containment/propose", json={
        "target_host": target, "forecast_id": forecast["forecast_id"], "requested_by": "console",
    })
    assert proposed.status_code == 200, proposed.get_data(as_text=True)
    confirmed = client.post("/api/x/containment/confirm", json={"action_id": proposed.get_json()["action_id"]})
    assert confirmed.status_code == 200, confirmed.get_data(as_text=True)
    assert "simulated what-if on recorded data" in confirmed.get_json()["result"]


def test_identical_streams_reproduce_normalized_events_forecasts_and_incidents(active_synthetic):
    client, flask_app = active_synthetic
    normalized = []
    for _ in range(2):
        _run_to_completion(client, flask_app, mode="labels", batch_size=777)
        world = flask_app.extensions["precog"]["world"]
        incidents = flask_app.extensions["precog"]["hooks"].require("incidents").snapshot_records()
        normalized.append({
            "alerts": [(item["event_id"], item["host"], item["source"], item["technique_id"]) for item in world.alerts(200)],
            "forecasts": [(item["forecast_id"], item["from_host"], item["targets"], item["status"], item["outcome"]) for item in world.forecasts()],
            "incidents": [(item["incident_id"], item["alert_ids"], item["affected_hosts"], item["compromised_hosts"]) for item in incidents],
        })
    assert normalized[0] == normalized[1]


def _make_100k_pack(source_pack, target, contracts_dir):
    from addons.dataset_packs import _payload_hash, validate_pack

    shutil.copytree(source_pack, target)
    db = target / "pack.sqlite"
    connection = sqlite3.connect(db)
    source, destination = connection.execute("SELECT src,dst FROM edges WHERE edge_kind='feasible' LIMIT 1").fetchone()
    initial = [(1, 0, None, destination, "technique", "HIGH", "simulated-initial-access", "simulated-access", "TCP", 443, 512,
                json.dumps({"simulated": True}, separators=(",", ":"))),
               (2, 1, source, destination, "attempt", "HIGH", "simulated-lateral-movement", "simulated-lateral-movement", "TCP", 443, 512,
                json.dumps({"simulated": True}, separators=(",", ":")))]
    try:
        connection.execute("DELETE FROM events")
        connection.execute("DELETE FROM labels")
        connection.executemany("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", initial)
        connection.executemany("INSERT INTO labels(event_id,label,provenance) VALUES(?,?,?)", [
            (1, "simulated-initial-access", "native-generated-simulation"),
            (2, "simulated-lateral-movement", "native-generated-simulation"),
        ])
        row = (None, 2, source, destination, "traffic", "NORMAL", None, None, "TCP", 443, 256,
               json.dumps({"simulated": True, "traffic_class": "generated-background"}, separators=(",", ":")))
        connection.executemany("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (tuple([index] + list(row[1:])) for index in range(3, 100001)))
        connection.commit()
    finally:
        connection.close()
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["id"] = target.name
    manifest["name"] = "100,000-event bounded stream fixture"
    manifest["counts"].update(events=100000, labelled_events=2, time_span_ms=99999)
    digest, size = _payload_hash(target)
    manifest["content_hash"], manifest["size_bytes"] = digest, size
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    validate_pack(target, contracts_dir)
    return target


def test_100k_event_pack_stays_batched_under_memory_and_payload_budgets(logged_in, flask_app, tmp_path):
    from addons.dataset_packs import PackStore

    manager = flask_app.extensions["precog_workspaces"]
    pipeline = flask_app.extensions["precog_pipeline"]
    pipeline.stop()
    original_store = manager.store
    manager.activate("demo-6")
    root = tmp_path / "packs"
    root.mkdir()
    source = REPO_ROOT / "packs" / "synth-enterprise-300"
    target = _make_100k_pack(source, root / "synth-scale-100k", flask_app.extensions["precog"]["config"].contracts_dir)
    manager.store = PackStore(root, flask_app.extensions["precog"]["config"].contracts_dir)
    activated = logged_in.post("/api/x/workspaces/synth-scale-100k/activate", json={"confirm": True})
    assert activated.status_code == 200, activated.get_data(as_text=True)
    tracemalloc.start()
    started = time.monotonic()
    pipeline.start(speed=1000, batch_size=1000, decision_point_limit=0, detector_mode="labels")
    pipeline._worker.join(60)
    elapsed = time.monotonic() - started
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert not pipeline._worker.is_alive()
    status = pipeline.status()
    assert status["state"] == "finished", status
    assert status["processed_events"] == 100000
    assert status["total_events"] == 100000
    assert status["alerts"] == 2
    assert peak < 150 * 1024 * 1024
    assert elapsed < 60
    payload_bytes = len(logged_in.get("/api/x/state").data)
    assert payload_bytes <= 200 * 1024
    assert status["batch_size"] == 1000
    print("D4_SCALE events=%d batch=%d elapsed_seconds=%.3f tracemalloc_peak_bytes=%d state_payload_bytes=%d" %
          (status["processed_events"], status["batch_size"], elapsed, peak, payload_bytes))
    # Restore the production pack store before returning to demo-6.
    manager.store = original_store
    manager.activate("demo-6")

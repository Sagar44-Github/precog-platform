"""The golden path through the REAL backend, REAL routes and every REAL role package (skipped until all of them are merged)."""
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from addons.loader import ROLE_PACKAGES, AddonContext, _load_role_packages

REPO = Path(__file__).resolve().parents[3]


def real(package, attribute):
    try:
        return hasattr(__import__(package), attribute)
    except ImportError:
        return False


def all_real():
    return real("detect_events", "EventProcessor") and real("graph_net", "LiveGraph") and real("graph_replay", "ReplayController") and real("viz_containment", "ContainmentService") and real("precog_engine", "PrecogEngine")


@pytest.fixture()
def stack(flask_app, monkeypatch):
    """Other tests in this folder empty the shared hooks, so register every role package again on the same app."""
    if not all_real():     # checked here, after the app was made, because making the app puts the role folders on Python's search path
        pytest.skip("DETECT, GRAPH, VIZ and Precog are not all merged yet")
    monkeypatch.setenv("PUSH_WATCHER", "0")
    monkeypatch.setenv("DATA_MODE", "live")
    shared = flask_app.extensions["precog"]
    context = AddonContext(shared["world"], shared["hooks"], shared["config"], shared["contracts"], shared["nids"], flask_app)
    shared["hooks"]._items.clear()
    _load_role_packages(context, ROLE_PACKAGES)
    replay = shared["hooks"].get("replay")
    replay.settle_seconds = 0
    shared["world"].reset()
    yield shared
    replay.stop()
    shared["hooks"].get("containment").shutdown()


def poll(client, condition, timeout=30.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        state = client.get("/api/x/state").get_json()
        if condition(state):
            return state
        time.sleep(0.005)
    raise AssertionError("timed out waiting for the condition; last replay state: %s" % client.get("/api/x/replay/status").get_json())


def start(client):
    reply = client.post("/api/x/replay/start", json={"scenario_id": "golden-path", "speed": 40})
    assert reply.status_code == 200, reply.get_json()
    return poll(client, lambda s: s["replay"]["state"] == "waiting_for_decision" and s["forecast"] is not None)


def test_every_part_is_registered(stack):
    for name in ("events", "graph", "replay", "containment", "precog", "push"):
        assert stack["hooks"].has(name), name


def test_the_golden_path_with_containment(logged_in, stack):
    state = start(logged_in)
    forecast = state["forecast"]
    assert forecast["targets"][0]["host_id"] == "server-b" and 1 <= len(forecast["targets"]) <= 3
    assert [h["state"] for h in state["graph"]["hosts"] if h["host_id"] == "host-a"] == ["compromised"]
    assert any(a["source"] == "nids_detector" and a["severity"] == "HIGH" for a in state["alerts"])
    propose = logged_in.post("/api/x/containment/propose", json={"target_host": "server-b", "forecast_id": forecast["forecast_id"], "requested_by": "mobile"})
    assert propose.status_code == 200 and propose.get_json()["status"] == "pending_confirmation"
    assert logged_in.get("/api/x/graph").get_json()["hosts"][2]["state"] == "normal"              # nothing changed yet
    confirm = logged_in.post("/api/x/containment/confirm", json={"action_id": propose.get_json()["action_id"]})
    assert confirm.status_code == 200 and confirm.get_json()["status"] == "executed"
    final = poll(logged_in, lambda s: s["replay"]["state"] == "finished")
    hosts = {h["host_id"]: h["state"] for h in final["graph"]["hosts"]}
    assert hosts["server-b"] == "contained" and final["graph"]["compromised_path"] == ["host-a"]
    assert any("was blocked" in a["explanation"] and "Web Server B" in a["explanation"] for a in final["alerts"])
    resolved = [f for f in logged_in.get("/api/x/forecasts").get_json() if f["status"] == "hit"]
    assert len(resolved) == 1 and resolved[0]["outcome"] == {"attempted_host": "server-b", "rank_hit": 1, "blocked": True}
    metrics = logged_in.get("/api/x/metrics/precog").get_json()
    assert (metrics["forecasts_resolved"], metrics["hits"], metrics["hit_rate"], metrics["precision_at_1"], metrics["containment_success_rate"]) == (1, 1, 1.0, 1.0, 1.0)
    poll(logged_in, lambda s: any("ended early" in (a["result"] or "") for a in s["actions"]), timeout=5)       # the re-evaluation watcher checks every 0.1 s
    sessions = logged_in.get("/api/x/sessions").get_json()
    assert sessions[0]["ended_at"] and sessions[0]["scenario_id"] == "golden-path" and sessions[0]["forecasts"][0]["status"] == "hit"


def test_the_golden_path_without_containment_lets_the_attacker_through_and_forecasts_again(logged_in, stack):
    start(logged_in)
    assert logged_in.post("/api/x/replay/resume").status_code == 200
    final = poll(logged_in, lambda s: s["replay"]["state"] == "finished")
    assert final["graph"]["compromised_path"] == ["host-a", "server-b"]
    metrics = logged_in.get("/api/x/metrics/precog").get_json()
    assert metrics["forecasts_resolved"] == 1 and metrics["hits"] == 1 and metrics["containment_success_rate"] is None
    forecasts = logged_in.get("/api/x/forecasts").get_json()
    assert forecasts[0]["outcome"]["blocked"] is False and forecasts[-1]["from_host"] == "server-b"      # a new forecast from the new host


def test_the_audit_log_has_detections_forecasts_and_containments(logged_in, stack):
    state = start(logged_in)
    action = logged_in.post("/api/x/containment/propose", json={"target_host": "server-b", "forecast_id": state["forecast"]["forecast_id"], "requested_by": "console"}).get_json()
    logged_in.post("/api/x/containment/confirm", json={"action_id": action["action_id"]})
    poll(logged_in, lambda s: s["replay"]["state"] == "finished")
    lines = [json.loads(l) for l in (REPO / "lead-core" / "backend" / "data" / "audit" / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {"detection", "forecast", "containment"} <= {l["type"] for l in lines}


def test_timing_budgets_hold(logged_in, stack):
    """NFR-PERF: the server side of 'event to result' must leave room for the 1.5 s polling delay inside the 3 s budget."""
    logged_in.post("/api/x/replay/start", json={"scenario_id": "golden-path", "speed": 1})
    seen = {}
    end = time.monotonic() + 20
    while "forecast" not in seen and time.monotonic() < end:
        state = logged_in.get("/api/x/state").get_json()
        now = time.monotonic()
        if "compromised" not in seen and [h["state"] for h in state["graph"]["hosts"] if h["host_id"] == "host-a"] == ["compromised"]:
            seen["compromised"] = now
        if "forecast" not in seen and state["forecast"] is not None:
            seen["forecast"] = now
        time.sleep(0.002)
    assert "forecast" in seen, "no forecast appeared"
    forecast_delay = seen["forecast"] - seen["compromised"]
    assert forecast_delay < 1.0, "compromise to forecast took %.3f s" % forecast_delay
    poll(logged_in, lambda s: s["replay"]["state"] == "waiting_for_decision")
    action = logged_in.post("/api/x/containment/propose", json={"target_host": "server-b", "forecast_id": None, "requested_by": "mobile"}).get_json()
    began = time.monotonic()
    logged_in.post("/api/x/containment/confirm", json={"action_id": action["action_id"]})
    poll(logged_in, lambda s: any(a["status"] == "executed" for a in s["actions"]))
    assert time.monotonic() - began < 1.0
    logged_in.post("/api/x/replay/restart")


def test_the_golden_path_script_passes_and_writes_the_rehearsal_log(stack, tmp_path):
    log = tmp_path / "rehearsals.csv"
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(REPO / "lead-core" / "backend")]))
    result = subprocess.run([sys.executable, str(REPO / "lead-core" / "integration" / "golden_path.py"), "--runs", "2", "--speed", "40", "--log", str(log)],
                            capture_output=True, text=True, env=env, timeout=240, cwd=str(REPO))
    assert result.returncode == 0, result.stdout[-2500:] + result.stderr[-1500:]
    rows = list(csv.reader(log.read_text(encoding="utf-8").splitlines()))
    assert rows[0][2] == "result" and [r[2] for r in rows[1:]] == ["PASS", "PASS"]
    assert "consecutive successes at the end: 2 of 2 runs" in result.stdout

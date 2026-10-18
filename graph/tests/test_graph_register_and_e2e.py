"""GRAPH through the real add-on loader, and the golden path through the REAL NIDS detector, REAL live graph and (if merged) REAL DETECT."""
import time
import types

import pytest
from flask import Flask

from addons.loader import register_addons
from graph_helpers import REPO_ROOT


def real_detect_available():
    try:
        import detect_events

        return hasattr(detect_events, "EventProcessor")
    except ImportError:
        return False


@pytest.fixture()
def live(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_MODE", "live")
    monkeypatch.setenv("WEB_DIST", str(tmp_path / "no-web"))
    monkeypatch.setenv("REPLAY_DECISION_TIMEOUT", "5")
    return Flask(__name__)


def test_graph_registers_without_nids_but_replay_reports_why_not(live):
    ctx = register_addons(live, REPO_ROOT, types.SimpleNamespace(), packages=("graph_replay", "graph_net"))
    report = live.extensions["precog"]["load_report"]
    assert report["graph_net"] == "registered" and report["graph_replay"].startswith("error") and "NIDS" in report["graph_replay"]
    assert ctx.hooks.has("graph") and not ctx.hooks.has("replay")


def test_live_mode_publishes_the_empty_graph_and_sample_mode_keeps_the_sample(monkeypatch, tmp_path):
    monkeypatch.setenv("WEB_DIST", str(tmp_path / "no-web"))
    monkeypatch.setenv("DATA_MODE", "live")
    ctx = register_addons(Flask(__name__), REPO_ROOT, types.SimpleNamespace(), packages=("graph_net",))
    assert {h["state"] for h in ctx.world.graph()["hosts"]} == {"normal"}
    monkeypatch.setenv("DATA_MODE", "sample")
    ctx = register_addons(Flask(__name__), REPO_ROOT, types.SimpleNamespace(), packages=("graph_net",))
    assert ctx.world.graph()["compromised_path"] == ["host-a"]


@pytest.fixture(scope="module")
def nids():
    from database.models import Packet, SessionLocal, init_db

    init_db()
    from pathlib import Path

    model = REPO_ROOT / "lead-core" / "backend" / "nids" / "ml" / "nids_model.pkl"
    if not model.is_file():
        from ml.train_model import train_and_evaluate

        train_and_evaluate()
    return types.SimpleNamespace(SessionLocal=SessionLocal, Packet=Packet)


def test_replay_registers_with_real_nids(live, nids):
    ctx = register_addons(live, REPO_ROOT, nids, packages=("graph_replay", "graph_net"))
    assert ctx.hooks.has("replay") and ctx.hooks.has("graph")
    assert {s["scenario_id"] for s in ctx.hooks.get("replay").list_scenarios()} == {"direct-hit", "golden-path", "lateral-spread", "quiet-scan"}


@pytest.mark.skipif(not real_detect_available(), reason="DETECT's real package is not merged yet")
def test_golden_path_through_real_nids_real_detect_and_real_graph(live, nids):
    ctx = register_addons(live, REPO_ROOT, nids, packages=("detect_events", "graph_replay", "graph_net"))
    replay = ctx.hooks.get("replay")
    replay.settle_seconds = 0
    replay.start("golden-path", 60.0)
    end = time.monotonic() + 20
    while replay.status()["state"] != "waiting_for_decision" and time.monotonic() < end:
        time.sleep(0.01)
    assert replay.status()["state"] == "waiting_for_decision"
    graph = ctx.hooks.get("graph")
    assert graph.host_state("host-a") == "compromised"
    alerts = ctx.world.alerts(50)
    from_nids = [a for a in alerts if a["source"] == "nids_detector"]
    assert from_nids and all(a["severity"] == "HIGH" for a in from_nids)        # NIDS's real detector flagged the suspicious ports
    assert {a["technique_id"] for a in from_nids} >= {"T1021.004", "T1021.002"}   # DETECT's port hints
    assert any(a["source"] == "scripted" and a["technique_id"] == "T1110" for a in alerts)
    graph.set_host_state("server-b", "contained")                                  # what VIZ's containment will do
    ctx.world.upsert_action({"action_id": "act-000001", "target_host": "server-b", "forecast_id": None, "requested_by": "mobile",
                             "status": "executed", "proposed_at": "2026-10-03T10:00:05Z", "confirmed_at": "2026-10-03T10:00:06Z", "result": None})
    assert replay.wait_until_done(20) and replay.last_error is None
    assert any("was blocked" in a["explanation"] and "Web Server B" in a["explanation"] for a in ctx.world.alerts(50))
    assert len(ctx.world.sessions()) == 1 and ctx.world.sessions()[0]["ended_at"]
    assert ctx.world.replay()["state"] == "finished"
    replay.stop()

"""VIZ through the real add-on loader, and the golden path with REAL containment (plus real NIDS, DETECT and GRAPH when merged)."""
import time
import types

import pytest
from flask import Flask

from addons.loader import register_addons
from viz_helpers import REPO_ROOT


def real(package, attribute):
    try:
        module = __import__(package)
        return hasattr(module, attribute)
    except ImportError:
        return False


@pytest.fixture()
def live(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_MODE", "live")
    monkeypatch.setenv("WEB_DIST", str(tmp_path / "no-web"))
    monkeypatch.setenv("PUSH_WATCHER", "0")
    monkeypatch.setenv("CONTAINMENT_CONFIRM_SECONDS", "7")
    monkeypatch.setenv("REPLAY_DECISION_TIMEOUT", "10")
    monkeypatch.delenv("FCM_PROJECT_ID", raising=False)
    return Flask(__name__)


def test_viz_registers_the_containment_and_push_hooks(live):
    ctx = register_addons(live, REPO_ROOT, types.SimpleNamespace(), packages=("viz_containment",))
    assert live.extensions["precog"]["load_report"]["viz_containment"] == "registered"
    assert ctx.hooks.has("containment") and ctx.hooks.has("push")
    assert ctx.hooks.get("containment").confirm_seconds == 7.0
    ctx.hooks.get("push").register("some-token")


def test_the_push_watcher_starts_unless_switched_off(live, monkeypatch):
    import threading

    monkeypatch.setenv("PUSH_WATCHER", "1")
    before = sum(1 for t in threading.enumerate() if t.name == "push-watcher")
    register_addons(live, REPO_ROOT, types.SimpleNamespace(), packages=("viz_containment",))
    assert sum(1 for t in threading.enumerate() if t.name == "push-watcher") == before + 1


def test_the_api_routes_reach_viz_containment(live):
    """propose and confirm through the lead's real /api/x routes (a stand-in graph; a logged-in session is faked)."""
    from viz_helpers import FakeGraph

    ctx = register_addons(live, REPO_ROOT, types.SimpleNamespace(), packages=("viz_containment",))
    ctx.hooks.register("graph", FakeGraph())
    service = ctx.hooks.get("containment")
    action = service.propose(ctx.world, "server-b", None, "console")
    assert ctx.world.actions()[0]["status"] == "pending_confirmation"
    assert service.confirm(ctx.world, action["action_id"])["status"] == "executed"


@pytest.fixture(scope="module")
def nids():
    from database.models import Packet, SessionLocal, init_db

    init_db()
    if not (REPO_ROOT / "lead-core" / "backend" / "nids" / "ml" / "nids_model.pkl").is_file():
        from ml.train_model import train_and_evaluate

        train_and_evaluate()
    return types.SimpleNamespace(SessionLocal=SessionLocal, Packet=Packet)


@pytest.mark.skipif(not (real("detect_events", "EventProcessor") and real("graph_net", "LiveGraph") and real("graph_replay", "ReplayController")),
                    reason="DETECT's and GRAPH's real packages are not merged yet")
def test_golden_path_with_real_containment(live, nids):
    ctx = register_addons(live, REPO_ROOT, nids, packages=("detect_events", "graph_replay", "graph_net", "viz_containment"))
    replay, graph, containment = ctx.hooks.get("replay"), ctx.hooks.get("graph"), ctx.hooks.get("containment")
    replay.settle_seconds = 0
    replay.start("golden-path", 60.0)
    end = time.monotonic() + 20
    while replay.status()["state"] != "waiting_for_decision" and time.monotonic() < end:
        time.sleep(0.01)
    assert replay.status()["state"] == "waiting_for_decision"
    action = containment.propose(ctx.world, "server-b", None, "mobile")                 # the phone taps Contain
    assert graph.host_state("server-b") == "normal" and replay.status()["state"] == "waiting_for_decision"
    containment.confirm(ctx.world, action["action_id"])                                  # the phone slides to confirm
    assert replay.wait_until_done(20) and replay.last_error is None
    assert replay.last_decision == "executed"
    assert graph.host_state("server-b") == "contained" and graph.snapshot()["compromised_path"] == ["host-a"]
    assert any("was blocked" in a["explanation"] and "Web Server B" in a["explanation"] for a in ctx.world.alerts(50))
    assert ctx.world.actions()[0]["status"] == "executed"
    replay.stop()
    containment.shutdown()

"""DETECT through the real add-on loader, with a bare Flask app (no NIDS needed)."""
import json
import types

import pytest
from flask import Flask

from addons.hooks import Hooks
from addons.loader import register_addons
from detect_helpers import REPO_ROOT, packet


@pytest.fixture()
def booted(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_MODE", "live")
    monkeypatch.setenv("WEB_DIST", str(tmp_path / "no-web"))
    app = Flask(__name__)
    ctx = register_addons(app, REPO_ROOT, types.SimpleNamespace(), packages=("detect_events",))
    return app, ctx


def test_register_adds_the_events_hook(booted):
    app, ctx = booted
    assert ctx.hooks.has("events")
    assert app.extensions["precog"]["load_report"] == {"detect_events": "registered"}
    health = app.test_client().get("/api/x/health").get_json()
    assert "events" in health["hooks"] and health["modules"]["detect_events"] == "registered"


def test_hooked_processor_feeds_the_shared_world_state(booted):
    _, ctx = booted
    events = ctx.hooks.get("events").process_packets([packet()])
    assert ctx.world.alerts()[0]["event_id"] == events[0]["event_id"]
    ctx.hooks.get("events").process_technique("host-a", "T1110", compromise=True)
    assert len(ctx.world.alerts()) == 2


def test_live_mode_without_a_report_file_keeps_going(booted):
    _, ctx = booted
    # no detect/offline_model/results/detection_report.json is needed for the server to start
    assert ctx.world.detection_report() is None or isinstance(ctx.world.detection_report(), dict)


def test_live_mode_loads_a_valid_report(monkeypatch, tmp_path):
    results = tmp_path / "repo" / "detect" / "offline_model" / "results"
    results.mkdir(parents=True)
    report = json.loads((REPO_ROOT / "contracts" / "samples" / "detection_report.sample.json").read_text(encoding="utf-8"))
    report["model"] = "From a results file"
    (results / "detection_report.json").write_text(json.dumps(report), encoding="utf-8")
    # a copy of just enough of the repo layout: contracts and detect_events data
    import shutil
    shutil.copytree(REPO_ROOT / "contracts", tmp_path / "repo" / "contracts")
    monkeypatch.setenv("DATA_MODE", "live")
    monkeypatch.setenv("WEB_DIST", str(tmp_path / "no-web"))
    app = Flask(__name__)
    ctx = register_addons(app, tmp_path / "repo", types.SimpleNamespace(), packages=("detect_events",))
    assert ctx.world.detection_report()["model"] == "From a results file"


def test_a_broken_report_does_not_stop_the_server(monkeypatch, tmp_path):
    results = tmp_path / "repo" / "detect" / "offline_model" / "results"
    results.mkdir(parents=True)
    (results / "detection_report.json").write_text('{"model": "incomplete"}', encoding="utf-8")
    import shutil
    shutil.copytree(REPO_ROOT / "contracts", tmp_path / "repo" / "contracts")
    monkeypatch.setenv("DATA_MODE", "live")
    monkeypatch.setenv("WEB_DIST", str(tmp_path / "no-web"))
    app = Flask(__name__)
    ctx = register_addons(app, tmp_path / "repo", types.SimpleNamespace(), packages=("detect_events",))
    assert ctx.hooks.has("events") and ctx.world.detection_report() is None


def test_sample_mode_keeps_the_sample_report(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_MODE", "sample")
    monkeypatch.setenv("WEB_DIST", str(tmp_path / "no-web"))
    app = Flask(__name__)
    ctx = register_addons(app, REPO_ROOT, types.SimpleNamespace(), packages=("detect_events",))
    assert ctx.world.detection_report()["dataset"] == "CICIDS2017" and "Sample" in ctx.world.detection_report()["notes"]


def test_the_audit_file_goes_into_the_ignored_data_folder(booted):
    _, ctx = booted
    ctx.hooks.get("events").process_packets([packet()])
    audit_file = REPO_ROOT / "lead-core" / "backend" / "data" / "audit" / "audit.jsonl"
    assert audit_file.is_file()
    ctx.hooks.get("events").reset()
    assert not audit_file.exists()

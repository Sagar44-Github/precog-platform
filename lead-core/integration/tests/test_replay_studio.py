"""C2 scenario validation, replay controls, snapshots, roles, and run history."""
from copy import deepcopy
import json
from pathlib import Path
import time

import pytest

from addons.loader import AddonContext, ROLE_PACKAGES, _load_role_packages
from addons.replay_studio import ReplayStudio


@pytest.fixture()
def studio_env(flask_app, ctx, tmp_path, monkeypatch):
    monkeypatch.setenv("PUSH_WATCHER", "0")
    hooks = ctx["hooks"]
    required = {"events", "graph", "replay", "precog", "containment", "incidents", "studio"}
    if not required.issubset(set(hooks.registered())):
        hooks._items.clear()
        context = AddonContext(ctx["world"], hooks, ctx["config"], ctx["contracts"], ctx["nids"], flask_app)
        _load_role_packages(context, ROLE_PACKAGES)
    replay = hooks.require("replay")
    replay.stop()
    replay.settle_seconds = 0
    replay.decision_timeout = 2
    studio = hooks.require("studio")
    studio.scenarios_dir = tmp_path / "scenarios"
    studio.runs_dir = tmp_path / "runs"
    studio._runs.clear()
    studio._active = None
    studio._revision = 0
    studio._snapshots.clear()
    yield studio
    replay.stop()


def scenario(identifier="user-c2-check"):
    return {
        "scenario_id": identifier,
        "description": "Two scripted events for replay studio acceptance.",
        "events": [
            {"seq": 1, "offset_ms": 0, "kind": "technique", "host": "host-a", "technique_id": "T1046", "note": "Discovery"},
            {"seq": 2, "offset_ms": 1000, "kind": "traffic", "packets": [
                {"src_host": "host-a", "dst_host": "host-b", "protocol": "TCP", "dst_port": 22, "size": 500, "repeat": 1},
            ]},
        ],
    }


def test_library_merges_shipped_and_saved_user_scenarios(studio_env):
    studio = studio_env
    before = {item["scenario_id"] for item in studio.scenarios()}
    assert {"golden-path", "direct-hit", "lateral-spread", "quiet-scan"} <= before
    saved = studio.save_scenario(scenario())
    assert saved["source"] == "user" and saved["editable"] is True
    assert "user-c2-check" in {item["scenario_id"] for item in studio.scenarios()}
    file_path = studio.scenarios_dir / "user-c2-check.json"
    assert json.loads(file_path.read_text(encoding="utf-8"))["scenario_id"] == "user-c2-check"


def test_saved_scenario_reloads_and_can_be_deleted(studio_env):
    studio = studio_env
    studio.save_scenario(scenario("user-reload-check"))
    reloaded = ReplayStudio(studio.ctx, studio.replay)
    reloaded.scenarios_dir = studio.scenarios_dir
    reloaded._load_user_scenarios()
    assert reloaded.get_scenario("user-reload-check")["scenario"]["scenario_id"] == "user-reload-check"
    reloaded.delete_scenario("user-reload-check")
    assert not (studio.scenarios_dir / "user-reload-check.json").exists()
    assert reloaded.get_scenario("user-reload-check") is None
    studio.replay.attach_studio(studio)


def test_path_like_scenario_ids_are_rejected(studio_env):
    with pytest.raises(ValueError, match="start with user-"):
        studio_env.save_scenario(scenario("../outside"))
    with pytest.raises(ValueError, match="user- id"):
        studio_env.delete_scenario("user-..-..-outside")


def test_validation_reports_schema_host_technique_order_port_and_size_errors(studio_env):
    studio = studio_env
    data = scenario()
    data["events"][0]["host"] = "192.0.2.99"
    data["events"][0]["technique_id"] = "T9999"
    data["events"][0]["offset_ms"] = 100
    data["events"][1]["offset_ms"] = 0
    data["events"][1]["packets"][0]["dst_port"] = 70000
    errors = studio.validate(data)
    assert errors["valid"] is False
    paths = {item["path"] for item in errors["errors"]}
    assert "$.events[0].host" in paths
    assert "$.events[0].technique_id" in paths
    assert "$.events[1].packets[0].dst_port" in paths
    assert any("offset_ms" in path for path in paths)

    too_many = scenario()
    too_many["events"] = [dict(too_many["events"][0], seq=index + 1, offset_ms=index) for index in range(201)]
    assert any(item["code"] == "event_limit" for item in studio.validate(too_many)["errors"])
    too_long = scenario()
    too_long["events"][0]["offset_ms"] = 7_200_001
    assert any(item["code"] in ("duration_limit", "schema") for item in studio.validate(too_long)["errors"])


def test_dry_run_is_pure_and_produces_estimated_host_states(studio_env, ctx):
    studio = studio_env
    before_version = ctx["world"].version
    before_graph = deepcopy(ctx["hooks"].require("graph").snapshot())
    before_incidents = ctx["hooks"].require("incidents").checkpoint_state()
    before_forecasts = ctx["world"].forecasts()
    before_actions = ctx["world"].actions()
    result = studio.dry_run(json.loads((Path(__file__).resolve().parents[3] / "graph" / "graph_replay" / "scenarios" / "golden-path.json").read_text(encoding="utf-8")))
    assert result["host_states"]["host-a"] == "compromised"
    assert result["forecasts"]
    assert result["forecasts"][0]["targets"]
    assert "does not change live state" in result["basis"]
    assert ctx["world"].version == before_version
    assert ctx["hooks"].require("graph").snapshot() == before_graph
    assert ctx["hooks"].require("incidents").checkpoint_state() == before_incidents
    assert ctx["world"].forecasts() == before_forecasts and ctx["world"].actions() == before_actions


def test_studio_steps_back_restores_world_then_finishes_deterministically(studio_env, logged_in, ctx):
    studio = studio_env
    replay = studio.replay
    replay.start("quiet-scan", 1, paused=True)
    first = replay.step()
    assert first["state"] == "paused" and first["position"] == 1
    after_first = deepcopy(ctx["world"].alerts())
    assert len(after_first) == 1
    second = replay.step()
    assert second["state"] == "paused" and second["position"] == 2
    replay.step_back()
    assert replay.status()["position"] == 1
    assert len(ctx["world"].alerts()) == 1
    replay.step()
    assert replay.status()["position"] == 2
    assert ctx["world"].alerts()[0]["event_id"] == "evt-000004"
    assert replay.set_speed(8)["speed"] == 8
    assert replay.set_breakpoints([3]) == [3]
    assert replay.set_breakpoints([]) == []
    replay.resume()
    assert replay.wait_until_done(5)
    assert replay.status()["state"] == "finished"
    assert studio.list_runs()[0]["status"] == "finished"
    assert len(studio.get_snapshot(studio.list_runs()[0]["run_id"])) == 4
    assert studio.runs_dir.joinpath(studio.list_runs()[0]["run_id"] + ".json").is_file()

    replay.start("quiet-scan", 1)
    assert replay.wait_until_done(5)
    runs = studio.list_runs()
    result = studio.compare(runs[1]["run_id"], runs[0]["run_id"])
    assert result["identical"] is True
    assert result["changes"]["outcome"] == {"left": "completed", "right": "completed"}
    assert all(not value.get("added") and not value.get("removed") for key, value in result["changes"].items() if key != "metrics")


def test_breakpoints_validate_event_sequences_and_studio_speed(studio_env):
    replay = studio_env.replay
    replay.start("quiet-scan", 1, paused=True)
    assert replay.set_breakpoints([2]) == [2]
    with pytest.raises(Exception, match="breakpoint"):
        replay.set_breakpoints([99])
    with pytest.raises(Exception, match="0.25x and 8x"):
        replay.set_speed(8.1)
    replay.stop()


def test_scenario_routes_validate_save_and_enforce_viewer_role(studio_env, logged_in, flask_app, tmp_path):
    catalog = logged_in.get("/api/x/scenarios")
    assert catalog.status_code == 200 and len(catalog.get_json()["items"]) >= 4
    options = logged_in.get("/api/x/scenarios/options")
    assert options.status_code == 200 and "host-a" in {item["host_id"] for item in options.get_json()["hosts"]}
    valid = logged_in.post("/api/x/scenarios/validate", json={"scenario": scenario()})
    assert valid.status_code == 200 and valid.get_json()["valid"] is True
    dry = logged_in.post("/api/x/scenarios/dry-run", json={"scenario": scenario()})
    assert dry.status_code == 200 and dry.get_json()["host_states"]["host-a"] == "normal"
    saved = logged_in.post("/api/x/scenarios", json={"scenario": scenario()})
    assert saved.status_code == 201

    viewer = flask_app.test_client()
    assert viewer.post("/api/x/login", json={"username": "viewer", "password": "test-viewer-password"}).status_code == 200
    headers = {"X-Precog-Request": "1"}
    assert viewer.post("/api/x/scenarios/validate", json={"scenario": scenario()}, headers=headers).status_code == 403
    assert viewer.post("/api/x/scenarios", json={"scenario": scenario("user-viewer-write")}, headers=headers).status_code == 403
    assert viewer.post("/api/x/replay/studio/start", json={"scenario_id": "quiet-scan", "speed": 1}, headers=headers).status_code == 403
    assert logged_in.delete("/api/x/scenarios/user-c2-check").status_code == 200


def test_replay_studio_routes_run_history_comparison_and_snapshot(studio_env, logged_in):
    status = logged_in.post("/api/x/replay/studio/start", json={"scenario_id": "quiet-scan", "speed": 1})
    assert status.status_code == 200 and status.get_json()["status"]["state"] == "paused"
    run_id = status.get_json()["active_run"]["run_id"]
    step = logged_in.post("/api/x/replay/step", json={})
    assert step.status_code == 200 and step.get_json()["status"]["position"] == 1
    assert logged_in.post("/api/x/replay/breakpoints", json={"sequences": [2]}).status_code == 200
    replay = studio_env.replay
    replay.resume()
    deadline = time.monotonic() + 3
    while replay.status()["state"] != "paused" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert replay.status()["state"] == "paused" and replay.status()["position"] == 2
    assert logged_in.post("/api/x/replay/step-back", json={}).status_code == 200
    assert logged_in.post("/api/x/replay/breakpoints", json={"sequences": []}).status_code == 200
    replay.resume()
    done = replay.wait_until_done(5)
    assert done
    index = logged_in.get("/api/x/runs/%s/snapshots" % run_id)
    assert index.status_code == 200 and len(index.get_json()["items"]) == 4
    snapshot = logged_in.get("/api/x/snapshots?run=%s&version=1" % run_id)
    assert snapshot.status_code == 200 and snapshot.get_json()["position"] == 1
    detail = logged_in.get("/api/x/runs/%s" % run_id)
    assert detail.status_code == 200 and detail.get_json()["summary"]["outcome"] == "completed"
    assert logged_in.get("/api/x/runs").get_json()[0]["run_id"] == run_id
    second_start = logged_in.post("/api/x/replay/studio/start", json={"scenario_id": "quiet-scan", "speed": 8})
    second_id = second_start.get_json()["active_run"]["run_id"]
    assert logged_in.post("/api/x/replay/resume", json={}).status_code == 200
    assert replay.wait_until_done(5)
    comparison = logged_in.get("/api/x/runs/compare?a=%s&b=%s" % (run_id, second_id))
    assert comparison.status_code == 200 and comparison.get_json()["identical"] is True
    assert comparison.get_json()["left_run_id"] != comparison.get_json()["right_run_id"]
    assert logged_in.get("/api/x/feed").get_json()["versions"]["runs"] >= 1

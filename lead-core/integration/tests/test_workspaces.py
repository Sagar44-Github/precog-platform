"""Workspace endpoints, activation semantics, and data isolation."""
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
INSTALLED_PACK_IDS = sorted(path.name for path in (ROOT / "packs").iterdir()
                            if path.is_dir() and (path.name == "demo-6" or path.name.startswith("synth-")))


@pytest.fixture(autouse=True)
def reset_pack_store_root(flask_app):
    """Keep temporary pack fixtures from redirecting the session-scoped app for later tests."""
    manager = flask_app.extensions["precog_workspaces"]
    manager.store.root = ROOT / "packs"
    yield
    manager.store.root = ROOT / "packs"


def make_test_pack(tmp_path, manager):
    source = ROOT / "packs" / "demo-6"
    if not (tmp_path / "demo-6").exists():
        shutil.copytree(source, tmp_path / "demo-6")
    target = tmp_path / "tiny-workspace"
    shutil.copytree(source, target)
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["id"] = "tiny-workspace"
    manifest["name"] = "Tiny workspace route fixture"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manager.store.root = tmp_path.resolve()
    return target


def test_workspace_list_active_and_card(logged_in, flask_app):
    manager = flask_app.extensions["precog_workspaces"]
    listing = logged_in.get("/api/x/workspaces")
    assert listing.status_code == 200
    payload = listing.get_json()
    assert payload["active_workspace"] == "demo-6"
    assert next(item for item in payload["workspaces"] if item["id"] == "demo-6")["status"] == "active"
    assert next(item for item in payload["workspaces"] if item["id"] == "lanl-cyber1")["status"] == "unavailable"
    active = logged_in.get("/api/x/workspaces/active")
    assert active.status_code == 200 and active.get_json()["id"] == "demo-6"
    assert active.get_json()["workspace_version"] == manager.version
    card = logged_in.get("/api/x/workspaces/demo-6/card")
    assert card.status_code == 200
    assert card.get_json()["capabilities"]["lateral_movement_routes"] == "native"
    assert "simulated" in card.get_json()["summary"].lower()
    unavailable_card = logged_in.get("/api/x/workspaces/lanl-cyber1/card")
    assert unavailable_card.status_code == 200
    assert "builder-only" in unavailable_card.get_json()["redistribution"]
    assert "not installed" in unavailable_card.get_json()["limitations"][0]


def test_activation_requires_confirmation_and_role(logged_in, client, flask_app, tmp_path):
    manager = flask_app.extensions["precog_workspaces"]
    make_test_pack(tmp_path, manager)
    # Earlier role tests may deliberately rotate demo passwords in the shared
    # session database. Restore the configured demo credentials before checking
    # the analyst route policy so this test is order independent.
    from addons.auth import ensure_demo_accounts

    ensure_demo_accounts(flask_app.extensions["precog"]["nids"])
    if manager.active.pack_id != "demo-6":
        assert logged_in.post("/api/x/workspaces/demo-6/activate", json={"confirm": True}).status_code == 200
    initial_version = manager.version
    assert logged_in.post("/api/x/workspaces/tiny-workspace/activate", json={}).status_code == 400
    assert manager.version == initial_version
    viewer = client.post("/api/x/login", json={"username": "viewer", "password": "test-viewer-password"})
    assert viewer.status_code == 200
    denied = client.post("/api/x/workspaces/tiny-workspace/activate", json={"confirm": True})
    assert denied.status_code == 403
    assert client.post("/api/x/workspaces/install", json={"pack_id": "tiny-workspace"}).status_code == 403
    assert client.delete("/api/x/workspaces/tiny-workspace").status_code == 403
    assert manager.version == initial_version
    analyst = client.post("/api/x/login", json={"username": "analyst", "password": "test-analyst-password"})
    assert analyst.status_code == 200
    assert client.post("/api/x/workspaces/install", json={"pack_id": "tiny-workspace"}).status_code == 403
    assert client.delete("/api/x/workspaces/tiny-workspace").status_code == 403
    allowed = client.post("/api/x/workspaces/tiny-workspace/activate", json={"confirm": True})
    assert allowed.status_code == 200


def test_analyst_activation_rebuilds_graph_and_resets_world(logged_in, flask_app, tmp_path):
    manager = flask_app.extensions["precog_workspaces"]
    make_test_pack(tmp_path, manager)
    if manager.active.pack_id != "demo-6":
        assert logged_in.post("/api/x/workspaces/demo-6/activate", json={"confirm": True}).status_code == 200
    assert manager.active.pack_id == "demo-6"
    expected_version = manager.version + 1
    result = logged_in.post("/api/x/workspaces/tiny-workspace/activate", json={"confirm": True})
    assert result.status_code == 200, result.get_data(as_text=True)
    assert result.get_json()["status"] == "active"
    assert result.get_json()["workspace_version"] == expected_version
    assert manager.active.pack_id == "tiny-workspace"
    assert len(flask_app.extensions["precog"]["hooks"].get("graph").topology.host_ids()) == 6
    assert flask_app.extensions["precog_workspaces"].ctx.dataset_context.pack_id == "tiny-workspace"
    assert flask_app.extensions["precog"]["world"].snapshot()["changed"] is True
    feed = logged_in.get("/api/x/feed").get_json()
    assert feed["versions"]["workspace"] == manager.version


def test_workspace_sessions_and_artifact_paths_do_not_mix(logged_in, flask_app, tmp_path):
    manager = flask_app.extensions["precog_workspaces"]
    make_test_pack(tmp_path, manager)
    world = flask_app.extensions["precog"]["world"]
    assert logged_in.post("/api/x/workspaces/demo-6/activate", json={"confirm": True}).status_code == 200
    world._sessions = [{"session_id": "demo-session"}]
    assert logged_in.post("/api/x/workspaces/tiny-workspace/activate", json={"confirm": True}).status_code == 200
    studio = flask_app.extensions["precog"]["hooks"].get("studio")
    governance = flask_app.extensions["precog_governance"]
    assert world.sessions() == []
    assert studio.runs_dir == manager.data_root / "tiny-workspace" / "runs"
    assert governance.path == manager.data_root / "tiny-workspace" / "governance" / "records.json"
    assert (manager.data_root / "tiny-workspace" / "state.json").is_file()
    assert logged_in.post("/api/x/workspaces/demo-6/activate", json={"confirm": True}).status_code == 200
    assert manager.active.pack_id == "demo-6"
    assert [item["session_id"] for item in world.sessions()] == ["demo-session"]


def test_install_validates_only_local_pack_ids(logged_in, flask_app, tmp_path):
    manager = flask_app.extensions["precog_workspaces"]
    make_test_pack(tmp_path, manager)
    response = logged_in.post("/api/x/workspaces/install", json={"pack_id": "tiny-workspace"})
    assert response.status_code == 200
    assert response.get_json()["state"] == "completed"
    rejected = logged_in.post("/api/x/workspaces/install", json={"pack_id": "../tiny-workspace"})
    assert rejected.status_code == 400


def test_workspace_delete_protects_default_and_active_and_deletes_inactive(logged_in, flask_app, tmp_path):
    manager = flask_app.extensions["precog_workspaces"]
    pack = make_test_pack(tmp_path, manager)
    assert logged_in.delete("/api/x/workspaces/demo-6").status_code == 403
    assert logged_in.post("/api/x/workspaces/tiny-workspace/activate", json={"confirm": True}).status_code == 200
    assert logged_in.delete("/api/x/workspaces/tiny-workspace").status_code == 409
    # Switch to the unchanged demo before deleting the extra validated pack.
    assert logged_in.post("/api/x/workspaces/demo-6/activate", json={"confirm": True}).status_code == 200
    removed = logged_in.delete("/api/x/workspaces/tiny-workspace")
    assert removed.status_code == 200
    assert not pack.exists()


def test_install_switch_and_delete_are_written_to_workspace_audit(logged_in, flask_app, tmp_path):
    manager = flask_app.extensions["precog_workspaces"]
    make_test_pack(tmp_path, manager)
    installed = logged_in.post("/api/x/workspaces/install", json={"pack_id": "tiny-workspace"})
    assert installed.status_code == 200
    source_audit = logged_in.get("/api/x/audit?type=workspace").get_json()["items"]
    assert any("validated local pack tiny-workspace" in item["summary"] for item in source_audit)

    switched = logged_in.post("/api/x/workspaces/tiny-workspace/activate", json={"confirm": True})
    assert switched.status_code == 200
    target_audit = logged_in.get("/api/x/audit?type=workspace").get_json()["items"]
    assert any("activated from workspace demo-6" in item["summary"] for item in target_audit)

    assert logged_in.post("/api/x/workspaces/demo-6/activate", json={"confirm": True}).status_code == 200
    deleted = logged_in.delete("/api/x/workspaces/tiny-workspace")
    assert deleted.status_code == 200
    audit = logged_in.get("/api/x/audit?type=workspace").get_json()["items"]
    assert any("deleted installed workspace pack tiny-workspace" in item["summary"] for item in audit)


@pytest.mark.parametrize("pack_id", INSTALLED_PACK_IDS)
def test_every_shipped_workspace_drives_twin_paths_and_asset_routes(logged_in, flask_app, pack_id):
    """Exercise workspace activation and every topology-dependent read endpoint per installed pack."""
    manager = flask_app.extensions["precog_workspaces"]
    try:
        listing = logged_in.get("/api/x/workspaces")
        assert listing.status_code == 200
        listed_pack = next(item for item in listing.get_json()["workspaces"] if item["id"] == pack_id)
        card = logged_in.get("/api/x/workspaces/%s/card" % pack_id)
        assert card.status_code == 200, card.get_data(as_text=True)
        activated = logged_in.post("/api/x/workspaces/%s/activate" % pack_id, json={"confirm": True})
        assert activated.status_code == 200, activated.get_data(as_text=True)
        assert activated.get_json()["id"] == pack_id

        topology_response = logged_in.get("/api/x/topology")
        assert topology_response.status_code == 200, topology_response.get_data(as_text=True)
        topology = topology_response.get_json()
        graph = manager.ctx.hooks.require("graph").topology
        ids = graph.host_ids()
        assert len(topology["hosts"]) == len(ids) == int(listed_pack["counts"]["hosts"])
        assert len(topology["feasible_edges"]) == len(graph.feasible_edges())
        assert {host["host_id"] for host in topology["hosts"]} == set(ids)

        summary = logged_in.get("/api/x/topology/summary?offset=0&limit=7")
        assert summary.status_code == 200, summary.get_data(as_text=True)
        assert summary.get_json()["total_hosts"] == len(ids)
        assert summary.get_json()["total_edges"] == len(graph.feasible_edges())

        source = next(host for host in ids if graph.reachable_from(host))
        target = graph.reachable_from(source)[-1]
        routes = logged_in.get("/api/x/topology/paths", query_string={"from": source, "to": target, "limit": 10})
        assert routes.status_code == 200, routes.get_data(as_text=True)
        assert routes.get_json()["paths"]
        assert routes.get_json()["paths"][0]["hosts"][0] == source
        assert routes.get_json()["paths"][0]["hosts"][-1] == target

        asset = logged_in.get("/api/x/hosts/%s" % ids[0])
        history = logged_in.get("/api/x/hosts/%s/history" % ids[0])
        assert asset.status_code == 200, asset.get_data(as_text=True)
        assert asset.get_json()["host"]["host_id"] == ids[0]
        assert history.status_code == 200, history.get_data(as_text=True)

        edge = graph.feasible_edges()[0]
        segmentation = logged_in.get("/api/x/topology/segmentation-preview", query_string={
            "from": edge[0], "remove_from": edge[0], "remove_to": edge[1],
        })
        assert segmentation.status_code == 200, segmentation.get_data(as_text=True)
        assert segmentation.get_json()["removed_edge"] == {"from_host": edge[0], "to_host": edge[1]}

        scenarios_response = logged_in.get("/api/x/replay/scenarios")
        assert scenarios_response.status_code == 200, scenarios_response.get_data(as_text=True)
        scenarios = scenarios_response.get_json()
        assert scenarios, "an installed workspace needs at least one replay scenario"
        scenario_id = scenarios[0]["scenario_id"]
        started = logged_in.post("/api/x/replay/start", json={"scenario_id": scenario_id, "speed": 8})
        assert started.status_code == 200, started.get_data(as_text=True)
        assert started.get_json()["scenario_id"] == scenario_id
        live_state = logged_in.get("/api/x/state")
        assert live_state.status_code == 200, live_state.get_data(as_text=True)
        assert len(live_state.get_json()["graph"]["hosts"]) == len(ids)
        assert live_state.get_json()["replay"]["scenario_id"] == scenario_id
    finally:
        replay = manager.ctx.hooks.get("replay")
        if replay is not None:
            replay.stop()
        if manager.active.pack_id != "demo-6":
            restored = logged_in.post("/api/x/workspaces/demo-6/activate", json={"confirm": True})
            assert restored.status_code == 200, restored.get_data(as_text=True)


def test_precog_model_and_forecast_state_are_isolated_on_repeated_workspace_switches(logged_in, flask_app):
    from precog_engine.model import NodeModel

    manager = flask_app.extensions["precog_workspaces"]
    engine = flask_app.extensions["precog"]["hooks"].require("precog")
    world = flask_app.extensions["precog"]["world"]
    signatures = {}
    sequence = INSTALLED_PACK_IDS + list(reversed(INSTALLED_PACK_IDS))
    lab = flask_app.extensions["precog_lab"]
    try:
        for pack_id in sequence:
            stale_key = "old-workspace-sentinel-%s" % manager.active.pack_id
            lab._cache[stale_key] = {"sentinel": True}
            activated = logged_in.post("/api/x/workspaces/%s/activate" % pack_id, json={"confirm": True})
            assert activated.status_code == 200, activated.get_data(as_text=True)
            context = manager.active
            graph = manager.ctx.hooks.require("graph")
            host_ids = set(graph.topology.host_ids())

            assert context.pack_id == pack_id
            assert engine.model.to_dict() == NodeModel.from_dict(context.model).to_dict()
            assert set(engine.model.counts) <= host_ids
            assert engine._counter == 0 and engine._pending is None and engine._resolved == [] and engine._explanations == {}
            assert world.forecasts() == [] and world.alerts() == []
            assert stale_key not in lab._cache
            expected_lab_dir = (manager.data_root / pack_id / "analytics" if pack_id != "demo-6"
                                else Path(manager.ctx.config.data_dir) / "analytics")
            assert lab.data_dir == expected_lab_dir

            source = next(host_id for host_id in sorted(host_ids) if graph.topology.candidates(host_id))
            assert graph.mark_compromised(source)
            forecast = engine.on_compromise(source)
            assert forecast is not None
            assert forecast["from_host"] == source
            assert {item["host_id"] for item in forecast["targets"]} <= set(graph.topology.candidates(source, exclude=[source]))
            assert {item["host_id"] for item in forecast["targets"]} <= host_ids
            explanation = engine.explanation_context(forecast["forecast_id"])
            assert explanation["stage"] == 0
            assert set(explanation["candidate_ids"]) <= host_ids
            signature = [(item["host_id"], item["confidence"]) for item in forecast["targets"]]
            if pack_id in signatures:
                assert signature == signatures[pack_id]
            signatures[pack_id] = signature
    finally:
        replay = manager.ctx.hooks.get("replay")
        if replay is not None:
            replay.stop()
        if manager.active.pack_id != "demo-6":
            restored = logged_in.post("/api/x/workspaces/demo-6/activate", json={"confirm": True})
            assert restored.status_code == 200, restored.get_data(as_text=True)

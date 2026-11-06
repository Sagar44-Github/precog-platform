"""Workspace endpoints, activation semantics, and data isolation."""
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


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

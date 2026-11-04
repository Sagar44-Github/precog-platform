"""API workflows for server-resolved playbooks and confirmed simulated release."""

import pytest

from addons.loader import ROLE_PACKAGES, AddonContext, _load_role_packages


@pytest.fixture()
def containment_stack(flask_app, monkeypatch):
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


def test_top_three_playbook_resolves_targets_and_keeps_confirmation_required(logged_in, world, containment_stack):
    graph = containment_stack["hooks"].get("graph")
    graph.mark_compromised("host-a")
    proposed = logged_in.post("/api/x/containment/playbooks/propose", json={
        "playbook": "top_three", "forecast_id": "fc-000001",
    })
    assert proposed.status_code == 200, proposed.get_json()
    action = proposed.get_json()
    assert action["playbook"] == "top_three"
    assert action["target_hosts"] == ["server-b", "file-server", "host-b"]
    assert action["status"] == "pending_confirmation"
    assert graph.host_state("server-b") == "normal"

    confirmed = logged_in.post("/api/x/containment/confirm", json={"action_id": action["action_id"]})
    assert confirmed.status_code == 200
    assert [graph.host_state(host) for host in action["target_hosts"]] == ["contained"] * 3
    assert world.get_action(action["action_id"])["operation"] == "contain"


def test_zone_playbook_resolves_only_hosts_in_the_selected_zone(logged_in, containment_stack):
    proposed = logged_in.post("/api/x/containment/playbooks/propose", json={"playbook": "zone", "zone": "user"})
    assert proposed.status_code == 200
    assert proposed.get_json()["target_hosts"] == ["host-a", "host-b"]
    assert logged_in.post("/api/x/containment/playbooks/propose", json={"playbook": "zone", "zone": "unknown"}).status_code == 404


def test_release_is_separate_two_step_admin_action_and_appears_in_history(logged_in, world, containment_stack):
    containment = containment_stack["hooks"].get("containment")
    original = containment.propose(world, "server-b", "fc-000001", "console")
    containment.confirm(world, original["action_id"])
    graph = containment_stack["hooks"].get("graph")

    proposed = logged_in.post("/api/x/containment/release/propose", json={"containment_action_id": original["action_id"]})
    assert proposed.status_code == 200
    release = proposed.get_json()
    assert release["operation"] == "release" and release["status"] == "pending_confirmation"
    assert graph.host_state("server-b") == "contained"

    done = logged_in.post("/api/x/containment/confirm", json={"action_id": release["action_id"]})
    assert done.status_code == 200 and done.get_json()["operation"] == "release"
    assert graph.host_state("server-b") == "normal"
    actions = logged_in.get("/api/x/containment/actions?include_archived=1").get_json()
    assert {item["operation"] for item in actions if item["action_id"] in {original["action_id"], release["action_id"]}} == {"contain", "release"}


def test_analyst_cannot_release_an_executed_containment(client, ctx, world, containment_stack):
    nids = ctx["nids"]
    session = nids.SessionLocal()
    try:
        user = session.query(nids.User).filter_by(username="analyst").first()
        password_hash = nids.bcrypt.generate_password_hash("analyst-test-password").decode("utf-8")
        if user is None:
            session.add(nids.User(username="analyst", password_hash=password_hash))
        else:
            user.password_hash = password_hash
        session.commit()
    finally:
        session.close()
    assert client.post("/api/x/login", json={"username": "analyst", "password": "analyst-test-password"}).status_code == 200
    reply = client.post("/api/x/containment/release/propose", json={"containment_action_id": "act-000001"})
    assert reply.status_code == 403 and reply.get_json()["error"]["code"] == "forbidden"


def test_playbook_input_is_contract_validated(logged_in):
    reply = logged_in.post("/api/x/containment/playbooks/propose", json={"playbook": "scan"})
    assert reply.status_code == 400
    assert reply.get_json()["error"]["code"] == "bad_request"

import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from addons.errors import ApiError
from addons.governance import GovernanceService, PLAYBOOK_POLICY


def _login(client, role):
    password = os.environ[role.upper() + "_PASSWORD"]
    return client.post("/api/x/login", json={"username": role, "password": password})


def _propose(client, playbook_id="contain-host", **fields):
    return client.post("/api/x/containment/governance/propose", json={
        "playbook_id": playbook_id,
        "reason": "Protect the scripted demo path.",
        **fields,
    })


def _record(response):
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["record"]


@pytest.fixture(autouse=True)
def reset_graph(ctx, flask_app):
    graph = ctx["hooks"].get("graph")
    if graph is not None:
        graph.reset()
    service = flask_app.extensions["precog_governance"]
    service._approvals.clear()
    service._releases.clear()
    service._counter = 0
    service.revision = 0
    service.path.unlink(missing_ok=True)


def test_playbook_policy_has_a_cell_for_each_role_and_scope(logged_in, ctx):
    service = logged_in.application.extensions["precog_governance"]
    actual = {item["playbook_id"]: item for item in service.list_playbooks()}
    assert set(actual) == set(PLAYBOOK_POLICY)
    for playbook_id, policy in PLAYBOOK_POLICY.items():
        assert actual[playbook_id]["allowed_roles"] == policy["roles"]
        for role in ("viewer", "analyst", "admin"):
            if role in policy["roles"]:
                assert service._policy(playbook_id, role) == policy
            else:
                with pytest.raises(ApiError) as denied:
                    service._policy(playbook_id, role)
                assert denied.value.status == 403
    assert all(item["simulation_only"] for item in actual.values())


def test_preview_matches_top_three_forecast_and_contains_side_effects(logged_in):
    response = logged_in.post("/api/x/containment/preview", json={
        "playbook_id": "contain-top-three", "forecast_id": "fc-000001",
    })
    assert response.status_code == 200, response.get_data(as_text=True)
    result = response.get_json()
    assert {item["host_id"] for item in result["hosts_affected"]} == {"server-b", "host-b", "file-server"}
    forecast = logged_in.application.extensions["precog"]["world"].snapshot()["forecast"]
    expected_removed = min(1.0, sum(item["confidence"] for item in forecast["targets"]))
    assert result["probability_removed"] == pytest.approx(expected_removed)
    assert result["probability_restored"] == 0
    assert result["criticality_total"] > 0
    assert result["feasible_edges_changed"]
    assert any("Legitimate use" in item for item in result["side_effects"])
    assert "re-evaluate" in result["expected_reevaluation"]


def test_analyst_single_host_is_propose_then_confirm_and_is_audited(logged_in, ctx, world):
    assert _login(logged_in, "analyst").status_code == 200
    before = logged_in.get("/api/x/feed").get_json()
    response = _propose(logged_in, host_id="server-b", forecast_id="fc-000001")
    record = _record(response)
    assert record["status"] == "pending_confirmation"
    forecast = logged_in.application.extensions["precog"]["world"].snapshot()["forecast"]
    assert record["preview_snapshot"]["probability_removed"] == pytest.approx(forecast["targets"][0]["confidence"])
    assert record["reason"] == "Protect the scripted demo path."
    confirmed = _record(logged_in.post("/api/x/containment/governance/confirm", json={"action_id": record["action_id"]}))
    assert confirmed["status"] == "executed"
    assert confirmed["host_action_ids"]
    assert world.actions()[-1]["status"] == "executed"
    assert ctx["hooks"].require("graph").host_state("server-b") == "contained"
    listed = logged_in.get("/api/x/containment/governance").get_json()
    assert listed["approvals"][0]["action_id"] == record["action_id"]
    after = logged_in.get("/api/x/feed?since=%s" % before["revision"]).get_json()
    assert after["changed"] is True and after["versions"]["actions"] > before["versions"]["actions"]
    audit = ctx["hooks"].require("events").audit.read_all()
    entries = [item for item in audit if item["ref_id"] == record["action_id"]]
    assert len(entries) >= 2 and all(item["type"] == "containment" for item in entries)
    stored = ctx["config"].data_dir / "governance" / "records.json"
    assert json.loads(stored.read_text(encoding="utf-8"))[-1]["record"]["status"] == "executed"


def test_viewer_and_analyst_policy_is_enforced_on_server(client, ctx):
    assert _login(client, "viewer").status_code == 200
    assert client.get("/api/x/containment/playbooks").status_code == 200
    assert client.get("/api/x/containment/governance").status_code == 200
    denied = _propose(client, host_id="server-b")
    assert denied.status_code == 403
    assert client.post("/api/x/containment/preview", json={"playbook_id": "contain-zone", "zone": "dmz"}).status_code == 403
    client.post("/api/x/logout", json={})
    assert _login(client, "analyst").status_code == 200
    host = _propose(client, host_id="server-b")
    assert host.status_code == 200
    assert client.post("/api/x/containment/preview", json={"playbook_id": "contain-zone", "zone": "dmz"}).status_code == 403
    assert client.post("/api/x/containment/preview", json={"playbook_id": "release-host", "host_id": "server-b"}).status_code == 403
    action_id = host.get_json()["record"]["action_id"]
    assert client.post("/api/x/containment/governance/cancel", json={"action_id": action_id, "reason": "Test cleanup."}).status_code == 200


def test_zone_preview_and_proposal_conflict_are_explicit(logged_in, ctx):
    graph = ctx["hooks"].require("graph")
    zone = graph.topology.hosts["server-b"]["zone"]
    preview = logged_in.post("/api/x/containment/preview", json={"playbook_id": "contain-zone", "zone": zone})
    assert preview.status_code == 200
    proposal = _record(_propose(logged_in, "contain-zone", zone=zone))
    assert proposal["status"] == "pending_confirmation"
    overlapping = _propose(logged_in, host_id="server-b")
    assert overlapping.status_code == 409
    cancelled = _record(logged_in.post("/api/x/containment/governance/cancel", json={"action_id": proposal["action_id"], "reason": "Operator cancelled."}))
    assert cancelled["status"] == "cancelled"
    again = logged_in.post("/api/x/containment/governance/confirm", json={"action_id": proposal["action_id"]})
    assert again.status_code == 409


def test_release_requires_admin_reason_and_confirmation(logged_in, ctx):
    graph = ctx["hooks"].require("graph")
    graph.set_host_state("server-b", "contained")
    missing_reason = logged_in.post("/api/x/containment/governance/propose", json={"playbook_id": "release-host", "host_id": "server-b"})
    assert missing_reason.status_code == 400
    record = _record(_propose(logged_in, "release-host", host_id="server-b", reason="Reviewed; restore this simulated host."))
    assert record["status"] == "pending_confirmation"
    assert graph.host_state("server-b") == "contained"
    released = _record(logged_in.post("/api/x/containment/governance/confirm", json={"action_id": record["action_id"]}))
    assert released["status"] == "released"
    assert graph.host_state("server-b") == "normal"
    assert logged_in.get("/api/x/containment/governance").get_json()["releases"][0]["action_id"] == record["action_id"]


def test_two_person_zone_approval_rejects_same_actor_and_then_executes(logged_in, ctx):
    service = logged_in.application.extensions["precog_governance"]
    service.two_person_zone = True
    zone = ctx["hooks"].require("graph").topology.hosts["server-b"]["zone"]
    record = service.propose("contain-zone", "admin", "admin", "Review high criticality assets.", zone=zone)
    assert record["status"] == "pending_approval"
    with pytest.raises(ApiError) as same_actor:
        service.approve(record["action_id"], "admin", "admin", "approve")
    assert same_actor.value.status == 403
    approved = service.approve(record["action_id"], "admin-reviewer", "admin", "approve")
    assert approved["status"] == "pending_confirmation"
    assert approved["approval"]["actor"] == "admin-reviewer"
    completed = service.confirm(record["action_id"], "admin", "admin")
    assert completed["status"] == "executed"


def test_expiry_is_enforced_and_recorded_atomically(ctx, world, tmp_path):
    now = [datetime(2026, 1, 1, tzinfo=timezone.utc)]
    service = GovernanceService(SimpleNamespace(**ctx), clock=lambda: now[0])
    service.path = tmp_path / "records.json"
    record = service.propose("contain-host", "analyst", "analyst", "Protect the host.", host_id="server-b")
    now[0] += timedelta(seconds=61)
    history = service.records()
    assert history["approvals"][0]["action_id"] == record["action_id"]
    assert history["approvals"][0]["status"] == "expired"
    assert not list(tmp_path.glob("*.tmp"))
    with pytest.raises(ApiError) as error:
        service.confirm(record["action_id"], "analyst", "analyst")
    assert error.value.status == 409


def test_replay_change_cancels_stale_proposal(logged_in, ctx, world):
    record = _record(_propose(logged_in, host_id="server-b"))
    world.set_session({**(world.session() or {}), "session_id": "new-replay-session"})
    confirm = logged_in.post("/api/x/containment/governance/confirm", json={"action_id": record["action_id"]})
    assert confirm.status_code == 409
    assert confirm.get_json()["error"]["code"] == "stale_request"
    history = logged_in.get("/api/x/containment/governance").get_json()
    assert history["approvals"][0]["status"] == "cancelled"


def test_reason_validation_and_html_is_stored_as_plain_text(logged_in):
    oversized = _propose(logged_in, host_id="server-b", reason="x" * 501)
    assert oversized.status_code == 400
    html_text = "<script>alert(1)</script> protect demo host"
    record = _record(_propose(logged_in, host_id="server-b", reason=html_text))
    assert record["reason"] == html_text
    logged_in.post("/api/x/containment/governance/cancel", json={"action_id": record["action_id"], "reason": "Test cleanup."})


def test_unknown_hosts_incidents_and_malformed_writes_are_rejected(logged_in):
    unknown = logged_in.post("/api/x/containment/preview", json={"playbook_id": "contain-host", "host_id": "../secret"})
    assert unknown.status_code == 404
    malformed_incident = _propose(logged_in, host_id="server-b", incident_id="INC-../../secret")
    assert malformed_incident.status_code == 400
    extra = logged_in.post("/api/x/containment/preview", json={"playbook_id": "contain-host", "host_id": "server-b", "path": "../../secret"})
    assert extra.status_code == 400


def test_preview_endpoint_has_an_in_memory_rate_limit(logged_in):
    from addons.auth import _RATE_BUCKETS, _RATE_LOCK
    endpoint = "precog_addons.containment_preview"
    with _RATE_LOCK:
        _RATE_BUCKETS.pop((logged_in.get("/api/x/me").get_json().get("username"), endpoint), None)
    replies = [logged_in.post("/api/x/containment/preview", json={"playbook_id": "contain-host", "host_id": "server-b"}) for _ in range(21)]
    assert any(reply.status_code == 200 for reply in replies)
    assert any(reply.status_code == 429 for reply in replies)


def test_governance_exports_are_available_as_json_and_markdown(logged_in):
    record = _record(_propose(logged_in, host_id="server-b"))
    logged_in.post("/api/x/containment/governance/cancel", json={"action_id": record["action_id"], "reason": "Export fixture cleanup."})
    json_export = logged_in.get("/api/x/containment/governance/export?format=json")
    assert json_export.status_code == 200
    assert json_export.get_json()["approvals"][0]["action_id"] == record["action_id"]
    markdown = logged_in.get("/api/x/containment/governance/export?format=markdown")
    assert markdown.status_code == 200 and "text/markdown" in markdown.content_type
    assert "SIMULATION" in markdown.get_data(as_text=True)
    assert "PB-ACT-" + record["action_id"].split("-")[-1] in markdown.get_data(as_text=True)
    assert logged_in.get("/api/x/containment/governance/export?format=html").status_code == 400


def test_governance_contract_samples_validate(ctx):
    for name in ("playbook", "playbook_preview", "approval_record", "release_record"):
        sample = json.loads((ctx["config"].contracts_dir / "samples" / (name + ".sample.json")).read_text(encoding="utf-8"))
        ctx["contracts"].validate(name, sample)

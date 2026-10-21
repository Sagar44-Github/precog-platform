import time

import pytest

from addons.errors import HookError
from viz_helpers import Rig


def propose(rig, target="server-b", forecast_id="fc-000001", requested_by="mobile"):
    return rig.service.propose(rig.world, target, forecast_id, requested_by)


# ---------- the two-step flow ----------
def test_propose_makes_a_pending_action_and_changes_nothing_else(rig, contracts):
    action = propose(rig)
    contracts.validate("containment_action", action)
    assert action["status"] == "pending_confirmation" and action["action_id"] == "act-000001"
    assert action["target_host"] == "server-b" and action["requested_by"] == "mobile" and action["confirmed_at"] is None
    assert rig.graph.states["server-b"] == "normal"                      # nothing happens until confirm
    assert rig.world.actions()[0]["status"] == "pending_confirmation"


def test_confirm_contains_the_host_and_records_the_time(rig, contracts):
    action = propose(rig)
    done = rig.service.confirm(rig.world, action["action_id"])
    contracts.validate("containment_action", done)
    assert done["status"] == "executed" and done["confirmed_at"] and "simulated" in done["result"]
    assert rig.graph.states["server-b"] == "contained"
    assert rig.world.actions()[0]["status"] == "executed"


def test_cancel_leaves_the_host_alone(rig):
    action = propose(rig)
    cancelled = rig.service.cancel(rig.world, action["action_id"])
    assert cancelled["status"] == "cancelled" and rig.graph.states["server-b"] == "normal"


def test_a_request_cannot_be_confirmed_twice_or_after_cancel(rig):
    action = propose(rig)
    rig.service.confirm(rig.world, action["action_id"])
    for call in (rig.service.confirm, rig.service.cancel):
        with pytest.raises(HookError) as info:
            call(rig.world, action["action_id"])
        assert info.value.status == 409 and info.value.code == "not_pending"
    second = Rig(rig.world, rig.service.contracts)
    second.service._counter = 5
    other = second.service.propose(rig.world, "host-b", None, "console")
    second.service.cancel(rig.world, other["action_id"])
    with pytest.raises(HookError):
        second.service.confirm(rig.world, other["action_id"])
    second.service.shutdown()


def test_unknown_action_and_unknown_host_are_clear_errors(rig):
    with pytest.raises(HookError) as info:
        rig.service.confirm(rig.world, "act-999999")
    assert info.value.status == 404 and info.value.code == "unknown_action"
    with pytest.raises(HookError) as info:
        propose(rig, target="ghost")
    assert info.value.status == 404 and info.value.code == "unknown_host"


def test_containing_a_contained_host_is_refused(rig):
    rig.service.confirm(rig.world, propose(rig)["action_id"])
    with pytest.raises(HookError) as info:
        propose(rig)
    assert info.value.status == 409 and info.value.code == "already_contained" and "Web Server B" in info.value.message


def test_only_one_request_waits_at_a_time(rig):
    first = propose(rig)
    assert propose(rig)["action_id"] == first["action_id"]               # same host: the open request is returned
    with pytest.raises(HookError) as info:
        propose(rig, target="host-b")
    assert info.value.status == 409 and info.value.code == "pending_exists"
    rig.service.cancel(rig.world, first["action_id"])
    assert propose(rig, target="host-b")["action_id"] == "act-000002"


def test_containment_needs_the_graph_part(rig):
    rig.hooks._items.pop("graph")
    with pytest.raises(HookError) as info:
        propose(rig)
    assert info.value.status == 501


# ---------- expiry ----------
def test_an_unanswered_request_expires_and_cannot_be_confirmed(world, contracts):
    rig = Rig(world, contracts, confirm_seconds=0.15)
    action = propose(rig)
    assert rig.wait(lambda: world.actions()[0]["status"] == "expired")
    assert rig.graph.states["server-b"] == "normal"
    with pytest.raises(HookError) as info:
        rig.service.confirm(world, action["action_id"])
    assert info.value.status == 409 and "expired" in info.value.message
    rig.service.shutdown()


def test_confirming_in_time_stops_the_expiry_timer(world, contracts):
    rig = Rig(world, contracts, confirm_seconds=0.2)
    rig.service.confirm(world, propose(rig)["action_id"])
    time.sleep(0.4)
    assert world.actions()[0]["status"] == "executed"
    rig.service.shutdown()


def test_a_replay_restart_forgets_pending_requests(rig):
    propose(rig)
    rig.world.reset()                                                    # what the replay does when it starts
    again = propose(rig)
    assert again["status"] == "pending_confirmation" and len(rig.world.actions()) == 1


# ---------- audit ----------
def test_every_step_is_written_to_the_audit_log(rig):
    action = propose(rig)
    rig.service.confirm(rig.world, action["action_id"])
    kinds = [(t, ref) for t, ref, _ in rig.events.audit]
    assert kinds[:2] == [("containment", action["action_id"])] * 2
    assert "proposed" in rig.events.audit[0][2] and "executed" in rig.events.audit[1][2]


def test_a_broken_audit_log_never_blocks_a_containment(rig):
    def explode(*args):
        raise RuntimeError("disk full")

    rig.events.audit_record = explode
    assert rig.service.confirm(rig.world, propose(rig)["action_id"])["status"] == "executed"


def test_containment_works_without_the_events_part(rig):
    rig.hooks._items.pop("events")
    assert rig.service.confirm(rig.world, propose(rig)["action_id"])["status"] == "executed"


# ---------- re-evaluation ----------
def resolve(rig, status, blocked, attempted="server-b"):
    rig.world.set_forecast({"forecast_id": "fc-000001", "ts": "2026-10-03T10:00:03Z", "from_host": "host-a",
                            "targets": [{"rank": 1, "host_id": "server-b", "confidence": 0.74}], "technique_hint": None,
                            "source": "lookup", "status": "pending", "outcome": None})
    rig.world.resolve_forecast("fc-000001", status, {"attempted_host": attempted, "rank_hit": 1 if status == "hit" else None, "blocked": blocked})


def test_re_evaluation_says_the_chain_ended_early_after_a_blocked_hit(rig, contracts):
    action = rig.service.confirm(rig.world, propose(rig)["action_id"])
    resolve(rig, "hit", True)
    assert rig.wait(lambda: rig.service.reeval_results())
    result = rig.service.reeval_results()[0]
    contracts.validate("reeval_result", result)
    assert result["chain_ended_early"] is True and result["attack_progressed"] is False and "Web Server B" in result["summary"]
    assert "ended early" in rig.world.actions()[0]["result"] and "Re-evaluation" in rig.world.actions()[0]["result"]
    assert any("Re-evaluation" in s for _, _, s in rig.events.audit)


def test_re_evaluation_says_the_attack_progressed_after_a_miss(rig):
    rig.service.confirm(rig.world, propose(rig)["action_id"])
    resolve(rig, "miss", False, attempted="host-b")
    assert rig.wait(lambda: rig.service.reeval_results())
    result = rig.service.reeval_results()[0]
    assert result["attack_progressed"] is True and result["chain_ended_early"] is False and "Workstation B" in result["summary"]


def test_re_evaluation_only_looks_at_the_forecast_the_containment_was_made_for(rig):
    rig.service.confirm(rig.world, propose(rig, forecast_id="fc-000007")["action_id"])
    resolve(rig, "hit", True)                                           # a different forecast (fc-000001)
    time.sleep(0.3)
    assert rig.service.reeval_results() == []


def test_without_a_resolved_forecast_the_action_keeps_its_plain_result(rig):
    done = rig.service.confirm(rig.world, propose(rig)["action_id"])
    time.sleep(0.2)
    assert rig.world.actions()[0]["result"] == done["result"]

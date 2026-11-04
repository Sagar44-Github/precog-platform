"""Multi-host response playbooks and release remain simulated and two-step."""

import pytest

from addons.errors import HookError
from viz_helpers import Rig


def test_playbook_proposal_lists_every_target_without_changing_state(rig, contracts):
    action = rig.service.propose_many(rig.world, ["host-a", "host-b", "host-a"], "fc-000001", "console", "top_three")
    contracts.validate("containment_action", action)
    assert action["operation"] == "contain"
    assert action["playbook"] == "top_three"
    assert action["target_host"] == "host-a"
    assert action["target_hosts"] == ["host-a", "host-b"]
    assert [rig.graph.states[host] for host in action["target_hosts"]] == ["normal", "normal"]


def test_multi_host_confirmation_contains_all_targets_in_one_audited_action(rig):
    action = rig.service.propose_many(rig.world, ["host-a", "host-b"], None, "console", "zone")
    confirmed = rig.service.confirm(rig.world, action["action_id"])
    assert confirmed["status"] == "executed"
    assert rig.graph.states["host-a"] == rig.graph.states["host-b"] == "contained"
    assert "2 hosts" in confirmed["result"]
    assert len([entry for entry in rig.world.actions() if entry["action_id"] == action["action_id"]]) == 1
    assert any("Workstation A, Workstation B" in summary for _, _, summary in rig.events.audit)


def test_release_is_proposed_and_requires_a_second_confirmation(rig, contracts):
    original = rig.service.propose_many(rig.world, ["host-a", "host-b"], "fc-000001", "console", "predicted_path")
    rig.service.confirm(rig.world, original["action_id"])

    release = rig.service.propose_release(rig.world, original["action_id"], "console")
    contracts.validate("containment_action", release)
    assert release["operation"] == "release" and release["related_action_id"] == original["action_id"]
    assert release["status"] == "pending_confirmation"
    assert rig.graph.states["host-a"] == rig.graph.states["host-b"] == "contained"

    done = rig.service.confirm(rig.world, release["action_id"])
    assert done["status"] == "executed" and "Released 2 hosts" in done["result"]
    assert rig.graph.states["host-a"] == rig.graph.states["host-b"] == "normal"
    assert rig.world.get_action(original["action_id"])["status"] == "executed"


def test_release_restores_a_previously_compromised_state(rig):
    rig.graph.states["host-a"] = "compromised"
    original = rig.service.propose(rig.world, "host-a", None, "console")
    rig.service.confirm(rig.world, original["action_id"])
    release = rig.service.propose_release(rig.world, original["action_id"], "console")
    rig.service.confirm(rig.world, release["action_id"])
    assert rig.graph.states["host-a"] == "compromised"


def test_release_rejects_non_containment_and_duplicate_release(rig):
    normal = rig.service.propose(rig.world, "host-a", None, "console")
    with pytest.raises(HookError) as info:
        rig.service.propose_release(rig.world, normal["action_id"], "console")
    assert info.value.code == "not_releasable"

    rig.service.confirm(rig.world, normal["action_id"])
    release = rig.service.propose_release(rig.world, normal["action_id"], "console")
    with pytest.raises(HookError) as info:
        rig.service.propose_release(rig.world, normal["action_id"], "console")
    assert info.value.code == "release_exists"
    rig.service.cancel(rig.world, release["action_id"])


def test_expired_or_cancelled_release_does_not_restore_hosts(rig):
    original = rig.service.propose(rig.world, "host-a", None, "console")
    rig.service.confirm(rig.world, original["action_id"])
    release = rig.service.propose_release(rig.world, original["action_id"], "console")
    rig.service.cancel(rig.world, release["action_id"])
    assert rig.graph.states["host-a"] == "contained"

import threading
import time

import pytest

from addons.errors import HookError
from graph_replay import ReplayController

FAST = 80.0  # run the 6.5-second scenarios in about 80 ms


def run_golden(rig, contain=True, speed=FAST):
    rig.controller.start("golden-path", speed)
    assert rig.wait_for("waiting_for_decision")
    if contain is True:
        rig.contain("server-b")
    elif contain == "manual":
        rig.controller.resume()
    assert rig.controller.wait_until_done(10)


# ---------- starting ----------
def test_start_needs_a_known_scenario_and_a_real_speed(rig):
    with pytest.raises(HookError) as info:
        rig.controller.start("nope", 1)
    assert info.value.status == 404 and "golden-path" in info.value.message
    for bad in (0, -1, None):
        with pytest.raises(HookError) as info:
            rig.controller.start("golden-path", bad)
        assert info.value.status == 400


def test_start_needs_the_events_and_graph_parts(rig):
    rig.hooks._items.pop("events")
    with pytest.raises(HookError) as info:
        rig.controller.start("golden-path", FAST)
    assert info.value.status == 501 and "events" in info.value.message
    assert rig.controller.status()["state"] == "idle"


def test_a_second_start_while_running_is_refused(rig):
    rig.controller.start("golden-path", 1.0)
    with pytest.raises(HookError) as info:
        rig.controller.start("golden-path", 1.0)
    assert info.value.status == 409


def test_list_scenarios(rig):
    assert {s["scenario_id"] for s in rig.controller.list_scenarios()} == {"direct-hit", "golden-path", "lateral-spread", "quiet-scan"}


# ---------- the golden path ----------
def test_golden_path_with_containment_blocks_the_move(rig):
    run_golden(rig, contain=True)
    status = rig.controller.status()
    assert status == {"state": "finished", "scenario_id": "golden-path", "speed": FAST, "position": 5}
    assert rig.graph.host_state("host-a") == "compromised" and rig.graph.host_state("server-b") == "contained"
    assert rig.graph.snapshot()["compromised_path"] == ["host-a"]
    assert ("attempt", "host-a", "server-b", True) in rig.precog.calls
    assert ("compromise", "server-b") not in rig.precog.calls
    assert rig.controller.last_decision == "executed" and rig.controller.last_error is None
    blocked = [a for a in rig.world.alerts(50) if "was blocked" in a["explanation"]]
    assert len(blocked) == 1 and "Web Server B" in blocked[0]["explanation"]


def test_golden_path_without_containment_lets_the_attacker_through(rig):
    run_golden(rig, contain="manual")
    assert rig.graph.host_state("server-b") == "compromised"
    assert rig.graph.snapshot()["compromised_path"] == ["host-a", "server-b"]
    assert rig.precog.calls == [("compromise", "host-a"), ("attempt", "host-a", "server-b", False), ("compromise", "server-b")]
    assert rig.controller.last_decision == "manual"


@pytest.mark.parametrize("decision,expected", [("cancelled", "success"), ("expired", "success")])
def test_a_cancelled_or_expired_decision_lets_the_replay_go_on_without_containment(rig, decision, expected):
    rig.controller.start("golden-path", FAST)
    assert rig.wait_for("waiting_for_decision")
    rig.contain("server-b", status=decision)
    assert rig.controller.wait_until_done(10)
    assert rig.graph.host_state("server-b") == "compromised" and rig.controller.last_decision == decision


def test_an_unanswered_decision_times_out_and_the_attacker_goes_on(world, graph, library, hosts):
    from graph_helpers import Rig

    rig = Rig(world, graph, library, hosts, decision_timeout=0.2)
    rig.controller.start("golden-path", FAST)
    assert rig.controller.wait_until_done(10)
    assert rig.controller.last_decision == "timeout" and rig.graph.host_state("server-b") == "compromised"


def test_the_replay_waits_before_the_decision_point_and_not_after_it_started(rig):
    rig.controller.start("golden-path", FAST)
    assert rig.wait_for("waiting_for_decision")
    assert rig.controller.status()["position"] == 3        # three events done; the attempt has NOT run yet
    assert rig.graph.host_state("server-b") == "normal"
    rig.controller.resume()
    assert rig.controller.wait_until_done(10)


def test_traffic_is_written_detected_handed_over_and_recorded(rig):
    run_golden(rig, contain=True)
    rows = rig.store.all()
    assert len(rows) == 5                                              # 3 packets to port 22 + 2 to port 445
    assert {r["src_ip"] for r in rows} == {"192.168.1.11"} and {r["dst_ip"] for r in rows} == {"192.168.1.12", "192.168.1.20"}
    assert all(r["severity"] == "HIGH" for r in rows) and rig.detector_calls >= 1
    assert len(rig.events.packet_batches) == 1 and len(rig.events.packet_batches[0]) == 5
    assert {(e["from_host"], e["to_host"]) for e in rig.graph.snapshot()["edges"]} == {("host-a", "host-b"), ("host-a", "server-b")}


def test_scripted_techniques_reach_the_events_part_with_their_notes(rig):
    run_golden(rig, contain=True)
    names = [(t["host"], t["technique_id"], t["compromise"]) for t in rig.events.techniques]
    assert names[0] == ("host-a", "T1046", False) and ("host-a", "T1110", True) in names and ("host-a", "T1048", False) in names


def test_precog_is_told_about_the_compromise_before_the_decision(rig):
    rig.controller.start("golden-path", FAST)
    assert rig.wait_for("waiting_for_decision")
    assert rig.precog.calls == [("compromise", "host-a")]
    rig.controller.resume()
    assert rig.controller.wait_until_done(10)


def test_the_session_is_recorded_and_archived(rig, contracts):
    run_golden(rig, contain=True)
    assert len(rig.world.sessions()) == 1
    session = rig.world.sessions()[0]
    contracts.validate("session_record", session)
    assert session["session_id"] == "ses-000001" and session["scenario_id"] == "golden-path" and session["ended_at"] is not None
    assert len(session["actions"]) == 1


def test_the_world_state_follows_the_replay(rig):
    versions = []
    rig.controller.start("golden-path", FAST)
    assert rig.wait_for("waiting_for_decision")
    versions.append(rig.world.replay()["state"])
    rig.controller.resume()
    assert rig.controller.wait_until_done(10)
    assert versions == ["waiting_for_decision"] and rig.world.replay()["state"] == "finished" and rig.world.replay()["position"] == 5


# ---------- other scenarios ----------
def test_quiet_scan_compromises_nobody_and_never_waits(rig):
    rig.controller.start("quiet-scan", FAST)
    assert rig.controller.wait_until_done(10)
    assert rig.precog.calls == [] and set(rig.graph.states().values()) == {"normal"} and rig.controller.last_decision is None


def test_lateral_spread_without_containment_reaches_the_database(rig):
    rig.controller.start("lateral-spread", FAST)
    assert rig.wait_for("waiting_for_decision")
    rig.controller.resume()
    assert rig.controller.wait_until_done(10)
    assert rig.graph.snapshot()["compromised_path"] == ["host-a", "file-server", "db-server"]


def test_direct_hit_starts_from_the_web_server(rig):
    rig.controller.start("direct-hit", FAST)
    assert rig.wait_for("waiting_for_decision")
    assert rig.precog.calls == [("compromise", "server-b")]
    rig.contain("db-server")
    assert rig.controller.wait_until_done(10)
    assert rig.graph.host_state("db-server") == "contained" and rig.graph.host_state("domain-controller") == "normal"


# ---------- controls ----------
def test_pause_holds_the_replay_and_resume_continues(rig):
    rig.controller.start("quiet-scan", 1.0)
    rig.controller.pause()
    assert rig.controller.status()["state"] == "paused"
    time.sleep(0.3)
    assert rig.controller.status()["state"] == "paused"
    rig.controller.resume()
    assert rig.controller.status()["state"] == "running"
    rig.controller.stop()


def test_controls_that_do_nothing_say_so(rig):
    for call in (rig.controller.pause, rig.controller.resume, rig.controller.restart):
        with pytest.raises(HookError) as info:
            call()
        assert info.value.status == 409


def test_restart_begins_again_from_a_clean_slate(rig):
    run_golden(rig, contain=True)
    status = rig.controller.restart()
    assert status["state"] == "running" and status["scenario_id"] == "golden-path" and status["position"] == 0
    assert rig.wait_for("waiting_for_decision")
    assert rig.graph.host_state("server-b") == "normal" and rig.store.all() == [] or rig.controller.status()["position"] == 3
    assert rig.world.actions() == [] and len(rig.world.sessions()) == 1   # history is kept, the live picture is not
    rig.controller.stop()
    assert rig.controller.status()["state"] == "idle"


def test_stop_ends_a_waiting_replay_quickly(rig):
    rig.controller.start("golden-path", FAST)
    assert rig.wait_for("waiting_for_decision")
    began = time.monotonic()
    rig.controller.stop()
    assert time.monotonic() - began < 2 and rig.controller.status()["state"] == "idle"


def test_a_bug_in_another_part_ends_the_replay_with_a_reason_instead_of_hanging(rig):
    def explode(*args, **kwargs):
        raise ValueError("Unknown host 'host-z'")

    rig.events.process_technique = explode
    rig.controller.start("golden-path", FAST)
    assert rig.controller.wait_until_done(10)
    assert rig.controller.status()["state"] == "finished" and "host-z" in rig.controller.last_error


def test_precog_is_optional(rig):
    rig.hooks._items.pop("precog")
    run_golden(rig, contain=True)
    assert rig.controller.last_error is None


def test_a_new_start_after_finishing_gets_the_next_session_number(rig):
    rig.controller.start("quiet-scan", FAST)
    assert rig.controller.wait_until_done(10)
    rig.controller.start("quiet-scan", FAST)
    assert rig.controller.wait_until_done(10)
    assert [s["session_id"] for s in rig.world.sessions()] == ["ses-000002", "ses-000001"]

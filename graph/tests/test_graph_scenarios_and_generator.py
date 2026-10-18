import copy
import json

import pytest

from graph_net import TOPOLOGY_FILE
from graph_replay import SCENARIOS_DIR, TRAINING_FILE, ScenarioError, ScenarioLibrary, check_scenario, generate_sequences, load_scenario


def golden():
    return json.loads((SCENARIOS_DIR / "golden-path.json").read_text(encoding="utf-8"))


# ---------- the shipped scenarios ----------
def test_four_scenarios_ship_and_all_are_valid(library):
    assert sorted(library.ids()) == ["direct-hit", "golden-path", "lateral-spread", "quiet-scan"]


def test_every_file_name_matches_its_scenario_id(library):
    for scenario_id in library.ids():
        assert (SCENARIOS_DIR / (scenario_id + ".json")).is_file()


def test_golden_path_shape(library):
    events = library.get("golden-path")["events"]
    assert [e["kind"] for e in events] == ["technique", "traffic", "technique", "attempt", "technique"]
    assert events[2]["compromise"] is True and events[3]["pause_for_decision"] is True
    assert events[3]["from_host"] == "host-a" and events[3]["to_host"] == "server-b"


def test_summaries_say_which_scenarios_have_a_decision_point(library):
    by_id = {s["scenario_id"]: s for s in library.summaries()}
    assert by_id["golden-path"]["has_decision_point"] is True and by_id["quiet-scan"]["has_decision_point"] is False
    assert by_id["golden-path"]["events"] == 5


def test_attack_packets_use_ports_nids_treats_as_suspicious(library):
    from graph_replay.packet_store import SUSPICIOUS_PORTS

    for scenario in (library.get("golden-path"), library.get("lateral-spread")):
        for event in scenario["events"]:
            for packet in event.get("packets", []):
                if packet["dst_port"] != 80:
                    assert packet["dst_port"] in SUSPICIOUS_PORTS


# ---------- checking ----------
def test_valid_scenario_passes_with_known_hosts():
    check_scenario(golden(), known_hosts={"host-a", "host-b", "server-b"})


@pytest.mark.parametrize("change,fragment", [
    (lambda s: s.pop("events"), "events"),
    (lambda s: s["events"].clear(), "events"),
    (lambda s: s.update(scenario_id="Bad Id"), "scenario_id"),
    (lambda s: s["events"][0].update(kind="teleport"), "teleport"),
    (lambda s: s["events"][0].update(technique_id="1110"), "technique_id"),
    (lambda s: s["events"][1]["packets"][0].update(protocol="CARRIER-PIGEON"), "protocol"),
    (lambda s: s["events"][1]["packets"][0].update(dst_port=70000), "dst_port"),
    (lambda s: s["events"][0].update(surprise=1), "surprise"),
])
def test_bad_scenarios_are_refused_with_a_useful_message(change, fragment):
    data = golden()
    change(data)
    with pytest.raises(ScenarioError) as info:
        check_scenario(data, name="x.json")
    assert "x.json" in str(info.value)


def test_events_must_be_in_order():
    data = golden()
    data["events"][1]["seq"] = 1
    with pytest.raises(ScenarioError, match="go up"):
        check_scenario(data)
    data = golden()
    data["events"][2]["offset_ms"] = 10
    with pytest.raises(ScenarioError, match="before the one before"):
        check_scenario(data)


def test_unknown_hosts_are_named():
    data = golden()
    data["events"][0]["host"] = "ghost"
    with pytest.raises(ScenarioError, match="ghost"):
        check_scenario(data, known_hosts={"host-a"})


def test_moves_to_oneself_are_refused():
    data = golden()
    data["events"][3]["to_host"] = "host-a"
    with pytest.raises(ScenarioError, match="itself"):
        check_scenario(data)
    data = golden()
    data["events"][1]["packets"][0]["dst_host"] = "host-a"
    with pytest.raises(ScenarioError, match="itself"):
        check_scenario(data)


def test_broken_json_file_is_reported_by_name(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ScenarioError, match="broken.json"):
        load_scenario(bad)


def test_library_refuses_a_mismatched_file_name_or_duplicate_ids(tmp_path):
    data = golden()
    (tmp_path / "wrong-name.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ScenarioError, match="file name"):
        ScenarioLibrary(tmp_path)
    (tmp_path / "wrong-name.json").unlink()
    (tmp_path / "golden-path.json").write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / "other.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ScenarioError):
        ScenarioLibrary(tmp_path)


# ---------- the generator ----------
def test_generator_is_repeatable_and_seed_dependent(topology):
    a = generate_sequences(topology, count=60, seed=1)
    assert a == generate_sequences(topology, count=60, seed=1)
    assert a["sequences"] != generate_sequences(topology, count=60, seed=2)["sequences"]


def test_every_step_follows_a_feasible_connection_and_never_repeats_a_host(topology):
    for sequence in generate_sequences(topology, count=300, seed=0)["sequences"]:
        path = sequence["path"]
        assert path[0] in ("host-a", "host-b") and len(path) == len(set(path)) and len(path) <= 6
        for here, nxt in zip(path, path[1:]):
            assert nxt in topology.connections(here)


def test_all_four_attacker_styles_appear_evenly(topology):
    counts = {}
    for sequence in generate_sequences(topology, count=300, seed=0)["sequences"]:
        counts[sequence["profile"]] = counts.get(sequence["profile"], 0) + 1
    assert counts == {"opportunist": 75, "data-hunter": 75, "domain-chaser": 75, "wanderer": 75}


def test_from_host_a_the_web_server_is_the_most_common_first_move(topology):
    hops = {}
    for sequence in generate_sequences(topology, count=300, seed=0)["sequences"]:
        if sequence["path"][0] == "host-a" and len(sequence["path"]) > 1:
            hops[sequence["path"][1]] = hops.get(sequence["path"][1], 0) + 1
    assert max(hops, key=hops.get) == "server-b"       # this is what makes the rehearsed demo forecast sensible
    assert len(hops) >= 3                              # but other moves happen, so a forecast can also be wrong


def test_the_shipped_training_file_is_what_the_generator_makes(topology):
    shipped = json.loads(TRAINING_FILE.read_text(encoding="utf-8"))
    assert shipped == generate_sequences(topology, count=300, seed=0)

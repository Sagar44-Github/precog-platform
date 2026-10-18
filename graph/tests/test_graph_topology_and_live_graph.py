import json
import threading

import pytest

from graph_net import LiveGraph, Topology, address_of, load_hosts
from graph_net import topology as topology_module
from graph_helpers import REPO_ROOT


# ---------- hosts file ----------
def test_host_file_has_six_hosts(hosts):
    assert [h["host_id"] for h in hosts] == ["host-a", "host-b", "server-b", "file-server", "db-server", "domain-controller"]
    assert address_of(hosts, "server-b") == "192.168.1.20"


def test_address_of_an_unknown_host_names_the_known_ones(hosts):
    with pytest.raises(ValueError) as info:
        address_of(hosts, "nope")
    assert "host-a" in str(info.value)


@pytest.mark.parametrize("change", [lambda h: h.append(dict(h[0])), lambda h: h[0].update(zone="moon"), lambda h: h[0].update(name="")])
def test_bad_host_files_are_refused(tmp_path, change):
    data = json.loads((REPO_ROOT / "contracts" / "data" / "hosts.json").read_text(encoding="utf-8"))
    change(data["hosts"])
    path = tmp_path / "hosts.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_hosts(path)


# ---------- topology ----------
def test_attackgraph_is_the_engine(topology):
    assert topology.engine == "attackgraph"


def test_connections_and_candidates(topology):
    assert topology.connections("host-a") == ["host-b", "server-b", "file-server"]
    assert topology.connections("domain-controller") == []
    assert topology.candidates("host-a", exclude=["host-a", "host-b"]) == ["server-b", "file-server"]


def test_reachability_paths_and_distance(topology):
    assert set(topology.reachable_from("host-a")) == {"host-b", "server-b", "file-server", "db-server", "domain-controller"}
    assert topology.paths("host-a", "db-server", limit=2)[0] in (["host-a", "server-b", "db-server"], ["host-a", "file-server", "db-server"])
    assert topology.distance("host-a", "db-server") == 2 and topology.distance("domain-controller", "host-a") is None


def test_exploit_likelihood_follows_the_simulated_weakness(topology):
    assert topology.edge_probability("host-a", "server-b") > topology.edge_probability("host-a", "host-b")
    assert topology.edge_probability("host-a", "server-b") == pytest.approx(0.98)


def test_risk_scores_exist_for_every_host(topology):
    assert all(topology.risk(h) >= 0 for h in topology.host_ids())
    assert topology.risk("db-server") > topology.risk("host-a")


def test_weakness_ids_are_clearly_simulated():
    data = json.loads((REPO_ROOT / "graph" / "graph_net" / "data" / "topology.json").read_text(encoding="utf-8"))
    ids = [v["id"] for asset in data["assets"].values() for v in asset["vulns"]]
    assert ids and all(i.startswith("DEMO-") for i in ids)


def test_fallback_without_attackgraph_gives_the_same_connections(hosts, topology):
    plain = Topology.from_files(hosts, REPO_ROOT / "graph" / "graph_net" / "data" / "topology.json", use_attackgraph=False)
    assert plain.engine == "networkx-fallback"
    assert plain.feasible_edges() == topology.feasible_edges()
    assert plain.edge_probability("host-a", "server-b") == pytest.approx(0.98)
    assert plain.risk("db-server") > plain.risk("host-a")


def test_missing_library_selects_the_fallback(hosts, monkeypatch):
    monkeypatch.setattr(topology_module, "HAVE_ATTACKGRAPH", False)
    assert Topology.from_files(hosts, REPO_ROOT / "graph" / "graph_net" / "data" / "topology.json").engine == "networkx-fallback"


def test_unknown_hosts_in_the_topology_are_refused(hosts):
    with pytest.raises(ValueError):
        Topology(hosts, {"feasible_connections": {"host-a": ["ghost"]}, "assets": {}})
    with pytest.raises(ValueError):
        Topology(hosts, {"feasible_connections": {"host-a": ["host-a"]}, "assets": {}})


def test_questions_about_unknown_hosts_are_errors(topology):
    for call in (topology.connections, topology.reachable_from, topology.risk):
        with pytest.raises(ValueError):
            call("ghost")


# ---------- live graph ----------
def test_a_new_graph_has_six_normal_hosts_and_nothing_else(graph, contracts):
    snapshot = graph.snapshot()
    contracts.validate("graph_snapshot", snapshot)
    assert {h["state"] for h in snapshot["hosts"]} == {"normal"} and snapshot["edges"] == [] and snapshot["compromised_path"] == []
    assert snapshot["hosts"][0] == {"host_id": "host-a", "name": "Workstation A", "zone": "user", "state": "normal"}


def test_connections_are_recorded_once_with_their_first_time(topology, world):
    times = iter(["2026-10-03T10:00:01Z", "2026-10-03T10:00:02Z"])
    live = LiveGraph(topology, world=world, clock=lambda: next(times))
    assert live.add_connection("host-a", "host-b") is True
    assert live.add_connection("host-a", "host-b") is False
    assert live.snapshot()["edges"] == [{"from_host": "host-a", "to_host": "host-b", "first_seen": "2026-10-03T10:00:01Z"}]


def test_a_host_cannot_connect_to_itself_or_to_nobody(graph):
    assert graph.add_connection("host-a", "host-a") is False
    with pytest.raises(ValueError):
        graph.add_connection("host-a", "ghost")


def test_compromise_builds_the_path_in_order(graph, contracts):
    assert graph.mark_compromised("host-a") is True
    assert graph.mark_compromised("host-a") is False
    graph.mark_compromised("server-b")
    snapshot = graph.snapshot()
    contracts.validate("graph_snapshot", snapshot)
    assert snapshot["compromised_path"] == ["host-a", "server-b"]
    assert graph.host_state("server-b") == "compromised"


def test_a_contained_host_cannot_be_compromised(graph):
    graph.set_host_state("server-b", "contained")
    assert graph.mark_compromised("server-b") is False
    assert graph.host_state("server-b") == "contained" and graph.snapshot()["compromised_path"] == []


def test_attempt_succeeds_on_a_normal_host_and_spreads(graph):
    graph.mark_compromised("host-a")
    outcome = graph.attempt("host-a", "server-b")
    assert outcome == {"result": "success", "from_host": "host-a", "to_host": "server-b"}
    assert graph.host_state("server-b") == "compromised"
    assert {"from_host": "host-a", "to_host": "server-b"}.items() <= graph.snapshot()["edges"][0].items()


def test_attempt_on_a_contained_host_is_blocked_and_leaves_no_trace(graph):
    graph.mark_compromised("host-a")
    graph.set_host_state("server-b", "contained")
    assert graph.attempt("host-a", "server-b")["result"] == "blocked"
    assert graph.snapshot()["edges"] == [] and graph.host_state("server-b") == "contained"


def test_attempt_from_a_contained_host_is_blocked_too(graph):
    graph.mark_compromised("host-a")
    graph.attempt("host-a", "server-b")
    graph.set_host_state("server-b", "contained")          # the attacker loses the web server
    assert graph.attempt("server-b", "db-server")["result"] == "blocked"
    assert graph.host_state("db-server") == "normal"


def test_feasible_targets_leave_out_compromised_and_contained_hosts(graph):
    graph.mark_compromised("host-a")
    graph.set_host_state("server-b", "contained")
    assert graph.feasible_targets("host-a") == ["host-b", "file-server"]


def test_bad_states_and_unknown_hosts_are_refused(graph):
    with pytest.raises(ValueError):
        graph.set_host_state("host-a", "on-fire")
    with pytest.raises(ValueError):
        graph.host_state("ghost")


def test_every_change_reaches_the_world_state(graph, world):
    before = world.version
    graph.mark_compromised("host-a")
    assert world.version > before and world.graph()["compromised_path"] == ["host-a"]


def test_reset_clears_everything(graph, world):
    graph.mark_compromised("host-a")
    graph.add_connection("host-a", "host-b")
    graph.reset()
    assert graph.snapshot()["compromised_path"] == [] and world.graph()["edges"] == []


def test_graph_works_without_a_world(topology):
    LiveGraph(topology).mark_compromised("host-a")


def test_many_threads_changing_the_graph_do_not_corrupt_it(graph):
    def work(i):
        for _ in range(20):
            graph.add_connection("host-a", "host-b")
            graph.mark_compromised("host-a")

    threads = [threading.Thread(target=work, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert graph.snapshot()["compromised_path"] == ["host-a"] and len(graph.snapshot()["edges"]) == 1

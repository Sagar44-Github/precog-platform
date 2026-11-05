"""Read-only network topology, path, segmentation, asset and host-history routes."""

def test_topology_matches_graph_hook_and_is_read_only(logged_in, ctx):
    graph = ctx["hooks"].require("graph")
    before_version = ctx["world"].version
    before_graph = graph.snapshot()
    response = logged_in.get("/api/x/topology")
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert {item["host_id"] for item in result["hosts"]} == set(graph.topology.host_ids())
    assert {(item["from_host"], item["to_host"]) for item in result["feasible_edges"]} == set(graph.topology.feasible_edges())
    assert result["engine"] == graph.topology.engine
    assert all(item["simulated"] is True and item["weakness_id"].startswith("DEMO-") for host in result["hosts"] for item in host["weaknesses"])
    assert {item["zone"] for item in result["zones"]} == {"user", "dmz", "internal"}
    assert result["basis"] and result["risk_basis"]
    assert ctx["world"].version == before_version
    assert graph.snapshot() == before_graph


def test_paths_match_networkx_enumeration_and_validate_inputs(logged_in, ctx):
    topology = ctx["hooks"].require("graph").topology
    response = logged_in.get("/api/x/topology/paths?from=host-a&to=domain-controller&limit=25")
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert [item["hosts"] for item in result["paths"]] == topology.paths("host-a", "domain-controller", limit=25)
    for path in result["paths"]:
        expected = 1.0
        for edge in path["edges"]:
            expected *= topology.edge_probability(edge["from_host"], edge["to_host"])
        assert abs(path["likelihood"] - round(expected, 6)) <= 1e-6
    assert logged_in.get("/api/x/topology/paths?from=unknown&to=host-a").status_code == 404
    assert logged_in.get("/api/x/topology/paths?from=host-a&to=host-b&limit=26").status_code == 400
    assert logged_in.get("/api/x/topology/paths?from=host-a").status_code == 400


def test_segmentation_preview_changes_reachability_without_mutation(logged_in, ctx):
    graph = ctx["hooks"].require("graph")
    before_version = ctx["world"].version
    before_graph = graph.snapshot()
    response = logged_in.get("/api/x/topology/segmentation-preview?from=host-a&remove_from=host-a&remove_to=host-b")
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result["newly_unreachable"] == ["host-b"]
    assert "host-b" in result["reachable_before"] and "host-b" not in result["reachable_after"]
    assert ctx["world"].version == before_version
    assert graph.snapshot() == before_graph
    assert logged_in.get("/api/x/topology/segmentation-preview?from=host-a&remove_from=host-a&remove_to=db-server").status_code == 400


def test_host_detail_includes_asset_risk_and_related_incidents(logged_in):
    response = logged_in.get("/api/x/hosts/server-b")
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result["host"]["name"] == "Web Server B"
    assert result["host"]["services"] == ["http/80", "ssh/22"]
    assert result["host"]["risk"] > 0 and result["host"]["criticality"] == 0.7
    assert result["host"]["weaknesses"][0]["simulated"] is True
    assert isinstance(result["alerts"], list) and isinstance(result["forecasts"], list)
    assert logged_in.get("/api/x/hosts/no-such-host").status_code == 404


def test_host_history_includes_replay_states_alerts_and_related_incident(logged_in, ctx, tmp_path):
    replay = ctx["hooks"].require("replay")
    studio = ctx["hooks"].require("studio")
    studio.runs_dir = tmp_path / "runs"
    studio._runs.clear()
    studio._revision = 0
    replay.settle_seconds = 0
    assert replay.start("quiet-scan", 8)
    assert replay.wait_until_done(5)
    response = logged_in.get("/api/x/hosts/host-b/history?limit=200")
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    kinds = {item["kind"] for item in result["events"]}
    assert "state" in kinds and "alert" in kinds and "incident" in kinds
    assert result["total"] >= len(result["events"])
    assert logged_in.get("/api/x/hosts/host-b/history?limit=501").status_code == 400
    assert logged_in.get("/api/x/hosts/not-a-host/history").status_code == 404

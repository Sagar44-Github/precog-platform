"""Read-only network topology, path, segmentation, asset and host-history routes."""
import pytest


def test_topology_summary_pages_filters_and_aggregates(logged_in, ctx):
    topology = ctx["hooks"].require("graph").topology
    before_version = ctx["world"].version
    first = logged_in.get("/api/x/topology/summary?offset=0&limit=2")
    assert first.status_code == 200, first.get_json()
    page = first.get_json()
    assert len(page["items"]) == 2
    assert page["total_hosts"] == len(topology.host_ids())
    assert page["total_edges"] == len(topology.feasible_edges())
    assert page["next_offset"] == 2
    assert {edge["from_host"] for edge in page["page_edges"]} <= {host["host_id"] for host in page["items"]}
    assert sum(zone["host_count"] for zone in page["zones"]) == len(topology.host_ids())
    assert sum(edge["count"] for edge in page["edge_bundles"]) == len(topology.feasible_edges())
    final = logged_in.get("/api/x/topology/summary?offset=5&limit=2").get_json()
    assert len(final["items"]) == 1 and final["next_offset"] is None
    match = logged_in.get("/api/x/topology/summary?q=Web%20Server%20B").get_json()
    assert match["total_matches"] == 1 and match["items"][0]["host_id"] == "server-b"
    assert logged_in.get("/api/x/topology/summary?zone=not-a-zone").get_json()["items"] == []
    assert ctx["world"].version == before_version


@pytest.mark.parametrize("query", [
    "offset=-1", "offset=not-a-number", "limit=0", "limit=201",
    "q=" + ("x" * 121), "zone=" + ("z" * 81),
])
def test_topology_summary_rejects_invalid_limits(logged_in, query):
    assert logged_in.get("/api/x/topology/summary?" + query).status_code == 400


def test_300_host_workspace_summary_and_asset_inventory(logged_in, flask_app):
    manager = flask_app.extensions["precog_workspaces"]
    pipeline = flask_app.extensions["precog_pipeline"]
    pipeline.stop()
    try:
        activated = logged_in.post("/api/x/workspaces/synth-enterprise-300/activate", json={"confirm": True})
        assert activated.status_code == 200, activated.get_json()
        first = logged_in.get("/api/x/topology/summary?limit=200").get_json()
        second = logged_in.get("/api/x/topology/summary?offset=200&limit=200").get_json()
        assert first["total_hosts"] == 300 and len(first["items"]) == 200
        assert first["next_offset"] == 200
        assert len(second["items"]) == 100 and second["next_offset"] is None
        assert sum(zone["host_count"] for zone in first["zones"]) == 300
        inventory = logged_in.get("/api/x/assets")
        assert inventory.status_code == 200, inventory.get_json()
        assert inventory.get_json()["total"] == 300
    finally:
        pipeline.stop()
        if manager.active.pack_id != "demo-6":
            manager.activate("demo-6")


def test_topology_summary_requires_login(client):
    response = client.get("/api/x/topology/summary")
    assert response.status_code == 401


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

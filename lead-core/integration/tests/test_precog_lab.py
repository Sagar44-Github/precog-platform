import copy
import json

from addons.contracts import Contracts


def error(reply):
    return reply.get_json()["error"]


def test_forecast_explanation_reproduces_transition_formula_and_model_card(logged_in):
    reply = logged_in.get("/api/x/forecasts/fc-000001/explain")
    assert reply.status_code == 200, reply.get_data(as_text=True)
    body = reply.get_json()
    assert body["forecast_id"] == "fc-000001"
    assert body["candidate_set"]
    assert "transition count + alpha" in body["formula"]
    assert body["model_card"]["network_hosts"] == 6
    assert body["metric_standard_error"] == 0.039
    assert all(row["count"] >= 0 for row in body["transition_counts"])
    counts = {row["host_id"]: row["count"] for row in body["transition_counts"]}
    for target in body["target_arithmetic"]:
        expected = (counts[target["host_id"]] + body["alpha"]) / body["formula_denominator"]
        assert round(expected, 4) == target["model_probability"]
        if body["context_source"] == "captured":
            assert target["model_probability"] == target["confidence"]


def test_forecast_explanation_is_not_found_for_unknown_forecast(logged_in):
    reply = logged_in.get("/api/x/forecasts/fc-999999/explain")
    assert reply.status_code == 404 and error(reply)["code"] == "not_found"


def test_whatif_changes_projection_without_mutating_live_state(logged_in, ctx, world):
    before_world = world.snapshot()
    graph = ctx["hooks"].require("graph")
    before_graph = graph.snapshot()
    engine = ctx["hooks"].require("precog")
    before_engine = (copy.deepcopy(engine._pending), copy.deepcopy(engine._resolved))
    reply = logged_in.post("/api/x/whatif", json={"from_host": "host-a", "host_states": {"host-a": "compromised"}, "contain_hosts": ["server-b"]})
    assert reply.status_code == 200, reply.get_data(as_text=True)
    result = reply.get_json()
    assert "server-b" in result["before"]["candidates"]
    assert "server-b" not in result["after"]["candidates"]
    assert result["removed_probability_share"] > 0
    assert result["live_forecast"] == before_world["forecast"]
    assert world.version == before_world["version"]
    assert graph.snapshot() == before_graph
    assert (engine._pending, engine._resolved) == before_engine


def test_whatif_rejects_unknown_hosts_and_impossible_source_state(logged_in):
    unknown = logged_in.post("/api/x/whatif", json={"from_host": "../secret", "host_states": {"../secret": "compromised"}, "contain_hosts": []})
    assert unknown.status_code == 400
    normal = logged_in.post("/api/x/whatif", json={"from_host": "host-a", "host_states": {"host-a": "normal"}, "contain_hosts": []})
    assert normal.status_code == 400
    invalid = logged_in.post("/api/x/whatif", json={"from_host": "host-a", "host_states": {"host-a": "unknown"}, "contain_hosts": []})
    assert invalid.status_code == 400


def test_whatif_is_available_to_viewers_because_it_is_read_only(client):
    import os
    reply = client.post("/api/x/login", json={"username": "viewer", "password": os.environ["VIEWER_PASSWORD"]})
    assert reply.status_code == 200
    result = client.post("/api/x/whatif", json={"from_host": "host-a", "host_states": {"host-a": "compromised"}, "contain_hosts": []})
    assert result.status_code == 200


def test_evaluation_seed_zero_reproduces_shipped_results_and_caches(logged_in, ctx):
    target = ctx["config"].repo_root / "lead-core" / "precog" / "results" / "precog_evaluation.json"
    model_path = ctx["config"].repo_root / "lead-core" / "precog" / "precog_engine" / "data" / "node_model.json"
    shipped = json.loads(target.read_text(encoding="utf-8"))
    shipped_model = model_path.read_bytes()
    first = logged_in.post("/api/x/analytics/evaluate", json={"seed": 0, "test_fraction": 0.2, "alpha_grid": [0.01, 0.05, 0.1, 0.2, 0.5, 1.0]})
    assert first.status_code == 200, first.get_data(as_text=True)
    body = first.get_json()
    for key in ("node_model", "baseline_rule_based", "baseline_uniform", "split", "alpha", "containment_success"):
        assert body["result"][key] == shipped[key]
    again = logged_in.post("/api/x/analytics/evaluate", json={"seed": 0, "test_fraction": 0.2, "alpha_grid": [0.01, 0.05, 0.1, 0.2, 0.5, 1.0]})
    assert again.status_code == 200 and again.get_json()["cached"] is True
    other_seed = logged_in.post("/api/x/analytics/evaluate", json={"seed": 9, "test_fraction": 0.2, "alpha_grid": [0.01, 0.05, 0.1, 0.2, 0.5, 1.0]})
    assert other_seed.status_code == 200
    assert other_seed.get_json()["result"]["node_model"] != body["result"]["node_model"]
    assert target.read_text(encoding="utf-8") == json.dumps(shipped, indent=1, sort_keys=True) + "\n" or json.loads(target.read_text(encoding="utf-8")) == shipped
    assert model_path.read_bytes() == shipped_model


def test_evaluation_validates_caps_roles_and_records_experiment(client, ctx):
    import os
    viewer = client.post("/api/x/login", json={"username": "viewer", "password": os.environ["VIEWER_PASSWORD"]})
    assert viewer.status_code == 200
    denied = client.post("/api/x/analytics/evaluate", json={"seed": 0})
    assert denied.status_code == 403
    client.post("/api/x/logout", json={})
    client.post("/api/x/login", json={"username": "analyst", "password": os.environ["ANALYST_PASSWORD"]})
    invalid = client.post("/api/x/analytics/evaluate", json={"seed": 0, "alpha_grid": [0, 0.1]})
    assert invalid.status_code == 400
    assert client.post("/api/x/analytics/evaluate", json={"seed": 0, "unexpected": True}).status_code == 400
    experiment = client.post("/api/x/analytics/evaluate", json={"seed": 9, "test_fraction": 0.3, "alpha_grid": [0.1]})
    assert experiment.status_code == 200
    assert experiment.get_json()["parameters"]["seed"] == 9
    assert client.get("/api/x/analytics/experiments").status_code == 200
    log_file = ctx["config"].data_dir / "analytics" / "experiments.json"
    assert log_file.is_file() and json.loads(log_file.read_text(encoding="utf-8"))[-1]["experiment_id"] == experiment.get_json()["experiment_id"]
    limited = client.post("/api/x/analytics/evaluate", json={"seed": 9, "test_fraction": 0.3, "alpha_grid": [0.1]})
    assert limited.status_code == 429 and error(limited)["code"] == "rate_limited"


def test_model_overview_returns_held_out_baselines_and_separate_detector_report(logged_in):
    reply = logged_in.get("/api/x/analytics/model")
    assert reply.status_code == 200, reply.get_data(as_text=True)
    body = reply.get_json()
    assert body["evaluation"]["node_model"]["forecasts"] == 149
    assert body["evaluation"]["node_model"]["precision_at_1"] == 0.651
    assert body["evaluation"]["baseline_rule_based"]["precision_at_1"] == 0.6376
    assert "not live" in body["detection_report"]["notes"]


def test_new_precog_contract_samples_validate(ctx):
    contracts = ctx["contracts"]
    assert {"forecast_explanation", "whatif_request", "whatif_result", "evaluation_request", "evaluation_run", "model_card"} <= set(contracts.names())
    for name in ("forecast_explanation", "whatif_request", "whatif_result", "evaluation_request", "evaluation_run", "model_card"):
        sample = json.loads((ctx["config"].contracts_dir / "samples" / (name + ".sample.json")).read_text(encoding="utf-8"))
        contracts.validate(name, sample)

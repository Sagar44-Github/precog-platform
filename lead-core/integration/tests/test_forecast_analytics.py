import copy

import pytest

from addons.loader import ROLE_PACKAGES, AddonContext, _load_role_packages


@pytest.fixture()
def forecast_roles(flask_app, monkeypatch):
    """Install real graph/Precog hooks; the shared test hook registry may be empty."""
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


def test_forecast_ledger_filters_and_detail_keeps_generation_explanation(logged_in):
    forecasts = logged_in.get("/api/x/forecasts?source=repo").get_json()
    assert len(forecasts) == 1
    forecast = forecasts[0]
    assert forecast["session_id"] == "ses-000001"
    explanation = forecast["explanation"]
    assert explanation["model"] == {"name": "markov", "alpha": 0.01}
    assert explanation["technique_hint_source"] == "repo"
    assert explanation["candidate_count"] == 3
    assert explanation["candidate_set"][0]["transition_count"] == 81
    assert explanation["candidate_set"][0]["rule_based_rank"] == 1
    assert logged_in.get("/api/x/forecasts?source=invalid").status_code == 400

    detail = logged_in.get("/api/x/forecasts/fc-000001")
    assert detail.status_code == 200
    assert detail.get_json()["explanation"] == explanation
    assert logged_in.get("/api/x/forecasts/fc-missing").status_code == 404


def test_what_if_is_read_only_and_requires_a_compromised_host(logged_in, forecast_roles):
    world = forecast_roles["world"]
    graph = forecast_roles["hooks"].get("graph")
    graph.mark_compromised("host-a")
    before_version = world.version
    before_forecasts = world.forecasts()
    before_graph = world.graph()

    response = logged_in.get("/api/x/forecasts/what-if?from_host=host-a")
    assert response.status_code == 200
    preview = response.get_json()
    assert preview["from_host"] == "host-a"
    assert [row["host_id"] for row in preview["targets"]] == ["server-b", "file-server", "host-b"]
    assert "Read-only" in preview["note"]
    assert world.version == before_version
    assert world.forecasts() == before_forecasts
    assert world.graph() == before_graph

    assert logged_in.get("/api/x/forecasts/what-if").status_code == 400
    assert logged_in.get("/api/x/forecasts/what-if?from_host=host-b").status_code == 409
    assert logged_in.get("/api/x/forecasts/what-if?from_host=unknown").status_code == 404


def test_archiving_retains_forecast_outcome_and_explanation_for_ledger(logged_in, world):
    forecast = copy.deepcopy(world.forecasts()[0])
    world.resolve_forecast(forecast["forecast_id"], "hit", {"attempted_host": "server-b", "rank_hit": 1, "blocked": False})
    world.archive_session()
    world.reset()

    rows = logged_in.get("/api/x/forecasts?status=hit&include_archived=1").get_json()
    assert len(rows) == 1
    assert rows[0]["session_id"] == "ses-000001"
    assert rows[0]["outcome"]["attempted_host"] == "server-b"
    assert rows[0]["explanation"]["candidate_count"] == 3
    assert logged_in.get("/api/x/forecasts/fc-000001").get_json()["status"] == "hit"
    report = logged_in.get("/api/x/reports/ses-000001").get_json()
    assert report["metrics"]["forecasts_resolved"] == 1
    assert report["forecasts"][0]["explanation"]["candidate_count"] == 3
    world._sessions.clear()


def test_analytics_separates_held_out_evaluation_from_session_counters(logged_in):
    response = logged_in.get("/api/x/analytics")
    assert response.status_code == 200
    data = response.get_json()
    evaluation = data["evaluation"]
    assert evaluation["node_model"]["forecasts"] == 149
    assert evaluation["node_model"]["precision_at_1"] == 0.651
    assert evaluation["node_model"]["precision_at_3"] == 1.0
    assert [item["metrics"]["precision_at_1"] for item in evaluation["baselines"]] == [0.6376, 0.5503]
    assert data["session"]["forecasts_resolved"] == 0
    assert data["live_tally"]["forecasts_resolved"] == 0
    assert "Session counter, not the model's overall accuracy" in data["live_tally"]["honesty_note"]
    assert any("Precision@3 is 1.0" in note for note in data["honesty_notes"])
    assert data["detection_report"]["dataset"] == "CICIDS2017"
    assert any("offline public sample" in note for note in data["honesty_notes"])


def test_analytics_updates_session_tally_using_captured_baseline_rankings(logged_in, world):
    forecast = world.forecasts()[0]
    world.resolve_forecast(forecast["forecast_id"], "miss", {"attempted_host": "file-server", "rank_hit": 2, "blocked": False})
    tally = logged_in.get("/api/x/analytics").get_json()["live_tally"]
    assert tally["forecasts_resolved"] == 1
    assert tally["model"]["rank1_hits"] == 0
    assert tally["rule_based"]["rank1_hits"] == 0
    assert tally["uniform"]["rank1_hits"] == 1


def test_forecast_analytics_routes_require_login(client):
    for path in ("/api/x/forecasts/fc-000001", "/api/x/forecasts/what-if?from_host=host-a", "/api/x/analytics"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.get_json()["error"]["code"] == "not_logged_in"

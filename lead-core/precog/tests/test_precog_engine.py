import json

import pytest

from precog_helpers import GOOD_MODEL, Rig


def compromise(rig, host="host-a"):
    return rig.engine.on_compromise(host)


# ---------- making a forecast ----------
def test_a_forecast_is_a_valid_top_three_with_confidences(rig, contracts):
    forecast = compromise(rig)
    contracts.validate("forecast", forecast)
    assert [t["host_id"] for t in forecast["targets"]] == ["server-b", "file-server", "host-b"]
    assert [t["rank"] for t in forecast["targets"]] == [1, 2, 3]
    assert sum(t["confidence"] for t in forecast["targets"]) == pytest.approx(1.0, abs=0.01)
    assert forecast["status"] == "pending" and forecast["outcome"] is None and forecast["from_host"] == "host-a"
    assert rig.world.current_forecast()["forecast_id"] == "fc-000001"


def test_the_ranking_is_the_models_probabilities(rig):
    first = compromise(rig)["targets"][0]
    assert first["confidence"] == pytest.approx((6 + 0.1) / (10 + 0.3), abs=1e-4)


def test_hosts_already_compromised_or_contained_are_not_candidates(rig):
    rig.graph.states["server-b"] = "contained"
    rig.graph.states["host-b"] = "compromised"
    assert [t["host_id"] for t in compromise(rig)["targets"]] == ["file-server"]


def test_fewer_than_three_candidates_gives_fewer_targets(rig):
    assert len(compromise(rig, "server-b")["targets"]) == 2


def test_nothing_reachable_means_no_forecast_and_no_pending_one(rig):
    assert compromise(rig, "db-server") is None
    assert rig.world.current_forecast() is None


def test_a_new_forecast_supersedes_the_pending_one(rig):
    compromise(rig, "host-a")
    compromise(rig, "server-b")
    statuses = {f["forecast_id"]: f["status"] for f in rig.world.forecasts()}
    assert statuses == {"fc-000001": "superseded", "fc-000002": "pending"}


def test_without_the_graph_part_there_is_no_forecast(rig):
    rig.hooks._items.pop("graph")
    assert compromise(rig) is None


def test_the_technique_hint_follows_the_last_technique_seen_on_that_host(rig):
    rig.world.add_alert({"event_id": "evt-000001", "ts": "2026-10-03T10:00:01Z", "host": "host-a", "packet_id": None, "anomaly": True, "risk_score": 90.0, "severity": "HIGH",
                         "explanation": "Scan.", "technique_id": "T1046", "technique_name": "Network Service Discovery", "source": "scripted"})
    forecast = compromise(rig)
    assert forecast["technique_hint"]["technique_id"] in ("T1016", "T1049") and forecast["source"] == "repo"


def test_the_rule_table_answers_and_is_named_when_the_exported_table_has_no_answer(rig):
    rig.world.add_alert({"event_id": "evt-000001", "ts": "2026-10-03T10:00:01Z", "host": "host-a", "packet_id": None, "anomaly": True, "risk_score": 90.0, "severity": "HIGH",
                         "explanation": "Logins.", "technique_id": "T1110", "technique_name": "Brute Force", "source": "scripted"})
    forecast = compromise(rig)
    assert forecast["technique_hint"] == {"technique_id": "T1078", "technique_name": "Valid Accounts", "probability": 0.5} and forecast["source"] == "lookup"


def test_forecast_source_lookup_is_honoured(contracts):
    rig = Rig(contracts, prefer="lookup")
    rig.world.add_alert({"event_id": "evt-000001", "ts": "2026-10-03T10:00:01Z", "host": "host-a", "packet_id": None, "anomaly": True, "risk_score": 90.0, "severity": "HIGH",
                         "explanation": "Scan.", "technique_id": "T1046", "technique_name": "x", "source": "scripted"})
    forecast = rig.engine.on_compromise("host-a")
    assert forecast["source"] == "lookup" and forecast["technique_hint"]["technique_id"] == "T1110"


def test_no_hint_when_no_technique_was_seen(rig):
    forecast = compromise(rig)
    assert forecast["technique_hint"] is None and forecast["source"] == "repo"


def test_without_a_model_easier_targets_are_ranked_first(contracts):
    rig = Rig(contracts, model=None)
    forecast = rig.engine.on_compromise("host-a")
    assert [t["host_id"] for t in forecast["targets"]] == ["server-b", "file-server", "host-b"]
    assert rig.engine.describe()["node_model"] == "rule-based fallback"


def test_describe_names_the_model(rig):
    assert rig.engine.describe() == {"node_model": "markov", "alpha": 0.1, "technique_source": "repo"}


def test_forecasts_are_audited(rig):
    forecast = compromise(rig)
    assert rig.events.audit[0][:2] == ("forecast", forecast["forecast_id"]) and "Web Server B" in rig.events.audit[0][2]


def test_a_broken_audit_log_never_stops_a_forecast(rig):
    rig.events.audit_record = lambda *a: (_ for _ in ()).throw(RuntimeError("disk full"))
    assert compromise(rig) is not None


# ---------- resolving ----------
def test_a_move_to_the_top_host_is_a_hit_at_rank_one(rig, contracts):
    compromise(rig)
    outcome = rig.engine.on_attempt("host-a", "server-b", False)
    assert outcome == {"attempted_host": "server-b", "rank_hit": 1, "blocked": False}
    done = rig.world.forecasts()[0]
    contracts.validate("forecast", done)
    assert done["status"] == "hit" and done["outcome"]["rank_hit"] == 1
    assert rig.world.current_forecast() is None


def test_a_move_to_the_second_host_is_a_hit_at_rank_two(rig):
    compromise(rig)
    assert rig.engine.on_attempt("host-a", "file-server", False)["rank_hit"] == 2
    assert rig.world.metrics()["precision_at_1"] == 0.0 and rig.world.metrics()["precision_at_3"] == 1.0


def test_a_move_outside_the_top_three_is_a_miss(rig):
    rig.graph.states["server-b"] = "compromised"
    compromise(rig, "host-a")
    rig.world.forecasts()
    outcome = rig.engine.on_attempt("host-a", "db-server", False)
    assert outcome["rank_hit"] is None and rig.world.forecasts()[0]["status"] == "miss"
    assert rig.world.metrics()["hits"] == 0 and rig.world.metrics()["hit_rate"] == 0.0


def test_a_predicted_move_that_was_blocked_is_a_blocked_hit(rig):
    compromise(rig)
    rig.engine.on_attempt("host-a", "server-b", True)
    assert rig.world.forecasts()[0]["outcome"] == {"attempted_host": "server-b", "rank_hit": 1, "blocked": True}


def test_an_attempt_with_no_pending_forecast_is_ignored(rig):
    assert rig.engine.on_attempt("host-a", "server-b", False) is None
    assert rig.world.metrics()["forecasts_resolved"] == 0


def test_the_session_numbers_update_after_each_resolution_and_follow_the_contract(rig, contracts):
    compromise(rig)
    rig.engine.on_attempt("host-a", "server-b", False)
    compromise(rig, "server-b")
    rig.engine.on_attempt("server-b", "file-server", False)
    m = rig.world.metrics()
    contracts.validate("session_metrics", m)
    assert (m["forecasts_resolved"], m["hits"], m["hit_rate"]) == (2, 2, 1.0)
    assert m["precision_at_1"] == 0.5 and m["precision_at_3"] == 1.0
    assert sum(b["count"] for b in m["calibration_bins"]) == 5     # 3 + 2 predictions


def test_containment_success_rate_follows_executed_containments(rig):
    compromise(rig)
    rig.execute_containment("server-b", forecast_id="fc-000001")
    rig.engine.on_attempt("host-a", "server-b", True)
    assert rig.world.metrics()["containment_success_rate"] == 1.0


def test_no_containment_means_no_success_rate(rig):
    compromise(rig)
    rig.engine.on_attempt("host-a", "server-b", False)
    assert rig.world.metrics()["containment_success_rate"] is None


def test_resolution_is_audited(rig):
    compromise(rig)
    rig.engine.on_attempt("host-a", "server-b", True)
    assert "hit at rank 1, the move was blocked" in rig.events.audit[-1][2]


def test_reset_forgets_forecasts_counts_and_numbers(rig):
    compromise(rig)
    rig.engine.on_attempt("host-a", "server-b", False)
    rig.engine.reset()
    assert rig.engine.metrics()["forecasts_resolved"] == 0
    rig.world.reset()
    assert compromise(rig)["forecast_id"] == "fc-000001"


# ---------- the session file ----------
def test_the_session_is_saved_to_a_json_file_when_a_forecast_is_resolved(rig, tmp_path):
    rig.world.set_session({"session_id": "ses-000007", "scenario_id": "golden-path", "started_at": "2026-10-03T10:00:00Z", "ended_at": None, "forecasts": [], "actions": []})
    compromise(rig)
    rig.engine.on_attempt("host-a", "server-b", False)
    saved = json.loads((tmp_path / "sessions" / "ses-000007.json").read_text(encoding="utf-8"))
    assert saved["session"]["scenario_id"] == "golden-path" and saved["metrics"]["hits"] == 1 and saved["forecasts"][0]["status"] == "hit"


def test_a_problem_saving_the_session_never_disturbs_the_run(contracts, tmp_path):
    blocker = tmp_path / "blocked"
    blocker.write_text("a file where a folder should be", encoding="utf-8")
    rig = Rig(contracts, sessions_dir=blocker / "sub")
    rig.world.set_session({"session_id": "ses-000001", "scenario_id": "x", "started_at": "2026-10-03T10:00:00Z", "ended_at": None, "forecasts": [], "actions": []})
    rig.engine.on_compromise("host-a")
    assert rig.engine.on_attempt("host-a", "server-b", False)["rank_hit"] == 1


def test_the_model_counts_used_here_are_the_documented_ones():
    assert GOOD_MODEL["host-a"]["server-b"] == 6

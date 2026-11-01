import math

import pytest

from precog_engine.metrics import calibration_bins, containment_success_rate, expected_calibration_error, session_metrics, zero_metrics
from precog_engine.model import NodeModel, count_moves, negative_log_likelihood, split_sequences, tune_alpha


def seqs(*paths):
    return [{"profile": "p", "path": list(p)} for p in paths]


# ---------- the split ----------
def test_split_is_repeatable_disjoint_and_the_right_size():
    data = seqs(*[("a", str(i)) for i in range(50)])
    train, test = split_sequences(data, seed=0, test_fraction=0.2)
    assert (len(train), len(test)) == (40, 10)
    assert train == split_sequences(data, seed=0)[0]
    assert not ({s["path"][1] for s in train} & {s["path"][1] for s in test})
    assert split_sequences(data, seed=1)[1] != test


# ---------- counting and probabilities ----------
def test_counting_moves():
    assert count_moves(seqs(("a", "b", "c"), ("a", "b"), ("a", "c"))) == {"a": {"b": 2, "c": 1}, "b": {"c": 1}}


def test_the_probability_formula_by_hand():
    model = NodeModel({"a": {"b": 3, "c": 1}}, alpha=0.1)
    p = model.probabilities("a", ["b", "c", "d"])
    assert p["b"] == pytest.approx(3.1 / 4.3) and p["c"] == pytest.approx(1.1 / 4.3) and p["d"] == pytest.approx(0.1 / 4.3)
    assert sum(p.values()) == pytest.approx(1.0)


def test_candidates_not_available_are_renormalised_away():
    model = NodeModel({"a": {"b": 3, "c": 1}}, alpha=0.1)
    p = model.probabilities("a", ["c", "d"])
    assert set(p) == {"c", "d"} and sum(p.values()) == pytest.approx(1.0) and p["c"] > p["d"]


def test_a_host_never_seen_gets_equal_shares_and_so_does_no_data_without_smoothing():
    assert NodeModel({}, alpha=0.1).probabilities("x", ["b", "c"]) == {"b": 0.5, "c": 0.5}
    assert NodeModel({}, alpha=0.0).probabilities("x", ["b", "c", "d"])["b"] == pytest.approx(1 / 3)


def test_top_is_sorted_cut_to_k_and_ties_go_to_the_host_id():
    model = NodeModel({"a": {"b": 2, "c": 2, "d": 5}}, alpha=0.1)
    assert [h for h, _ in model.top("a", ["b", "c", "d", "e"], k=3)] == ["d", "b", "c"]
    assert model.top("a", [], 3) == []
    assert len(model.top("a", ["b", "c"], 3)) == 2


def test_a_negative_alpha_is_refused():
    with pytest.raises(ValueError):
        NodeModel({}, alpha=-1)


def test_save_and_load_keep_everything(tmp_path):
    model = NodeModel.train(seqs(("a", "b"), ("a", "c")), 0.2, meta={"seed": 3})
    model.save(tmp_path / "m.json")
    loaded = NodeModel.load(tmp_path / "m.json")
    assert loaded.counts == model.counts and loaded.alpha == 0.2 and loaded.meta == {"seed": 3}


def test_a_trained_model_is_less_surprised_than_an_untrained_one():
    data = seqs(*[("a", "b")] * 8 + [("a", "c")] * 2)
    candidates = lambda here, path: [c for c in ("b", "c") if c not in path]
    assert negative_log_likelihood(NodeModel.train(data, 0.1), data, candidates) < negative_log_likelihood(NodeModel({}, 0.1), data, candidates)


def test_alpha_is_tuned_on_training_data_only_and_repeatably():
    data = seqs(*[("a", "b")] * 40 + [("a", "c")] * 10)
    candidates = lambda here, path: [c for c in ("b", "c") if c not in path]
    first = tune_alpha(data, candidates, seed=0)
    assert first == tune_alpha(data, candidates, seed=0)
    assert first[0] in first[1] and first[1][first[0]] == min(first[1].values())


# ---------- metrics ----------
def record(fid, targets, attempted, rank, blocked=False):
    return {"forecast_id": fid, "targets": [{"rank": i + 1, "host_id": h, "confidence": c} for i, (h, c) in enumerate(targets)], "attempted_host": attempted, "rank_hit": rank, "blocked": blocked}


def test_calibration_bins_group_by_tenths_and_compare_stated_with_observed():
    bins = calibration_bins([record("a", [("x", 0.74), ("y", 0.15), ("z", 0.07)], "x", 1)])
    by = {b["bin_low"]: b for b in bins}
    assert by[0.7] == {"bin_low": 0.7, "bin_high": 0.8, "mean_confidence": 0.74, "observed_rate": 1.0, "count": 1}
    assert by[0.1]["observed_rate"] == 0.0 and by[0.0]["count"] == 1 and len(bins) == 3


def test_a_confidence_of_exactly_one_goes_in_the_last_bin_and_empty_bins_are_left_out():
    bins = calibration_bins([record("a", [("x", 1.0)], "x", 1)])
    assert len(bins) == 1 and bins[0]["bin_low"] == 0.9 and bins[0]["bin_high"] == 1.0


def test_expected_calibration_error():
    assert expected_calibration_error([{"count": 2, "mean_confidence": 0.8, "observed_rate": 0.5}, {"count": 2, "mean_confidence": 0.2, "observed_rate": 0.2}]) == 0.15
    assert expected_calibration_error([]) is None


def test_session_metrics_count_hits_and_precision():
    records = [record("a", [("x", .6), ("y", .4)], "x", 1), record("b", [("x", .6), ("y", .4)], "y", 2), record("c", [("x", .6), ("y", .4)], "z", None)]
    m = session_metrics(records, [])
    assert (m["forecasts_resolved"], m["hits"], m["hit_rate"], m["precision_at_1"], m["precision_at_3"]) == (3, 2, 0.6667, 0.3333, 0.6667)
    assert m["containment_success_rate"] is None


def test_zero_metrics_and_contract(contracts):
    zero = zero_metrics()
    assert zero["forecasts_resolved"] == 0 and zero["hit_rate"] is None and zero["calibration_bins"] == []
    contracts.validate("session_metrics", zero)
    contracts.validate("session_metrics", session_metrics([record("a", [("x", .74), ("y", .26)], "x", 1)], []))


def action(target, status="executed", forecast_id=None):
    return {"action_id": "act-1", "target_host": target, "forecast_id": forecast_id, "status": status}


def test_containment_success_counts_only_executed_actions_on_predicted_hosts():
    hit = record("fc-1", [("x", .7), ("y", .3)], "x", 1, blocked=True)
    miss = record("fc-2", [("x", .7), ("y", .3)], "z", None, blocked=False)
    assert containment_success_rate([hit, miss], [action("x", forecast_id="fc-1"), action("x", forecast_id="fc-2")]) == 0.5
    assert containment_success_rate([hit], [action("x", status="cancelled")]) is None
    assert containment_success_rate([hit], [action("zzz")]) is None
    assert containment_success_rate([hit], [action("x", forecast_id="fc-9")]) is None
    assert containment_success_rate([hit], [action("y")]) == 1.0

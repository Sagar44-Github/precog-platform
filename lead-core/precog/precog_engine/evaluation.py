"""Honest evaluation of the node-level model (PRD EV-6 to EV-10). Used by tools/evaluate_precog.py and by the tests.

Rules that keep the numbers honest:
  * the test sequences are held out: they are never used for training and never for choosing alpha;
  * each held-out position is one forecast: "the attacker is on host i; candidates are the hosts not yet compromised that i can reach";
  * the numbers come ONLY from held-out sequences, never from the rehearsed golden path (TRD 9.9).
"""
from .metrics import calibration_bins, expected_calibration_error
from .model import ALPHA_GRID, NodeModel, split_sequences, tune_alpha


def _forecast_points(sequences, candidates_fn):
    """Yields (profile, here, candidates, actual_next) for every move in the sequences."""
    for sequence in sequences:
        path = sequence["path"]
        for i in range(len(path) - 1):
            yield sequence.get("profile", "?"), path[i], candidates_fn(path[i], path[: i + 1]), path[i + 1]


def _score(points, ranker, k=3, extended_metrics=False):
    """ranker(here, candidates) -> [(host, probability)] best first."""
    total = first = top_k = more_than_k = 0
    reciprocal_rank = 0.0
    biggest = 0
    records = []
    for _profile, here, candidates, actual in points:
        biggest = max(biggest, len(candidates))
        more_than_k += 1 if len(candidates) > k else 0
        all_ranked = ranker(here, candidates)
        ranked = all_ranked[:k]
        ids = [h for h, _ in all_ranked]
        total += 1
        first += 1 if ids[:1] == [actual] else 0
        top_k += 1 if actual in ids[:k] else 0
        if actual in ids:
            reciprocal_rank += 1.0 / (ids.index(actual) + 1)
        records.append({"targets": [{"host_id": h, "confidence": p} for h, p in ranked], "attempted_host": actual})
    bins = calibration_bins([dict(r, forecast_id="x") for r in records])
    p1 = first / total
    result = {"forecasts": total, "precision_at_1": round(p1, 4), "precision_at_1_std_error": round((p1 * (1 - p1) / total) ** 0.5, 4),
              "precision_at_3": round(top_k / total, 4), "max_candidates": biggest,
              "share_with_more_than_3_candidates": round(more_than_k / total, 4),
              "calibration_bins": bins, "expected_calibration_error": expected_calibration_error(bins)}
    if extended_metrics:
        result["mean_reciprocal_rank"] = round(reciprocal_rank / total, 4)
    return result


def evaluate(sequences, candidates_fn, edge_probability_fn, seed=0, test_fraction=0.2, grid=ALPHA_GRID, extended_metrics=False):
    train, test = split_sequences(sequences, seed=seed, test_fraction=test_fraction)
    alpha, alpha_scores = tune_alpha(train, candidates_fn, grid=grid, seed=seed)
    model = NodeModel.train(train, alpha, meta={"seed": seed, "test_fraction": test_fraction, "training_sequences": len(train), "alpha_chosen_on": "a validation part of the training data"})
    points = list(_forecast_points(test, candidates_fn))
    candidate_distribution = {}
    if extended_metrics:
        for _profile, _here, candidates, _actual in points:
            candidate_distribution[str(len(candidates))] = candidate_distribution.get(str(len(candidates)), 0) + 1

    def uniform(here, candidates):
        return [(c, 1.0 / len(candidates)) for c in sorted(candidates)]

    def rule_based(here, candidates):  # no learning: easier-to-attack hosts first (the fallback ranking)
        weights = {c: max(edge_probability_fn(here, c), 0.01) for c in candidates}
        total = sum(weights.values())
        return sorted(((c, w / total) for c, w in weights.items()), key=lambda item: (-item[1], item[0]))

    def markov_all(here, candidates):
        return model.top(here, candidates, k=len(candidates))

    result = {"node_model": _score(points, markov_all, extended_metrics=extended_metrics),
              "baseline_rule_based": _score(points, rule_based, extended_metrics=extended_metrics),
              "baseline_uniform": _score(points, uniform, extended_metrics=extended_metrics)}
    by_profile = {}
    for profile in sorted({p[0] for p in points}):
        by_profile[profile] = _score([p for p in points if p[0] == profile], markov_all, extended_metrics=extended_metrics)
        by_profile[profile].pop("calibration_bins")
    # Containing the top-ranked host (one tap) stops the chain only when the attacker's next move was that host; containing the
    # whole Top-3 stops it when the move was any of them. In this replay setting these equal precision@1 and precision@3.
    result["containment_success"] = {"contain_top_1": result["node_model"]["precision_at_1"], "contain_top_3": result["node_model"]["precision_at_3"]}
    result["by_profile"] = by_profile
    if extended_metrics:
        result["candidate_set_distribution"] = {key: candidate_distribution[key] for key in sorted(candidate_distribution, key=int)}
    result["split"] = {"seed": seed, "training_sequences": len(train), "test_sequences": len(test), "test_forecasts": len(points)}
    result["alpha"] = {"chosen": alpha, "validation_surprise": {str(a): round(s, 4) for a, s in alpha_scores.items()}}
    return model, result

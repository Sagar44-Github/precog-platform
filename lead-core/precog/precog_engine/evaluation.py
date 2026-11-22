"""Honest evaluation of the node-level model (PRD EV-6 to EV-10). Used by tools/evaluate_precog.py and by the tests.

Rules that keep the numbers honest:
  * the test sequences are held out: they are never used for training and never for choosing alpha;
  * each held-out position is one forecast: "the attacker is on host i; candidates are the hosts not yet compromised that i can reach";
  * the numbers come ONLY from held-out sequences, never from the rehearsed golden path (TRD 9.9).
"""
import math

from .metrics import calibration_bins, expected_calibration_error
from .model import (ALPHA_GRID, CONTEXT_WEIGHT_GRID, SOURCE_ZONE_WEIGHT_GRID,
                    NodeModel, split_sequences, tune_alpha)


def _forecast_points(sequences, candidates_fn):
    """Yields (profile, here, candidates, actual_next) for every move in the sequences."""
    for sequence in sequences:
        path = sequence["path"]
        for i in range(len(path) - 1):
            yield sequence.get("profile", "?"), path[i], candidates_fn(path[i], path[: i + 1]), path[i + 1], i


def _score(points, ranker, k=3, extended_metrics=False):
    """ranker(here, candidates) -> [(host, probability)] best first."""
    total = first = top_k = more_than_k = 0
    negative_log_likelihood = 0.0
    reciprocal_rank = 0.0
    biggest = 0
    records = []
    for _profile, here, candidates, actual, stage in points:
        biggest = max(biggest, len(candidates))
        more_than_k += 1 if len(candidates) > k else 0
        all_ranked = ranker(here, candidates, stage)
        ranked = all_ranked[:k]
        ids = [h for h, _ in all_ranked]
        total += 1
        actual_probability = next((probability for host, probability in all_ranked if host == actual), 0.0)
        negative_log_likelihood += -math.log(max(actual_probability, 1e-12))
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
        result["log_loss"] = round(negative_log_likelihood / total, 6)
    return result


def _candidate_classification(points, ranker):
    """One-vs-rest candidate confusion for the sole Top-1 recommendation.

    This is intentionally accompanied by Top-1 forecast accuracy: candidate negatives
    dominate the binary accuracy in large graphs.
    """
    tp = fp = fn = tn = forecasts = correct = 0
    for _profile, here, candidates, actual, stage in points:
        if actual not in candidates:
            raise ValueError("Held-out route hop %s -> %s is not in its feasible candidate set" % (here, actual))
        ranked = ranker(here, candidates, stage)
        predicted = ranked[0][0] if ranked else None
        forecasts += 1
        if predicted == actual:
            tp += 1
            tn += max(0, len(candidates) - 1)
            correct += 1
        else:
            fp += 1
            fn += 1
            tn += max(0, len(candidates) - 2)
    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {
        "unit": "candidate-one-vs-rest",
        "positive_label": "actual next host",
        "prediction_rule": "rank 1 is the sole positive candidate",
        "top1_forecast_accuracy": round(correct / forecasts, 4) if forecasts else 0.0,
        "accuracy": round((tp + tn) / total, 4) if total else 0.0,
        "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
        "false_positive_rate": round(fp / (fp + tn), 4) if fp + tn else 0.0,
        "false_negative_rate": round(fn / (fn + tp), 4) if fn + tp else 0.0,
        "confusion_matrix": {"labels": ["not next", "actual next"], "matrix": [[tn, fp], [fn, tp]]},
    }


def _tune_context_model(train, candidates_fn, host_zones, seed, grid, context_weight_grid,
                        source_zone_weight_grid):
    fit, validation = split_sequences(train, seed=seed + 1, test_fraction=0.2)
    validation_points = list(_forecast_points(validation, candidates_fn))
    scores = {}
    for alpha in grid:
        for context_weight in context_weight_grid:
            for source_zone_weight in source_zone_weight_grid:
                candidate_model = NodeModel.train(fit, alpha, host_zones=host_zones,
                    context_weight=context_weight, source_zone_weight=source_zone_weight)
                loss = 0.0
                moves = 0
                for _profile, here, candidates, actual, stage in validation_points:
                    probabilities = candidate_model.probabilities(here, candidates, stage=stage)
                    loss += -math.log(max(probabilities.get(actual, 1e-12), 1e-12))
                    moves += 1
                scores[(float(alpha), float(context_weight), float(source_zone_weight))] = loss / moves if moves else float("inf")
    chosen_alpha, chosen_weight, chosen_source_weight = min(
        scores, key=lambda value: (scores[value], value[0], -value[1], -value[2]))
    best_by_alpha = {alpha: min(loss for (candidate_alpha, _weight, _source_weight), loss in scores.items()
                                if candidate_alpha == alpha) for alpha in map(float, grid)}
    return chosen_alpha, chosen_weight, chosen_source_weight, best_by_alpha, {
        "%s|%s|%s" % (alpha, weight, source_weight): round(loss, 6)
        for (alpha, weight, source_weight), loss in scores.items()
    }


def evaluate(sequences, candidates_fn, edge_probability_fn, seed=0, test_fraction=0.2, grid=ALPHA_GRID,
             extended_metrics=False, host_zones=None, context_weight_grid=CONTEXT_WEIGHT_GRID,
             source_zone_weight_grid=SOURCE_ZONE_WEIGHT_GRID):
    train, test = split_sequences(sequences, seed=seed, test_fraction=test_fraction)
    context_weight = None
    source_zone_weight = None
    if host_zones:
        alpha, context_weight, source_zone_weight, alpha_scores, context_weight_scores = _tune_context_model(
            train, candidates_fn, host_zones, seed, grid, context_weight_grid, source_zone_weight_grid)
    else:
        alpha, alpha_scores = tune_alpha(train, candidates_fn, grid=grid, seed=seed)
    meta = {"seed": seed, "test_fraction": test_fraction, "training_sequences": len(train),
            "alpha_chosen_on": "a validation part of the training data"}
    model = NodeModel.train(train, alpha, meta=meta, host_zones=host_zones,
                            context_weight=context_weight if context_weight is not None else 1.0,
                            source_zone_weight=source_zone_weight if source_zone_weight is not None else 0.5)
    points = list(_forecast_points(test, candidates_fn))
    candidate_distribution = {}
    if extended_metrics:
        for _profile, _here, candidates, _actual, _stage in points:
            candidate_distribution[str(len(candidates))] = candidate_distribution.get(str(len(candidates)), 0) + 1

    def uniform(here, candidates, _stage):
        return [(c, 1.0 / len(candidates)) for c in sorted(candidates)]

    def rule_based(here, candidates, _stage):  # no learning: easier-to-attack hosts first (the fallback ranking)
        weights = {c: max(edge_probability_fn(here, c), 0.01) for c in candidates}
        total = sum(weights.values())
        return sorted(((c, w / total) for c, w in weights.items()), key=lambda item: (-item[1], item[0]))

    def markov_all(here, candidates, stage):
        return model.top(here, candidates, k=len(candidates), stage=stage)

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
    if context_weight is not None:
        result["prediction_context"] = {
            "kind": "route-stage-source-zone-v2", "context_weight": context_weight,
            "source_zone_weight": source_zone_weight,
            "context_weight_grid": list(context_weight_grid),
            "source_zone_weight_grid": list(source_zone_weight_grid),
            "validation_surprise": context_weight_scores,
        }
    if extended_metrics:
        result["classification"] = _candidate_classification(points, markov_all)
    return model, result

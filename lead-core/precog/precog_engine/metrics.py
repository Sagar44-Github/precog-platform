"""The numbers the paper reports (PRD EV-6 to EV-10), as plain functions with no state, so they are easy to test.

A "resolved record" is one forecast whose outcome is known:
    {"forecast_id": "fc-000001", "targets": [{"rank": 1, "host_id": "server-b", "confidence": 0.46}, ...],
     "attempted_host": "server-b", "rank_hit": 1 or 2 or 3 or None, "blocked": True or False}
"""

BIN_WIDTH = 0.1


def _ratio(count, total):
    return round(count / total, 4) if total else None


def calibration_bins(records):
    """Every target of every resolved forecast is one prediction: its stated confidence, and whether it was the host the attacker tried.
    Predictions are grouped into bins of width 0.1; each bin compares its average stated confidence with how often it was right.
    Empty bins are left out."""
    bins = {}
    for record in records:
        for target in record["targets"]:
            index = min(int(target["confidence"] / BIN_WIDTH), 9)
            confidences, outcomes = bins.setdefault(index, ([], []))
            confidences.append(target["confidence"])
            outcomes.append(1.0 if target["host_id"] == record["attempted_host"] else 0.0)
    result = []
    for index in sorted(bins):
        confidences, outcomes = bins[index]
        result.append({"bin_low": round(index * BIN_WIDTH, 1), "bin_high": round((index + 1) * BIN_WIDTH, 1),
                       "mean_confidence": round(sum(confidences) / len(confidences), 4),
                       "observed_rate": round(sum(outcomes) / len(outcomes), 4), "count": len(confidences)})
    return result


def expected_calibration_error(bins):
    """The size-weighted average gap between stated confidence and observed rate (0 is perfect)."""
    total = sum(b["count"] for b in bins)
    return round(sum(b["count"] * abs(b["mean_confidence"] - b["observed_rate"]) for b in bins) / total, 4) if total else None


def containment_success_rate(records, actions):
    """Of the resolved forecasts where an EXECUTED containment was applied to one of the predicted hosts, the share where the
    attacker's next move was blocked (the chain ended early). None when no containment was applied."""
    applied = success = 0
    for record in records:
        predicted = {t["host_id"] for t in record["targets"]}
        used = [a for a in actions if a["status"] == "executed" and a["target_host"] in predicted and a["forecast_id"] in (None, record["forecast_id"])]
        if used:
            applied += 1
            success += 1 if record["blocked"] else 0
    return _ratio(success, applied)


def session_metrics(records, actions):
    """The session_metrics contract: hit rate, precision@1, precision@3, calibration bins, containment success."""
    total = len(records)
    hits = sum(1 for r in records if r["rank_hit"] is not None)
    return {"forecasts_resolved": total, "hits": hits, "hit_rate": _ratio(hits, total),
            "precision_at_1": _ratio(sum(1 for r in records if r["rank_hit"] == 1), total),
            "precision_at_3": _ratio(sum(1 for r in records if r["rank_hit"] is not None and r["rank_hit"] <= 3), total),
            "calibration_bins": calibration_bins(records), "containment_success_rate": containment_success_rate(records, actions)}


def zero_metrics():
    return session_metrics([], [])

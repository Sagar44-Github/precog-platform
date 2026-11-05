"""The Precog Engine hook: forecasts the attacker's next host, resolves each forecast, and keeps the session numbers.

The replay (GRAPH) calls three methods while it plays:
    reset()                              a new replay begins
    on_compromise(host)                  a host became compromised -> make a forecast from it
    on_attempt(from_host, to_host, blocked)   the attacker's next move is seen -> the pending forecast is resolved
A forecast is a Top-3 list of hosts with confidences (the node-level Markov model), plus a technique hint and the name of
the table that produced it. Resolving it as hit or miss updates the live accuracy numbers (precision@1, precision@3,
calibration, containment success) in the shared world state, so both clients show them.
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from .metrics import session_metrics, zero_metrics

log = logging.getLogger("precog.engine")


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class PrecogEngine:
    def __init__(self, world, hooks, model, technique_layer, contracts=None, clock=utc_now, sessions_dir=None, top_k=3):
        """model: a NodeModel, or None (then hosts are ranked by how easy they are to attack, the rule-based fallback)."""
        self.world, self.hooks, self.model, self.layer = world, hooks, model, technique_layer
        self.contracts, self._clock, self.sessions_dir, self.top_k = contracts, clock, sessions_dir, top_k
        self._counter = 0
        self._pending = None
        self._resolved = []

    # ---------- the hook interface ----------
    def reset(self):
        self._counter = 0
        self._pending = None
        self._resolved = []

    def on_compromise(self, host):
        """Makes and publishes a forecast from `host`. Returns it, or None when no host is left to forecast."""
        graph = self.hooks.get("graph")
        if graph is None:
            log.warning("No forecast: the graph part is missing")
            return None
        candidates = graph.feasible_targets(host)
        if not candidates:
            self._pending = None
            return None          # "no forecast available": nothing reachable is left
        preview = self.preview(host, candidates)
        self._counter += 1
        forecast = {"forecast_id": "fc-%06d" % self._counter, "ts": self._clock(), "from_host": host,
                    "targets": preview["targets"], "technique_hint": preview["technique_hint"], "source": preview["source"],
                    "status": "pending", "outcome": None, "explanation": preview["explanation"]}
        if self.contracts is not None:
            self.contracts.validate("forecast", forecast)
        self.world.set_forecast(forecast)
        self._pending = forecast
        names = self._names(graph)
        self._audit(forecast["forecast_id"], "Forecast from %s: %s." % (names.get(host, host), ", ".join(
            "%s %d %%" % (names.get(t["host_id"], t["host_id"]), round(t["confidence"] * 100)) for t in forecast["targets"])))
        return forecast

    def preview(self, host, candidates):
        """Explain a forecast without publishing it or changing replay state (used by the read-only what-if route)."""
        graph = self.hooks.get("graph")
        topology = getattr(graph, "topology", None) if graph is not None else None
        candidates = list(dict.fromkeys(candidates))

        if self.model is not None:
            model_probabilities = self.model.probabilities(host, candidates)
        else:
            model_probabilities = self._rule_probabilities(topology, host, candidates)
        rule_probabilities = self._rule_probabilities(topology, host, candidates)
        uniform_probabilities = {candidate: 1.0 / len(candidates) for candidate in candidates} if candidates else {}

        def ranks(probabilities):
            ordered = sorted(probabilities, key=lambda candidate: (-probabilities[candidate], candidate))
            return {candidate: index + 1 for index, candidate in enumerate(ordered)}

        model_ranks = ranks(model_probabilities)
        rule_ranks = ranks(rule_probabilities)
        uniform_ranks = ranks(uniform_probabilities)
        counts = self.model.counts.get(host, {}) if self.model is not None else {}
        candidate_rows = [{
            "host_id": candidate,
            "transition_count": int(counts.get(candidate, 0)),
            "model_probability": round(model_probabilities[candidate], 6),
            "model_rank": model_ranks[candidate],
            "rule_based_probability": round(rule_probabilities[candidate], 6),
            "rule_based_rank": rule_ranks[candidate],
            "uniform_probability": round(uniform_probabilities[candidate], 6),
            "uniform_rank": uniform_ranks[candidate],
        } for candidate in sorted(candidates, key=lambda item: (model_ranks[item], item))]
        hint, source = self.layer.hint(self._last_technique(host)) if self.layer else (None, "lookup")
        explanation = {
            "model": {"name": "markov" if self.model else "rule_based_fallback", "alpha": self.model.alpha if self.model else None},
            "technique_hint_source": source,
            "candidate_count": len(candidate_rows),
            "candidate_set": candidate_rows,
        }
        targets = [{"rank": index + 1, "host_id": row["host_id"], "confidence": round(row["model_probability"], 4)}
                   for index, row in enumerate(candidate_rows[:self.top_k])]
        return {"targets": targets, "technique_hint": hint, "source": source, "explanation": explanation}

    def on_attempt(self, from_host, to_host, blocked):
        """The attacker tried to move. Resolves the pending forecast as a hit (at rank 1 to 3) or a miss."""
        forecast = self._pending
        if forecast is None:
            return None
        ids = [t["host_id"] for t in forecast["targets"]]
        rank_hit = ids.index(to_host) + 1 if to_host in ids else None
        outcome = {"attempted_host": to_host, "rank_hit": rank_hit, "blocked": bool(blocked)}
        status = "hit" if rank_hit else "miss"
        self.world.resolve_forecast(forecast["forecast_id"], status, outcome)
        self._pending = None
        self._resolved.append({"forecast_id": forecast["forecast_id"], "targets": forecast["targets"], "attempted_host": to_host,
                               "rank_hit": rank_hit, "blocked": bool(blocked)})
        self.refresh_metrics()
        graph = self.hooks.get("graph")
        names = self._names(graph) if graph is not None else {}
        words = ("hit at rank %d" % rank_hit if rank_hit else "miss") + (", the move was blocked" if blocked else "")
        self._audit(forecast["forecast_id"], "Forecast resolved: %s (the attacker tried %s)." % (words, names.get(to_host, to_host)))
        return outcome

    # ---------- numbers ----------
    def metrics(self):
        return session_metrics(self._resolved, self.world.actions())

    def refresh_metrics(self):
        """Recomputes the session numbers and publishes them (also called when a containment changes the success rate)."""
        metrics = self.metrics()
        if self.contracts is not None:
            self.contracts.validate("session_metrics", metrics)
        self.world.set_metrics(metrics)
        self._write_session(metrics)
        return metrics

    def describe(self):
        return {"node_model": "markov" if self.model else "rule-based fallback", "alpha": self.model.alpha if self.model else None,
                "technique_source": self.layer.default_source if self.layer else "lookup"}

    # ---------- internals ----------
    @staticmethod
    def _rule_probabilities(topology, host, candidates):
        weights = {candidate: max(topology.edge_probability(host, candidate), 0.01) if topology else 1.0 for candidate in candidates}
        total = sum(weights.values())
        return {candidate: weight / total for candidate, weight in weights.items()} if total else {}

    def _last_technique(self, host):
        for alert in self.world.alerts(200):                  # newest first
            if alert["host"] == host and alert["technique_id"]:
                return alert["technique_id"]
        return None

    @staticmethod
    def _names(graph):
        return {h["host_id"]: h["name"] for h in graph.snapshot()["hosts"]}

    def _audit(self, ref_id, summary):
        events = self.hooks.get("events")
        if events is not None:
            try:
                events.audit_record("forecast", ref_id, summary)
            except Exception:
                log.exception("Could not write the audit entry")

    def _write_session(self, metrics):
        """Saves the session to a JSON file (TRD 8.8). A problem here must never disturb the demo."""
        session = self.world.session()
        if not self.sessions_dir or not session:
            return
        try:
            folder = Path(self.sessions_dir)
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / (session["session_id"] + ".json")
            temp = target.with_suffix(".tmp")
            temp.write_text(json.dumps({"session": session, "forecasts": self.world.forecasts(), "actions": self.world.actions(), "metrics": metrics}, indent=1) + "\n", encoding="utf-8")
            os.replace(temp, target)
        except Exception:
            log.exception("Could not save the session file")

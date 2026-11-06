"""Explainable, read-only Precog projections and held-out evaluation runs."""
import copy
import json
import os
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

from precog_engine.evaluation import evaluate
from precog_engine.model import ALPHA_GRID, NodeModel


MAX_EXPERIMENTS = 50
MAX_ALPHA_GRID = 6


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rank(probabilities):
    return [{"rank": index + 1, "host_id": host, "confidence": round(probability, 4)}
            for index, (host, probability) in enumerate(sorted(probabilities.items(), key=lambda item: (-item[1], item[0]))[:3])]


class PrecogLab:
    def __init__(self, ctx):
        self.ctx = ctx
        root = Path(ctx.config.repo_root)
        self.training_path = root / "graph" / "graph_replay" / "training" / "sequences.json"
        self.evaluation_path = root / "lead-core" / "precog" / "results" / "precog_evaluation.json"
        self.model_path = root / "lead-core" / "precog" / "precog_engine" / "data" / "node_model.json"
        self.detection_path = root / "detect" / "offline_model" / "results" / "detection_report.json"
        self.data_dir = Path(ctx.config.data_dir) / "analytics"
        self._lock = threading.RLock()
        self._cache = OrderedDict()
        self._experiments = []
        self._load_experiments()

    @property
    def graph(self):
        return self.ctx.hooks.require("graph")

    @property
    def engine(self):
        return self.ctx.hooks.get("precog")

    @property
    def dataset_context(self):
        manager = self.ctx.flask_app.extensions.get("precog_workspaces")
        return manager.active if manager is not None else getattr(self.ctx, "dataset_context", None)

    def explain(self, forecast_id):
        forecast = next((item for item in self.ctx.world.forecasts() if item["forecast_id"] == forecast_id), None)
        if forecast is None:
            raise KeyError(forecast_id)
        graph, engine = self.graph, self.engine
        context = engine.explanation_context(forecast_id) if engine is not None and hasattr(engine, "explanation_context") else None
        topology = graph.topology
        model = engine.model if engine is not None else None
        context_source = "captured"
        if context is None:
            # Sample mode ships a forecast without a live-engine sidecar. Rebuild
            # its best available context from the sampled graph and disclose the
            # estimate basis on the page; replay-generated forecasts use exact capture.
            states = {item["host_id"]: item["state"] for item in self.ctx.world.graph().get("hosts", [])}
            context_source = "reconstructed"
            candidates = topology.candidates(forecast["from_host"], exclude=[host for host, state in states.items() if state != "normal"])
            if not candidates:
                candidates = [target["host_id"] for target in forecast["targets"]]
            model_row = model.counts.get(forecast["from_host"], {}) if model is not None else {}
            context = {"candidate_ids": candidates, "host_states": states,
                       "transition_counts": {candidate: int(model_row.get(candidate, 0)) for candidate in candidates},
                       "alpha": model.alpha if model is not None else None}
        candidates = list(context.get("candidate_ids") or [target["host_id"] for target in forecast["targets"]])
        states = context.get("host_states", {})
        excluded = []
        for host_id in topology.connections(forecast["from_host"]):
            state = states.get(host_id, "normal")
            if host_id not in candidates:
                excluded.append({"host_id": host_id, "state": state,
                                 "reason": "already compromised" if state == "compromised" else "simulated containment" if state == "contained" else "not in the captured feasible candidate set"})
        alpha = context.get("alpha", model.alpha if model else None)
        model_row = model.counts.get(forecast["from_host"], {}) if model is not None else {}
        counts = {host: int(context.get("transition_counts", {}).get(host, model_row.get(host, 0))) for host in candidates}
        total = sum(int(counts.get(host, 0)) for host in candidates)
        denominator = total + (float(alpha) * len(candidates) if alpha is not None else 0)
        if model is not None:
            probabilities = model.probabilities(forecast["from_host"], candidates)
        else:
            weights = {host: max(float(topology.edge_probability(forecast["from_host"], host)), 0.01) for host in candidates}
            mass = sum(weights.values()) or 1
            probabilities = {host: weight / mass for host, weight in weights.items()}
        rows = []
        for item in forecast["targets"]:
            host = item["host_id"]
            count = int(counts.get(host, 0))
            model_probability = probabilities.get(host, 0.0)
            formula = ("(%d + %s) / (%d + %s × %d) = %.4f" %
                       (count, _num(alpha), total, _num(alpha), len(candidates), model_probability)) if alpha is not None else "Rule-based fallback using simulated edge likelihoods."
            rows.append({"host_id": host, "transition_count": count, "confidence": item["confidence"],
                         "model_probability": round(model_probability, 4), "formula": formula})
        uniform = {host: 1 / len(candidates) for host in candidates} if candidates else {}
        rule_weights = {host: max(float(topology.edge_probability(forecast["from_host"], host)), 0.01) for host in candidates}
        rule_total = sum(rule_weights.values()) or 1
        rule = {host: weight / rule_total for host, weight in rule_weights.items()}
        target_confidence = forecast["targets"][0]["confidence"] if forecast["targets"] else None
        calibration = None
        if target_confidence is not None:
            evaluation = self.shipped_evaluation()
            calibration = next((item for item in evaluation["node_model"]["calibration_bins"]
                               if item["bin_low"] <= target_confidence < item["bin_high"] or (item["bin_high"] == 1.0 and target_confidence == 1.0)), None)
        shipped = self.shipped_evaluation()
        return {
            "forecast_id": forecast_id,
            "context_source": context_source,
            "candidate_set": candidates,
            "excluded": excluded,
            "from_host": forecast["from_host"],
            "transition_counts": [{"host_id": host, "count": int(counts.get(host, 0))} for host in candidates],
            "alpha": alpha,
            "formula": "P(target | source) = (transition count + alpha) / (counts across feasible candidates + alpha × candidate count)",
            "formula_denominator": round(denominator, 6),
            "target_arithmetic": rows,
            "baseline_rule_based": _rank(rule),
            "baseline_uniform": _rank(uniform),
            "technique_hint": forecast.get("technique_hint"),
            "technique_table": forecast.get("source"),
            "calibration_bin": calibration,
            "metric_standard_error": shipped["node_model"]["precision_at_1_std_error"],
            "model_card": self.model_card(),
            "outcome": {"status": forecast["status"], "result": forecast.get("outcome")},
        }

    def whatif(self, data):
        topology, engine, graph = self.graph.topology, self.engine, self.graph
        known = set(topology.host_ids())
        source = data["from_host"]
        if source not in known:
            raise ValueError("Unknown demo host '%s'." % source)
        states = dict(graph.states())
        overrides = data.get("host_states", {})
        for host, state in overrides.items():
            if host not in known:
                raise ValueError("Unknown demo host '%s' in host_states." % host)
            if state not in ("normal", "compromised", "contained"):
                raise ValueError("Host state for '%s' must be normal, compromised or contained." % host)
            states[host] = state
        if states.get(source) != "compromised":
            raise ValueError("from_host must be compromised in the hypothetical state.")
        contain = data.get("contain_hosts", [])
        if len(contain) != len(set(contain)):
            raise ValueError("contain_hosts cannot contain duplicates.")
        for host in contain:
            if host not in known:
                raise ValueError("Unknown demo host '%s' in contain_hosts." % host)
            if host == source:
                raise ValueError("The hypothetical source host cannot also be contained.")
        before_candidates = topology.candidates(source, exclude=[host for host, state in states.items() if state != "normal"])
        after_states = dict(states)
        for host in contain:
            after_states[host] = "contained"
        after_candidates = topology.candidates(source, exclude=[host for host, state in after_states.items() if state != "normal"])

        def probabilities(candidates):
            if engine is not None and engine.model is not None:
                return engine.model.probabilities(source, candidates)
            weights = {host: max(float(topology.edge_probability(source, host)), 0.01) for host in candidates}
            total = sum(weights.values()) or 1
            return {host: weight / total for host, weight in weights.items()}

        before, after = probabilities(before_candidates), probabilities(after_candidates)
        removed = sum(before.get(host, 0) for host in contain if host in before)
        existing_forecasts = self.ctx.world.forecasts()
        current = existing_forecasts[-1] if existing_forecasts else None
        dataset = self.dataset_context
        if dataset is not None and dataset.pack_id != "demo-6":
            route_source = dataset.manifest.get("capabilities", {}).get("lateral_movement_routes", "none")
            basis = ("Model-based estimate over %d hosts in dataset workspace %s; route ground truth is %s. "
                     "This is a simulated what-if on recorded data; it does not change the pack or live state." %
                     (len(dataset.hosts), dataset.pack_id, route_source))
        else:
            basis = "Model-based estimate over the six-host scripted topology. This what-if does not change live state and is not a guarantee."
        return {
            "from_host": source,
            "before": {"candidates": before_candidates, "targets": _rank(before)},
            "after": {"candidates": after_candidates, "targets": _rank(after)},
            "contain_hosts": contain,
            "removed_probability_share": round(removed, 6),
            "live_forecast": copy.deepcopy(current),
            "basis": basis,
        }

    def model_card(self):
        evaluation = self.shipped_evaluation()
        dataset = self.dataset_context
        if dataset is not None and dataset.pack_id != "demo-6":
            limitations = list(dataset.evaluation.get("limitations", []))
            limitations.append("Results depend on this pack's stated ground-truth provenance; derived routes are estimates.")
            return {"data_source": dataset.manifest["source"]["name"], "training_sequences": len(dataset.training_routes),
                    "network_hosts": len(dataset.hosts), "held_out_forecasts": evaluation["node_model"]["forecasts"],
                    "precision_at_1_standard_error": evaluation["node_model"]["precision_at_1_std_error"],
                    "limitations": limitations[:20]}
        return {"data_source": "graph_replay scripted generator", "training_sequences": 300,
                "network_hosts": len(self.graph.topology.host_ids()), "held_out_forecasts": evaluation["node_model"]["forecasts"],
                "precision_at_1_standard_error": evaluation["node_model"]["precision_at_1_std_error"],
                "limitations": ["Scripted paths and six demo hosts do not represent real attackers.",
                                "Precision@3 is trivial here: every held-out step has at most three candidates.",
                                "The offline CICIDS2017 report is a separate lab result, not live detector performance."]}

    def shipped_evaluation(self):
        dataset = self.dataset_context
        if dataset is not None and isinstance(dataset.evaluation, dict) and "node_model" in dataset.evaluation:
            return dataset.evaluation
        return json.loads(self.evaluation_path.read_text(encoding="utf-8"))

    def model_overview(self):
        evaluation = self.shipped_evaluation()
        dataset = self.dataset_context
        detection = json.loads(self.detection_path.read_text(encoding="utf-8")) if self.detection_path.is_file() and (dataset is None or dataset.detector_mode == "nids-live") else None
        return {"evaluation": evaluation, "model_card": self.model_card(), "technique_source": getattr(self.engine.layer, "default_source", "lookup") if self.engine else "lookup",
                "detection_report": detection, "live_metrics": self.ctx.world.metrics()}

    def run_evaluation(self, seed, test_fraction, grid):
        key = json.dumps({"seed": seed, "test_fraction": test_fraction, "grid": grid}, sort_keys=True, separators=(",", ":"))
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return copy.deepcopy(dict(self._cache[key], cached=True))
            dataset = self.dataset_context
            training = ([{"profile": route.get("profile", "unknown"), "path": route["path"]} for route in dataset.training_routes]
                        if dataset is not None else json.loads(self.training_path.read_text(encoding="utf-8"))["sequences"])
            topology = self.graph.topology
            candidates = lambda here, path: topology.candidates(here, exclude=path)
            started = time.monotonic()
            _model, result = evaluate(training, candidates, topology.edge_probability, seed=seed,
                                      test_fraction=test_fraction, grid=grid)
            runtime_ms = int((time.monotonic() - started) * 1000)
            if runtime_ms > 5000:
                raise TimeoutError("Evaluation exceeded the 5 second safety limit.")
            record = {"experiment_id": "EXP-%06d" % (len(self._experiments) + 1), "created_at": _utc_now(),
                      "parameters": {"seed": seed, "test_fraction": test_fraction, "alpha_grid": grid},
                      "result": result, "runtime_ms": runtime_ms, "cached": False}
            self._experiments.append(record)
            self._experiments = self._experiments[-MAX_EXPERIMENTS:]
            self._cache[key] = record
            while len(self._cache) > MAX_EXPERIMENTS:
                self._cache.popitem(last=False)
            self._save_experiments()
            return copy.deepcopy(record)

    def list_experiments(self):
        return copy.deepcopy(list(reversed(self._experiments)))

    def _load_experiments(self):
        target = self.data_dir / "experiments.json"
        try:
            self._experiments = json.loads(target.read_text(encoding="utf-8"))[-MAX_EXPERIMENTS:]
            for item in self._experiments:
                parameters = item["parameters"]
                key = json.dumps({"seed": parameters["seed"], "test_fraction": parameters["test_fraction"],
                                  "grid": parameters["alpha_grid"]}, sort_keys=True, separators=(",", ":"))
                self._cache[key] = item
        except (OSError, ValueError, KeyError, TypeError):
            self._experiments = []

    def _save_experiments(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        target = self.data_dir / "experiments.json"
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(self._experiments, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, target)


def _num(value):
    return "n/a" if value is None else ("%g" % value)


def register(ctx):
    ctx.flask_app.extensions["precog_lab"] = PrecogLab(ctx)

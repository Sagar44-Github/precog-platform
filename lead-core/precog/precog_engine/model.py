"""Precog's smoothed host-transition model with an optional route-stage/zone backoff.

The exact component is a first-order Markov model over host IDs. When a pack
ships host-zone metadata, a second component pools target counts for the same
route stage and target zone. A validation-selected mixture provides reusable
evidence when large workspaces have sparse per-host counts. Both components
use the same feasible candidate set and alpha smoothing; neither uses held-out
outcomes or scripted scenario results.
"""
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path

DEFAULT_ALPHA = 0.1
ALPHA_GRID = (0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0)
CONTEXT_WEIGHT_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
SOURCE_ZONE_WEIGHT_GRID = (0.0, 0.5, 1.0)
MAX_ROUTE_STAGE = 2


def route_stage_bucket(stage):
    """Pool late route hops; sparse route packs cannot support one model row per hop."""
    if isinstance(stage, bool) or not isinstance(stage, int) or stage < 0:
        return None
    return min(stage, MAX_ROUTE_STAGE)


def split_sequences(sequences, seed=0, test_fraction=0.2):
    """A repeatable split: (training, held-out test). The same seed always gives the same split."""
    order = list(range(len(sequences)))
    random.Random(seed).shuffle(order)
    cut = int(round(len(sequences) * (1 - test_fraction)))
    return [sequences[i] for i in order[:cut]], [sequences[i] for i in order[cut:]]


def count_moves(sequences):
    counts = defaultdict(lambda: defaultdict(int))
    for sequence in sequences:
        path = sequence["path"] if isinstance(sequence, dict) else sequence
        for here, nxt in zip(path, path[1:]):
            counts[here][nxt] += 1
    return {a: dict(row) for a, row in counts.items()}


class NodeModel:
    def __init__(self, counts, alpha=DEFAULT_ALPHA, meta=None):
        if alpha < 0:
            raise ValueError("alpha cannot be negative")
        self.counts, self.alpha, self.meta = counts, float(alpha), dict(meta or {})
        context = self.meta.get("prediction_context")
        context = context if isinstance(context, dict) else {}
        self.stage_zone_counts = context.get("stage_zone_counts", {})
        self.stage_source_zone_counts = context.get("stage_source_zone_counts", {})
        self.host_zones = context.get("host_zones", {})
        weight = context.get("context_weight", 1.0)
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 <= weight <= 1:
            raise ValueError("prediction context weight must be between 0 and 1")
        self.context_weight = float(weight)
        source_weight = context.get("source_zone_weight", 0.5)
        if isinstance(source_weight, bool) or not isinstance(source_weight, (int, float)) or not 0 <= source_weight <= 1:
            raise ValueError("source-zone context weight must be between 0 and 1")
        self.source_zone_weight = float(source_weight)

    @classmethod
    def train(cls, sequences, alpha=DEFAULT_ALPHA, meta=None, host_zones=None, context_weight=1.0,
              source_zone_weight=0.5):
        metadata = dict(meta or {})
        if host_zones:
            stage_zone_counts = defaultdict(lambda: defaultdict(int))
            stage_source_zone_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
            for sequence in sequences:
                path = sequence["path"] if isinstance(sequence, dict) else sequence
                for stage, (source, target) in enumerate(zip(path, path[1:])):
                    source_zone = host_zones.get(source)
                    zone = host_zones.get(target)
                    if zone:
                        stage_zone_counts[str(route_stage_bucket(stage))][zone] += 1
                    if source_zone and zone:
                        stage_source_zone_counts[str(route_stage_bucket(stage))][source_zone][zone] += 1
            metadata["prediction_context"] = {
                "kind": "route-stage-source-zone-v2",
                "context_weight": float(context_weight),
                "source_zone_weight": float(source_zone_weight),
                "stage_zone_counts": {stage: dict(counts) for stage, counts in stage_zone_counts.items()},
                "stage_source_zone_counts": {
                    stage: {source_zone: dict(counts) for source_zone, counts in sources.items()}
                    for stage, sources in stage_source_zone_counts.items()
                },
                "host_zones": dict(host_zones),
            }
        return cls(count_moves(sequences), alpha, metadata)

    def probability_components(self, from_host, candidates, stage=None):
        """Return exact-host and pooled stage/zone distributions for one candidate set."""
        if not candidates:
            return {"node": {}, "context": {}, "context_weight": self.context_weight}
        row = self.counts.get(from_host, {})
        denominator = sum(row.get(c, 0) for c in candidates) + self.alpha * len(candidates)
        exact = ({c: 1.0 / len(candidates) for c in candidates} if denominator == 0 else
                 {c: (row.get(c, 0) + self.alpha) / denominator for c in candidates})
        bucket = route_stage_bucket(stage)
        stage_counts = self.stage_zone_counts.get(str(bucket), {}) if bucket is not None else {}
        zone_sizes = defaultdict(int)
        for candidate in candidates:
            zone = self.host_zones.get(candidate)
            if not zone:
                return {"node": exact, "context": {}, "context_weight": 1.0,
                        "source_zone": {}, "stage_zone": {}, "source_zone_weight": self.source_zone_weight}
            zone_sizes[zone] += 1
        def normalize(zone_counts):
            denominator = sum(zone_counts.get(zone, 0) for zone in zone_sizes) + self.alpha * len(candidates)
            if not zone_counts or denominator <= 0 or not any(zone_counts.get(zone, 0) for zone in zone_sizes):
                return {}
            return {
                candidate: (zone_counts.get(self.host_zones[candidate], 0) + self.alpha * zone_sizes[self.host_zones[candidate]])
                           / denominator / zone_sizes[self.host_zones[candidate]]
                for candidate in candidates
            }

        stage_source_counts = self.stage_source_zone_counts.get(str(bucket), {}) if bucket is not None else {}
        source_zone = self.host_zones.get(from_host)
        source_distribution = normalize(stage_source_counts.get(source_zone, {})) if source_zone else {}
        stage_distribution = normalize(stage_counts)
        if source_distribution and stage_distribution:
            source_weight = self.source_zone_weight
            context = {candidate: source_weight * source_distribution[candidate] +
                       (1.0 - source_weight) * stage_distribution[candidate] for candidate in candidates}
        elif source_distribution:
            source_weight, context = 1.0, source_distribution
        elif stage_distribution:
            source_weight, context = 0.0, stage_distribution
        else:
            source_weight, context = self.source_zone_weight, {}
        return {"node": exact, "context": context, "context_weight": self.context_weight,
                "source_zone": source_distribution, "stage_zone": stage_distribution,
                "source_zone_weight": source_weight}

    def probabilities(self, from_host, candidates, stage=None):
        """Candidate probabilities summing to one; optional route-stage pooling backs off sparse host rows."""
        parts = self.probability_components(from_host, candidates, stage)
        if not parts["context"]:
            return parts["node"]
        weight = parts["context_weight"]
        return {candidate: weight * parts["node"][candidate] + (1.0 - weight) * parts["context"][candidate]
                for candidate in candidates}

    def top(self, from_host, candidates, k=3, stage=None):
        """The k likeliest hosts as [(host, probability)], best first (ties go to the host id so the result is repeatable)."""
        probabilities = self.probabilities(from_host, candidates, stage=stage)
        return sorted(probabilities.items(), key=lambda item: (-item[1], item[0]))[:k]

    def to_dict(self):
        return {"alpha": self.alpha, "counts": self.counts, "meta": self.meta}

    @classmethod
    def from_dict(cls, data):
        return cls(data["counts"], data["alpha"], data.get("meta"))

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_dict(), indent=1, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def file_sha256(path):
    # Training data is text, and Git may check it out with CRLF on Windows.
    # Hash a canonical LF representation so model metadata is portable across
    # operating systems and checkout settings.
    contents = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(contents).hexdigest()


def negative_log_likelihood(model, sequences, candidates_fn):
    """How surprised the model is by the moves in `sequences` (lower is better). candidates_fn(here, already_compromised) -> list."""
    total, moves = 0.0, 0
    for sequence in sequences:
        path = sequence["path"]
        for i in range(len(path) - 1):
            probabilities = model.probabilities(path[i], candidates_fn(path[i], path[: i + 1]))
            total += -math.log(max(probabilities.get(path[i + 1], 1e-12), 1e-12))
            moves += 1
    return total / moves if moves else float("inf")


def tune_alpha(train_sequences, candidates_fn, grid=ALPHA_GRID, seed=0):
    """Picks alpha from the grid by the surprise on a validation part of the TRAINING data (the test data is never used).
    Returns (best alpha, {alpha: surprise})."""
    fit, validation = split_sequences(train_sequences, seed=seed + 1, test_fraction=0.2)
    scores = {a: negative_log_likelihood(NodeModel.train(fit, a), validation, candidates_fn) for a in grid}
    return min(scores, key=lambda a: (scores[a], a)), scores

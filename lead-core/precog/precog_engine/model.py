"""The node-level Precog model: a smoothed first-order Markov model over hosts (TRD Section 9.2).

State: the host the attacker is on. Candidates: the hosts it could go to next. The probability of moving from i to j is

    P(j | i) = ( count(i -> j) + alpha ) / ( sum over candidates k of count(i -> k) + alpha * number_of_candidates )

alpha is a small smoothing number, so a move never seen in training still has a small chance. The top three
probabilities are the forecast. The counts come from the training sequences made by GRAPH's generator.
"""
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path

DEFAULT_ALPHA = 0.1
ALPHA_GRID = (0.01, 0.05, 0.1, 0.2, 0.5, 1.0)


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

    @classmethod
    def train(cls, sequences, alpha=DEFAULT_ALPHA, meta=None):
        return cls(count_moves(sequences), alpha, meta)

    def probabilities(self, from_host, candidates):
        """{candidate: probability}, summing to 1. With no data at all every candidate gets the same share."""
        if not candidates:
            return {}
        row = self.counts.get(from_host, {})
        denominator = sum(row.get(c, 0) for c in candidates) + self.alpha * len(candidates)
        if denominator == 0:
            return {c: 1.0 / len(candidates) for c in candidates}
        return {c: (row.get(c, 0) + self.alpha) / denominator for c in candidates}

    def top(self, from_host, candidates, k=3):
        """The k likeliest hosts as [(host, probability)], best first (ties go to the host id so the result is repeatable)."""
        probabilities = self.probabilities(from_host, candidates)
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
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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

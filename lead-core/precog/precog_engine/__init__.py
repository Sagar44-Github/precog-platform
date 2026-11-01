"""LEAD-CORE's Precog Engine package.

register(ctx) plugs the engine into the backend through the 'precog' hook, which GRAPH's replay calls:

    precog = ctx.hooks.get("precog")
    precog.reset()
    precog.on_compromise(host)
    precog.on_attempt(from_host, to_host, blocked)

Settings (environment variables): FORECAST_SOURCE = repo (default) or lookup, chooses which technique table is preferred.
Files it reads: data/node_model.json (the trained, evaluated model; trained on the training file when missing),
data/technique_markov.json and data/technique_lookup.json.
"""
import logging
import os
from pathlib import Path

from .engine import PrecogEngine
from .metrics import session_metrics, zero_metrics
from .model import NodeModel
from .technique_layer import TechniqueLayer

log = logging.getLogger("precog.engine")

PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR / "data"
MODEL_FILE = DATA_DIR / "node_model.json"
TRAINING_FILE = Path("graph") / "graph_replay" / "training" / "sequences.json"

__all__ = ["register", "PrecogEngine", "NodeModel", "TechniqueLayer", "session_metrics", "zero_metrics", "MODEL_FILE"]


def _load_model(repo_root):
    if MODEL_FILE.is_file():
        model = NodeModel.load(MODEL_FILE)
        log.info("Precog model loaded (alpha %s)", model.alpha)
        return model
    training = Path(repo_root) / TRAINING_FILE
    if training.is_file():
        import json

        model = NodeModel.train(json.loads(training.read_text(encoding="utf-8"))["sequences"], meta={"trained_at_start_up": True})
        log.warning("No saved model: trained from %s with the default alpha. Run lead-core/precog/tools/evaluate_precog.py to make the evaluated model.", training.name)
        return model
    log.warning("No Precog model and no training file: forecasts use the rule-based fallback ranking")
    return None


def register(ctx):
    prefer = os.environ.get("FORECAST_SOURCE", "repo").strip().lower()
    if prefer not in ("repo", "lookup"):
        raise ValueError("FORECAST_SOURCE must be 'repo' or 'lookup', not %r" % prefer)
    layer = TechniqueLayer.load(DATA_DIR / "technique_markov.json", DATA_DIR / "technique_lookup.json", prefer)
    engine = PrecogEngine(ctx.world, ctx.hooks, _load_model(ctx.config.repo_root), layer, contracts=ctx.contracts,
                          sessions_dir=ctx.config.repo_root / "lead-core" / "backend" / "data" / "sessions")
    ctx.hooks.register("precog", engine)
    log.info("Precog ready: %s", engine.describe())

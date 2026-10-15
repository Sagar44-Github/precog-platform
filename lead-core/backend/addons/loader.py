"""Joins everything to the NIDS Flask app. Called once at start-up from run_app.py."""
import importlib
import logging

import sys
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .contracts import Contracts

from .hooks import Hooks
from .routes import bp

from .sample_loader import load_samples
from .webapp import register_webapp

from .world_state import WorldState

log = logging.getLogger("precog.addons")

# Folders that hold each role's Python packages (added to Python's search path).
ROLE_FOLDERS = ("detect", "graph", "viz", "lead-core/precog")
# Each package may define register(ctx). Missing packages are skipped, never fatal.
ROLE_PACKAGES = ("detect_events", "graph_replay", "graph_net", "viz_containment")


@dataclass
class AddonContext:
    """What every role module receives in its register(ctx) function."""
    world: WorldState
    hooks: Hooks
    config: Config
    contracts: object
    nids: object
    flask_app: object



def _load_role_packages(ctx, packages):
    report = {}
    for name in packages:

        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError as exc:

            # Only "this package is missing" is fine. A missing library inside it is a real error.
            if exc.name == name:
                report[name] = "missing"
                continue

            log.exception("Module %s could not be imported", name)
            report[name] = "error: %s" % exc
            continue

        except Exception as exc:  # a bug in a role's code must not stop the whole server
            log.exception("Module %s could not be imported", name)
            report[name] = "error: %s" % exc

            continue

        register = getattr(module, "register", None)

        if register is None:
            report[name] = "loaded (no register function yet)"
            continue

        try:
            register(ctx)
            report[name] = "registered"

        except Exception as exc:
            log.exception("Module %s failed in register()", name)
            report[name] = "error: %s" % exc

    return report


def register_addons(flask_app, repo_root, nids, packages=ROLE_PACKAGES):
    config = Config.from_env(repo_root)
    contracts = Contracts(config.contracts_dir) if config.validate_contracts else None
    world = WorldState(contracts)
    hooks = Hooks()

    for folder in ROLE_FOLDERS:
        path = str(config.repo_root / folder)
        if path not in sys.path:
            sys.path.append(path)

    ctx = AddonContext(world=world, hooks=hooks, config=config, contracts=contracts, nids=nids, flask_app=flask_app)
    load_report = _load_role_packages(ctx, packages)

    flask_app.extensions["precog"] = {
        "world": world, "hooks": hooks, "config": config, "contracts": contracts,
        "nids": nids, "load_report": load_report,
    }
    flask_app.register_blueprint(bp)
    register_webapp(flask_app, config)

    if config.data_mode == "sample":
        load_samples(world, config.contracts_dir)
        log.info("Sample mode: the world state was filled from contracts/samples")
    return ctx

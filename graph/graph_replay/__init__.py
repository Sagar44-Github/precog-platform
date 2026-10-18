"""GRAPH's package: the replay controller and writer, scenario files and the training-sequence generator.

register(ctx) plugs the controller into the backend through the 'replay' hook:

    replay = ctx.hooks.get("replay")
    replay.list_scenarios()          -> [{"scenario_id", "description", "events", "has_decision_point"}]
    replay.status()                  -> replay_status dict
    replay.start(scenario_id, speed) -> replay_status dict   (needs the 'events' and 'graph' hooks)
    replay.pause() / replay.resume() / replay.restart()

The replay calls these hooks while it plays:
    events (DETECT)   process_packets(rows), process_technique(host, technique_id, note=..., compromise=...), reset()
    graph  (GRAPH)    add_connection, mark_compromised, attempt, reset
    precog (LEAD-CORE, optional)  reset(), on_compromise(host), on_attempt(from_host, to_host, blocked)
"""
import logging
import os
from pathlib import Path

from .controller import ReplayController
from .generator import generate_sequences
from .packet_store import MemoryPacketStore, NidsPacketStore, simple_detector
from .scenario import SCENARIOS_DIR, ScenarioError, ScenarioLibrary, check_scenario, load_scenario

log = logging.getLogger("precog.replay")

TRAINING_FILE = Path(__file__).resolve().parent / "training" / "sequences.json"

__all__ = ["register", "ReplayController", "ScenarioLibrary", "ScenarioError", "check_scenario", "load_scenario",
           "generate_sequences", "MemoryPacketStore", "NidsPacketStore", "simple_detector", "SCENARIOS_DIR", "TRAINING_FILE"]


def _nids_detector():
    from ml.anomaly_detector import run_detection  # NIDS's own function; the backend has NIDS on its search path

    return run_detection


def register(ctx):
    from graph_net.hosts_file import load_hosts  # GRAPH's other package

    hosts = load_hosts(ctx.config.contracts_dir / "data" / "hosts.json")
    library = ScenarioLibrary(SCENARIOS_DIR, known_hosts={h["host_id"] for h in hosts})
    if ctx.nids is None or not hasattr(ctx.nids, "SessionLocal"):
        raise RuntimeError("The replay needs NIDS's database (ctx.nids with SessionLocal and Packet)")
    timeout = float(os.environ.get("REPLAY_DECISION_TIMEOUT", "120"))  # seconds; 0 = wait for the analyst forever
    controller = ReplayController(ctx.world, ctx.hooks, NidsPacketStore(ctx.nids), _nids_detector(), library, hosts,
                                  decision_timeout=timeout)
    ctx.hooks.register("replay", controller)
    log.info("Replay ready: %d scenarios, decision wait %s s", len(library.ids()), timeout)

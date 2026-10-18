"""Shared helpers for GRAPH's tests: path set-up and the Rig that wires a replay together. (A unique module name, so it never clashes with another role's conftest.)"""
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("DATABASE_URL", "sqlite:///" + (Path(tempfile.mkdtemp(prefix="graph-tests-")) / "test.db").as_posix())
for folder in ("lead-core/backend", "graph", "detect", "lead-core/backend/nids"):
    path = str(REPO_ROOT / folder)
    if path not in sys.path:
        sys.path.insert(0, path)

from addons.contracts import Contracts  # noqa: E402
from addons.hooks import Hooks  # noqa: E402
from addons.world_state import WorldState  # noqa: E402
from graph_net import TOPOLOGY_FILE, LiveGraph, Topology, load_hosts  # noqa: E402
from graph_replay import MemoryPacketStore, ReplayController, ScenarioLibrary, simple_detector  # noqa: E402
from graph_replay.standins import StandInEvents, StandInPrecog  # noqa: E402


class Rig:
    """Everything a replay test needs, wired together with stand-ins for DETECT's events and Precog."""

    def __init__(self, world, graph, library, hosts, decision_timeout=5, settle=0):
        self.world, self.graph = world, graph
        self.hooks = Hooks()
        self.events = StandInEvents(world)
        self.precog = StandInPrecog()
        self.hooks.register("events", self.events)
        self.hooks.register("graph", graph)
        self.hooks.register("precog", self.precog)
        self.store = MemoryPacketStore()
        self.detector_calls = 0
        base = simple_detector(self.store)

        def counting_detector():
            self.detector_calls += 1
            base()

        self.controller = ReplayController(world, self.hooks, self.store, counting_detector, library, hosts,
                                           decision_timeout=decision_timeout, settle_seconds=settle)

    def wait_for(self, state, timeout=10):
        import time

        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.controller.status()["state"] == state:
                return True
            time.sleep(0.005)
        return False

    def contain(self, host_id, status="executed"):
        """What VIZ's containment will do: change the host's state and record the decision."""
        if status == "executed":
            self.graph.set_host_state(host_id, "contained")
        self.world.upsert_action({"action_id": "act-%06d" % (len(self.world.actions()) + 1), "target_host": host_id, "forecast_id": None,
                                  "requested_by": "console", "status": status, "proposed_at": "2026-10-03T10:00:05Z",
                                  "confirmed_at": "2026-10-03T10:00:06Z" if status == "executed" else None, "result": None})

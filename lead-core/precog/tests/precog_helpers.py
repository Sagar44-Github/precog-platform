"""Shared helpers for the Precog tests: path set-up, stand-ins for GRAPH's graph and DETECT's events, and the Rig.
(A unique module name, so it never clashes with another role's conftest.)"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
for folder in ("lead-core/backend", "lead-core/precog", "graph", "detect"):
    path = str(REPO_ROOT / folder)
    if path not in sys.path:
        sys.path.insert(0, path)

from addons.contracts import Contracts  # noqa: E402
from addons.hooks import Hooks  # noqa: E402
from addons.world_state import WorldState  # noqa: E402
from precog_engine import PrecogEngine, TechniqueLayer  # noqa: E402
from precog_engine.model import NodeModel  # noqa: E402

DATA = REPO_ROOT / "lead-core" / "precog" / "precog_engine" / "data"
NAMES = {"host-a": "Workstation A", "host-b": "Workstation B", "server-b": "Web Server B", "file-server": "File Server", "db-server": "Database Server"}
LINKS = {"host-a": ["host-b", "server-b", "file-server"], "host-b": ["host-a", "server-b", "file-server"], "server-b": ["file-server", "db-server"],
         "file-server": ["db-server"], "db-server": []}


class FakeTopology:
    def edge_probability(self, source, target):
        return {"server-b": 0.98, "file-server": 0.81, "host-b": 0.65, "db-server": 0.91}.get(target, 0.1)


class FakeGraph:
    """A stand-in for GRAPH's graph hook."""

    def __init__(self):
        self.states = {h: "normal" for h in NAMES}
        self.topology = FakeTopology()

    def feasible_targets(self, host):
        return [t for t in LINKS[host] if self.states[t] == "normal"]

    def snapshot(self):
        return {"hosts": [{"host_id": h, "name": n, "zone": "user", "state": self.states[h]} for h, n in NAMES.items()], "edges": [], "compromised_path": []}


class FakeEvents:
    def __init__(self):
        self.audit = []

    def audit_record(self, entry_type, ref_id, summary):
        self.audit.append((entry_type, ref_id, summary))


GOOD_MODEL = {"host-a": {"server-b": 6, "file-server": 3, "host-b": 1}, "server-b": {"db-server": 3, "file-server": 1}}


class Rig:
    def __init__(self, contracts, model="default", sessions_dir=None, prefer="repo"):
        self.world = WorldState(contracts)
        self.graph, self.events = FakeGraph(), FakeEvents()
        self.hooks = Hooks()
        self.hooks.register("graph", self.graph)
        self.hooks.register("events", self.events)
        node_model = NodeModel(GOOD_MODEL, alpha=0.1) if model == "default" else model
        layer = TechniqueLayer.load(DATA / "technique_markov.json", DATA / "technique_lookup.json", prefer)
        self.engine = PrecogEngine(self.world, self.hooks, node_model, layer, contracts=contracts, sessions_dir=sessions_dir, clock=lambda: "2026-10-03T10:00:03Z")

    def execute_containment(self, host, forecast_id=None):
        self.graph.states[host] = "contained"
        self.world.upsert_action({"action_id": "act-%06d" % (len(self.world.actions()) + 1), "target_host": host, "forecast_id": forecast_id, "requested_by": "console",
                                  "status": "executed", "proposed_at": "2026-10-03T10:00:04Z", "confirmed_at": "2026-10-03T10:00:05Z", "result": None})

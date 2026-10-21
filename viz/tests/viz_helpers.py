"""Shared helpers for VIZ's tests: path set-up, stand-ins for GRAPH's graph and DETECT's events, and the Rig. (A unique module name, so it never clashes with another role's conftest.)"""
import os
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("DATABASE_URL", "sqlite:///" + (Path(tempfile.mkdtemp(prefix="viz-tests-")) / "test.db").as_posix())
for folder in ("lead-core/backend", "viz", "graph", "detect", "lead-core/backend/nids"):
    path = str(REPO_ROOT / folder)
    if path not in sys.path:
        sys.path.insert(0, path)

from addons.contracts import Contracts  # noqa: E402
from addons.hooks import Hooks  # noqa: E402
from addons.world_state import WorldState  # noqa: E402
from viz_containment import ContainmentService  # noqa: E402

HOSTS = [("host-a", "Workstation A", "user"), ("host-b", "Workstation B", "user"), ("server-b", "Web Server B", "dmz")]


class FakeGraph:
    """A tiny stand-in for GRAPH's 'graph' hook, so VIZ's tests do not need GRAPH's code."""

    def __init__(self):
        self.states = {h: "normal" for h, _, _ in HOSTS}

    def host_state(self, host_id):
        if host_id not in self.states:
            raise ValueError("Unknown host '%s'. Known hosts: %s" % (host_id, ", ".join(self.states)))
        return self.states[host_id]

    def set_host_state(self, host_id, state):
        self.host_state(host_id)
        self.states[host_id] = state

    def snapshot(self):
        return {"hosts": [{"host_id": h, "name": n, "zone": z, "state": self.states[h]} for h, n, z in HOSTS], "edges": [], "compromised_path": []}


class FakeEvents:
    def __init__(self):
        self.audit = []

    def audit_record(self, entry_type, ref_id, summary):
        self.audit.append((entry_type, ref_id, summary))


class Rig:
    def __init__(self, world, contracts, confirm_seconds=5.0):
        self.world, self.graph, self.events = world, FakeGraph(), FakeEvents()
        self.hooks = Hooks()
        self.hooks.register("graph", self.graph)
        self.hooks.register("events", self.events)
        self.service = ContainmentService(world, self.hooks, confirm_seconds=confirm_seconds, contracts=contracts, poll=0.01, reeval_wait=3.0)

    def wait(self, check, timeout=5.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if check():
                return True
            time.sleep(0.01)
        return False

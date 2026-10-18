"""Watch a replay happen, with no server and no database.

Run from the repo root (backend environment on):   python graph/tools/demo_replay.py
Options:  --scenario golden-path   --no-contain  (let the attacker succeed instead of containing the host)
It uses stand-ins for DETECT's events and NIDS's detector, but the REAL live graph, scenario files and replay controller.
"""
import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for folder in ("graph", "lead-core/backend"):
    sys.path.insert(0, str(REPO_ROOT / folder))

from addons.contracts import Contracts  # noqa: E402
from addons.hooks import Hooks  # noqa: E402
from addons.world_state import WorldState  # noqa: E402
from graph_net import TOPOLOGY_FILE, LiveGraph, Topology, load_hosts  # noqa: E402
from graph_replay import MemoryPacketStore, ReplayController, ScenarioLibrary, simple_detector  # noqa: E402
from graph_replay.standins import StandInEvents, StandInPrecog  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="golden-path")
    parser.add_argument("--no-contain", action="store_true")
    args = parser.parse_args(argv)

    world = WorldState(Contracts(REPO_ROOT / "contracts"))
    hosts = load_hosts(REPO_ROOT / "contracts" / "data" / "hosts.json")
    graph = LiveGraph(Topology.from_files(hosts, TOPOLOGY_FILE), world=world)
    precog = StandInPrecog()
    hooks = Hooks()
    hooks.register("events", StandInEvents(world))
    hooks.register("graph", graph)
    hooks.register("precog", precog)
    store = MemoryPacketStore()
    controller = ReplayController(world, hooks, store, simple_detector(store), ScenarioLibrary(known_hosts={h["host_id"] for h in hosts}),
                                  hosts, decision_timeout=20, settle_seconds=0.2)

    print("Starting '%s' at 20x speed ..." % args.scenario)
    controller.start(args.scenario, 20.0)
    last = None
    while controller.status()["state"] not in ("finished", "idle"):
        status = controller.status()
        if status["state"] == "waiting_for_decision":
            if last != "waiting":
                print("  -> the replay is waiting for the analyst's decision")
                last = "waiting"
            time.sleep(0.5)  # the "analyst" thinks for a moment
            if args.no_contain:
                controller.resume()
            else:
                graph.set_host_state("server-b" if args.scenario == "golden-path" else "file-server", "contained")
                world.upsert_action({"action_id": "act-demo", "target_host": "server-b", "forecast_id": None, "requested_by": "console",
                                     "status": "executed", "proposed_at": status and datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                     "confirmed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "result": "Contained (demo)"})
                print("  -> the analyst contained the predicted host")
        time.sleep(0.05)
    controller.wait_until_done(5)
    print("\nAlerts the analyst would see (oldest first):")
    for alert in reversed(world.alerts(50)):
        print("  %s  %-6s %-10s %s" % (alert["event_id"], alert["severity"], alert["host"], alert["explanation"]))
    print("\nHost states at the end:")
    for host_id, state in graph.states().items():
        print("  %-18s %s" % (host_id, state))
    print("Compromised path:", " -> ".join(world.graph()["compromised_path"]) or "(none)")
    print("Precog was told:", precog.calls or "(nothing)")
    print("Replay finished:", controller.status()["state"], "| sessions in history:", len(world.sessions()))
    return 0 if controller.last_error is None else 1


if __name__ == "__main__":
    sys.exit(main())

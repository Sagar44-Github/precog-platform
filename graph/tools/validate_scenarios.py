"""Checks every scenario file: format, host names, order. If DETECT's technique table is present it also checks technique ids.

Run from the repo root (backend environment on):   python graph/tools/validate_scenarios.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "graph"))
sys.path.insert(0, str(REPO_ROOT / "detect"))
sys.path.insert(0, str(REPO_ROOT / "lead-core" / "backend"))

from graph_net import load_hosts  # noqa: E402
from graph_replay import SCENARIOS_DIR, ScenarioError, load_scenario  # noqa: E402


def technique_ids():
    """The ids DETECT knows, or None if DETECT's real package is not merged yet."""
    try:
        from detect_events import TECHNIQUES_FILE, TechniqueTable

        return set(TechniqueTable.from_file(TECHNIQUES_FILE).ids())
    except ImportError:
        return None


def main():
    hosts = {h["host_id"] for h in load_hosts(REPO_ROOT / "contracts" / "data" / "hosts.json")}
    known = technique_ids()
    problems = 0
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        try:
            scenario = load_scenario(path, hosts)
            if known is not None:
                for event in scenario["events"]:
                    if event["kind"] in ("technique", "attempt") and event["technique_id"] not in known:
                        raise ScenarioError("%s: event %s uses the technique %s, which DETECT's table does not contain" % (path.name, event["seq"], event["technique_id"]))
            print("ok    %-18s %d events" % (path.name, len(scenario["events"])))
        except ScenarioError as exc:
            print("BAD  ", exc)
            problems += 1
    print(("%d problem(s)" % problems) if problems else "all scenarios OK" + ("" if known is not None else " (technique ids not checked: DETECT's package is not merged yet)"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

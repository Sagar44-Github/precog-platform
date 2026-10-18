"""Reading and checking scenario files (graph_replay/scenarios/*.json)."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_FILE = Path(__file__).resolve().parent / "schemas" / "scenario.schema.json"
SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


class ScenarioError(ValueError):
    """A scenario file is not valid. The message says which file and what is wrong."""


def _validator():
    return Draft202012Validator(json.loads(SCHEMA_FILE.read_text(encoding="utf-8")))


def _hosts_in(event):
    if event["kind"] == "technique":
        return [event["host"]]
    if event["kind"] == "attempt":
        return [event["from_host"], event["to_host"]]
    return [p[side] for p in event["packets"] for side in ("src_host", "dst_host")]


def check_scenario(data, known_hosts=None, name="scenario"):
    """Returns the scenario when it is valid, otherwise raises ScenarioError."""
    errors = sorted(_validator().iter_errors(data), key=lambda e: list(e.path))
    if errors:
        where = "/".join(str(p) for p in errors[0].path) or "(top level)"
        raise ScenarioError("%s: %s at %s" % (name, errors[0].message[:200], where))
    events = data["events"]
    previous_seq, previous_offset = 0, 0
    for event in events:
        if event["seq"] <= previous_seq:
            raise ScenarioError("%s: event numbers (seq) must go up one after another, but %s follows %s" % (name, event["seq"], previous_seq))
        if event["offset_ms"] < previous_offset:
            raise ScenarioError("%s: event %s happens before the one before it (offset_ms must not go down)" % (name, event["seq"]))
        previous_seq, previous_offset = event["seq"], event["offset_ms"]
        if event["kind"] == "attempt" and event["from_host"] == event["to_host"]:
            raise ScenarioError("%s: event %s moves from a host to itself" % (name, event["seq"]))
        if event["kind"] == "traffic":
            for packet in event["packets"]:
                if packet["src_host"] == packet["dst_host"]:
                    raise ScenarioError("%s: event %s sends a packet from a host to itself" % (name, event["seq"]))
        if known_hosts is not None:
            for host in _hosts_in(event):
                if host not in known_hosts:
                    raise ScenarioError("%s: event %s uses the unknown host '%s'. Known hosts: %s" % (name, event["seq"], host, ", ".join(sorted(known_hosts))))
    return data


def load_scenario(path, known_hosts=None):
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScenarioError("%s is not valid JSON: %s" % (path.name, exc))
    return check_scenario(data, known_hosts, path.name)


class ScenarioLibrary:
    """All the scenario files in one folder."""

    def __init__(self, folder=SCENARIOS_DIR, known_hosts=None):
        self.folder = Path(folder)
        self._scenarios = {}
        for path in sorted(self.folder.glob("*.json")):
            scenario = load_scenario(path, known_hosts)
            if scenario["scenario_id"] in self._scenarios:
                raise ScenarioError("Two files use the scenario_id '%s'" % scenario["scenario_id"])
            if path.stem != scenario["scenario_id"]:
                raise ScenarioError("%s: the file name must match its scenario_id ('%s')" % (path.name, scenario["scenario_id"]))
            self._scenarios[scenario["scenario_id"]] = scenario

    def ids(self):
        return list(self._scenarios)

    def get(self, scenario_id):
        return self._scenarios.get(scenario_id)

    def summaries(self):
        return [{"scenario_id": s["scenario_id"], "description": s["description"], "events": len(s["events"]),
                 "has_decision_point": any(e.get("pause_for_decision") for e in s["events"])} for s in self._scenarios.values()]

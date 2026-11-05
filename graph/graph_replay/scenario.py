"""Reading and checking scenario files (graph_replay/scenarios/*.json)."""
import json
import uuid
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
    """Shipped scenarios plus validated, locally saved demo scenarios."""

    def __init__(self, folder=SCENARIOS_DIR, known_hosts=None, custom_folder=None):
        self.folder = Path(folder)
        self.custom_folder = Path(custom_folder) if custom_folder is not None else None
        self.known_hosts = set(known_hosts) if known_hosts is not None else None
        self._scenarios = {}
        self._custom_ids = set()
        folders = [(self.folder, False)]
        if self.custom_folder is not None:
            folders.append((self.custom_folder, True))
        for source_folder, is_custom in folders:
            for path in sorted(source_folder.glob("*.json")):
                scenario = load_scenario(path, self.known_hosts)
                if scenario["scenario_id"] in self._scenarios:
                    raise ScenarioError("Two files use the scenario_id '%s'" % scenario["scenario_id"])
                if path.stem != scenario["scenario_id"]:
                    raise ScenarioError("%s: the file name must match its scenario_id ('%s')" % (path.name, scenario["scenario_id"]))
                self._scenarios[scenario["scenario_id"]] = scenario
                if is_custom:
                    self._custom_ids.add(scenario["scenario_id"])

    def ids(self):
        return list(self._scenarios)

    def add(self, scenario):
        """Register a validated user scenario in the in-memory replay library."""
        self._scenarios[scenario["scenario_id"]] = scenario

    def remove(self, scenario_id):
        """Remove only an explicitly named scenario; callers enforce ownership."""
        return self._scenarios.pop(scenario_id, None)

    def get(self, scenario_id):
        return self._scenarios.get(scenario_id)

    def summaries(self):
        return [{"scenario_id": s["scenario_id"], "description": s["description"], "events": len(s["events"]),
                 "has_decision_point": any(e.get("pause_for_decision") for e in s["events"]),
                 "custom": s["scenario_id"] in self._custom_ids} for s in self._scenarios.values()]

    def save_custom(self, data):
        """Validate and atomically save a new scenario in the runtime-only custom folder."""
        if self.custom_folder is None:
            raise ScenarioError("Custom scenario saving is not configured")
        scenario = check_scenario(data, self.known_hosts, "submitted scenario")
        scenario_id = scenario["scenario_id"]
        if scenario_id in self._scenarios:
            raise ScenarioError("A scenario called '%s' already exists" % scenario_id)
        self.custom_folder.mkdir(parents=True, exist_ok=True)
        destination = self.custom_folder / (scenario_id + ".json")
        temporary = self.custom_folder / (".%s.%s.tmp" % (scenario_id, uuid.uuid4().hex))
        try:
            temporary.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
            temporary.replace(destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        self._scenarios[scenario_id] = scenario
        self._custom_ids.add(scenario_id)
        return scenario

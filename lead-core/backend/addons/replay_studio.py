"""Scenario authoring, deterministic dry runs, and bounded replay history."""
from collections import deque
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import threading

from jsonschema import Draft202012Validator

from .contracts import ContractError

log = logging.getLogger("precog.replay_studio")

MAX_EVENTS = 200
MAX_DURATION_MS = 7_200_000
MAX_USER_SCENARIOS = 50
MAX_FINISHED_RUNS = 50
MAX_SNAPSHOTS = 2000
SCENARIO_ID = re.compile(r"^user-[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])?$")
RUN_ID = re.compile(r"^RUN-[0-9]{6}$")


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path_text(path):
    text = "$"
    for part in path:
        text += "[%d]" % part if isinstance(part, int) else ".%s" % part
    return text


def _stable(value):
    """Drop wall-clock fields while preserving identifiers and measured values."""
    time_fields = {"ts", "timestamp", "first_seen", "first_alert_at", "last_alert_at", "started_at", "ended_at", "created_at", "updated_at",
                   "proposed_at", "confirmed_at", "expires_at", "captured_at", "session_id", "duration_seconds"}
    if isinstance(value, dict):
        return {key: _stable(item) for key, item in sorted(value.items()) if key not in time_fields}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


def _canonical(value):
    return json.dumps(_stable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class ReplayStudio:
    """C2 service, attached to GRAPH's existing ReplayController as an observer."""

    def __init__(self, ctx, replay):
        self.ctx, self.replay = ctx, replay
        self.world = ctx.world
        self.hooks = ctx.hooks
        self.contracts = ctx.contracts
        self.topology = getattr(self.hooks.get("graph"), "topology", None)
        self.known_hosts = set(self.topology.host_ids()) if self.topology is not None else set()
        self.technique_ids = self._technique_ids()
        self.schema_path = ctx.config.repo_root / "graph" / "graph_replay" / "schemas" / "scenario.schema.json"
        self.schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(self.schema)
        self.data_dir = Path(ctx.config.data_dir)
        self.scenarios_dir = self.data_dir / "scenarios"
        self.runs_dir = self.data_dir / "runs"
        self._lock = threading.RLock()
        self._active = None
        self._runs = {}
        self._revision = 0
        self._snapshots = deque(maxlen=MAX_SNAPSHOTS)
        self._load_user_scenarios()
        self._load_runs()
        replay.attach_studio(self)

    def _technique_ids(self):
        events = self.hooks.get("events")
        table = getattr(events, "techniques", None)
        if table is None:
            delegate = getattr(events, "_delegate", None)
            table = getattr(delegate, "techniques", None)
        return set(table.ids()) if table is not None else set()

    def _validate(self, scenario):
        errors = []
        if not isinstance(scenario, dict):
            return [{"path": "$", "code": "type", "message": "Scenario must be a JSON object."}]
        schema_errors = sorted(self.validator.iter_errors(scenario), key=lambda item: (list(item.path), item.message))
        for error in schema_errors[:50]:
            if error.validator == "oneOf" and error.absolute_path and error.absolute_path[0] == "events":
                continue  # the event kind is known below, so report its precise field error instead
            errors.append({"path": _path_text(error.absolute_path), "code": "schema", "message": error.message[:240]})
        events = scenario.get("events")
        if not isinstance(events, list):
            return errors
        if len(events) > MAX_EVENTS:
            errors.append({"path": "$.events", "code": "event_limit", "message": "A scenario may contain at most 200 events."})
        previous_offset = -1
        previous_seq = 0
        for index, event in enumerate(events[:MAX_EVENTS]):
            if not isinstance(event, dict):
                continue
            event_path = "$.events[%d]" % index
            kind_schema = self.schema.get("$defs", {}).get(event.get("kind"))
            if kind_schema is not None:
                for error in sorted(Draft202012Validator(kind_schema).iter_errors(event), key=lambda item: (list(item.path), item.message))[:20]:
                    path = _path_text(("events", index) + tuple(error.absolute_path))
                    errors.append({"path": path, "code": "schema", "message": error.message[:240]})
            sequence = event.get("seq")
            if isinstance(sequence, int) and not isinstance(sequence, bool):
                if sequence <= previous_seq:
                    errors.append({"path": event_path + ".seq", "code": "sequence_order", "message": "Event sequence numbers must increase in timeline order."})
                previous_seq = sequence
            offset = event.get("offset_ms")
            if isinstance(offset, int) and not isinstance(offset, bool):
                if offset < previous_offset:
                    errors.append({"path": event_path + ".offset_ms", "code": "offset_order", "message": "Event offsets must be non-decreasing."})
                previous_offset = offset
                if offset > MAX_DURATION_MS:
                    errors.append({"path": event_path + ".offset_ms", "code": "duration_limit", "message": "A scenario may last at most two hours."})
            kind = event.get("kind")
            host_fields = []
            if kind == "technique":
                host_fields = ["host"]
                if event.get("compromise") is not None and not isinstance(event.get("compromise"), bool):
                    errors.append({"path": event_path + ".compromise", "code": "type", "message": "Compromise must be true or false."})
            elif kind == "attempt":
                host_fields = ["from_host", "to_host"]
            elif kind == "traffic":
                for packet_index, packet in enumerate(event.get("packets", [])):
                    if isinstance(packet, dict):
                        for field in ("src_host", "dst_host"):
                            host_fields.append((field, packet_index))
            for field in host_fields:
                if isinstance(field, tuple):
                    name, packet_index = field
                    host = event.get("packets", [])[packet_index].get(name)
                    path = "%s.packets[%d].%s" % (event_path, packet_index, name)
                else:
                    host = event.get(field)
                    path = event_path + "." + field
                if isinstance(host, str) and host not in self.known_hosts:
                    errors.append({"path": path, "code": "unknown_host", "message": "Host '%s' is not in the demo topology." % host[:100]})
            if kind == "attempt" and event.get("from_host") == event.get("to_host"):
                errors.append({"path": event_path + ".to_host", "code": "same_host", "message": "An attempt must move between different hosts."})
            if kind == "traffic":
                for packet_index, packet in enumerate(event.get("packets", [])):
                    if isinstance(packet, dict) and packet.get("src_host") == packet.get("dst_host"):
                        errors.append({"path": "%s.packets[%d].dst_host" % (event_path, packet_index), "code": "same_host", "message": "Traffic must move between different hosts."})
            if kind in ("technique", "attempt"):
                technique_id = event.get("technique_id")
                if isinstance(technique_id, str) and self.technique_ids and technique_id not in self.technique_ids:
                    errors.append({"path": event_path + ".technique_id", "code": "unknown_technique", "message": "Technique '%s' is not in DETECT's technique table." % technique_id[:80]})
        return errors

    def validate(self, scenario):
        errors = self._validate(scenario)
        events = scenario.get("events", []) if isinstance(scenario, dict) else []
        duration = events[-1].get("offset_ms", 0) if events and isinstance(events[-1], dict) else 0
        result = {"valid": not errors, "errors": errors, "event_count": len(events), "duration_ms": duration}
        return self._out("scenario_validation", result)

    def _safe_user_id(self, scenario_id):
        return isinstance(scenario_id, str) and bool(SCENARIO_ID.fullmatch(scenario_id))

    def _atomic_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        os.replace(temp, path)

    def _load_user_scenarios(self):
        folder = self.scenarios_dir.resolve()
        if not folder.exists():
            return
        for path in folder.glob("user-*.json"):
            if path.parent.resolve() != folder or not self._safe_user_id(path.stem):
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if value.get("scenario_id") != path.stem or self._validate(value):
                    continue
                self.replay.library.add(value)
            except Exception as exc:
                log.warning("Ignoring invalid saved scenario %s: %s", path.name, exc)

    def scenarios(self):
        results = []
        for item in self.replay.list_scenarios():
            scenario_id = item["scenario_id"]
            item = dict(item)
            item["source"] = "user" if scenario_id.startswith("user-") else "shipped"
            item["editable"] = item["source"] == "user"
            results.append(item)
        return results

    def get_scenario(self, scenario_id):
        scenario = self.replay.library.get(scenario_id)
        if scenario is None:
            return None
        source = "user" if scenario_id.startswith("user-") else "shipped"
        result = {"scenario": deepcopy(scenario), "source": source, "editable": source == "user", "updated_at": None}
        if source == "user":
            try:
                result["updated_at"] = datetime.fromtimestamp((self.scenarios_dir / (scenario_id + ".json")).stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except OSError:
                pass
        return self._out("scenario_draft", result)

    def save_scenario(self, scenario):
        scenario_id = scenario.get("scenario_id") if isinstance(scenario, dict) else None
        if not self._safe_user_id(scenario_id):
            raise ValueError("Scenario id must start with user- and contain only lowercase letters, digits, and hyphens.")
        errors = self._validate(scenario)
        if errors:
            raise ValueError("%s %s" % (errors[0]["path"], errors[0]["message"]))
        current_user_scenarios = [item for item in self.replay.list_scenarios() if item["scenario_id"].startswith("user-")]
        target = self.scenarios_dir / (scenario_id + ".json")
        if not target.exists() and len(current_user_scenarios) >= MAX_USER_SCENARIOS:
            raise ValueError("The user scenario library has reached its 50-scenario limit.")
        value = deepcopy(scenario)
        self._atomic_json(target, value)
        self.replay.library.add(value)
        return self.get_scenario(scenario_id)

    def delete_scenario(self, scenario_id):
        if not self._safe_user_id(scenario_id):
            raise ValueError("Only scenarios with a user- id can be deleted.")
        target = self.scenarios_dir / (scenario_id + ".json")
        if not target.is_file():
            raise KeyError(scenario_id)
        target.unlink()
        self.replay.library.remove(scenario_id)
        return True

    def dry_run(self, scenario):
        errors = self._validate(scenario)
        if errors:
            raise ValueError("%s %s" % (errors[0]["path"], errors[0]["message"]))
        graph = self.hooks.get("graph")
        precog = self.hooks.get("precog")
        topology = getattr(graph, "topology", None)
        if topology is None:
            raise RuntimeError("The topology hook is not available for dry-run.")
        states = {host_id: "normal" for host_id in topology.host_ids()}
        forecasts = []
        pending = None
        model = getattr(precog, "model", None)
        for event in scenario["events"]:
            kind = event["kind"]
            if kind == "technique" and event.get("compromise"):
                host = event["host"]
                if states[host] == "normal":
                    states[host] = "compromised"
                    pending = self._dry_forecast(host, states, topology, model)
                    if pending:
                        forecasts.append(pending)
            elif kind == "attempt":
                source, target = event["from_host"], event["to_host"]
                blocked = states[source] == "contained" or states[target] == "contained"
                if pending is not None:
                    ids = [item["host_id"] for item in pending["targets"]]
                    pending["outcome"] = {"attempted_host": target, "rank_hit": ids.index(target) + 1 if target in ids else None, "blocked": blocked}
                    pending = None
                if not blocked and states[target] == "normal":
                    states[target] = "compromised"
                    pending = self._dry_forecast(target, states, topology, model)
                    if pending:
                        forecasts.append(pending)
        return self._out("scenario_dry_run", {
            "scenario_id": scenario["scenario_id"], "event_count": len(scenario["events"]),
            "duration_ms": scenario["events"][-1]["offset_ms"], "host_states": states,
            "forecasts": forecasts,
            "basis": "Model-based estimate over the scripted six-host demo topology; this dry-run does not change live state.",
        })

    @staticmethod
    def _dry_forecast(host, states, topology, model):
        excluded = [name for name, state in states.items() if state != "normal"]
        candidates = topology.candidates(host, exclude=excluded)
        if not candidates:
            return None
        if model is not None:
            ranked = model.top(host, candidates, min(3, len(candidates)))
        else:
            weights = {candidate: max(topology.edge_probability(host, candidate), 0.01) for candidate in candidates}
            total = sum(weights.values())
            ranked = sorted(((candidate, weight / total) for candidate, weight in weights.items()), key=lambda item: (-item[1], item[0]))[:3]
        return {"from_host": host, "targets": [{"rank": index + 1, "host_id": item[0], "confidence": round(float(item[1]), 4)} for index, item in enumerate(ranked)], "outcome": None}

    # ---------- persisted run history ----------
    def _load_runs(self):
        if not self.runs_dir.exists():
            return
        for path in self.runs_dir.glob("RUN-*.json"):
            if not RUN_ID.fullmatch(path.stem):
                continue
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
                summary = item.get("summary")
                if not isinstance(summary, dict) or summary.get("run_id") != path.stem:
                    continue
                self._out("run_summary", summary)
                self._runs[path.stem] = item
            except Exception as exc:
                log.warning("Ignoring invalid run file %s: %s", path.name, exc)
        self._revision = len(self._runs)

    def begin(self, scenario, speed):
        with self._lock:
            next_number = max((int(key[-6:]) for key in self._runs), default=0) + 1
            run_id = "RUN-%06d" % next_number
            started_at = utc_now()
            fingerprint = hashlib.sha256(_canonical(scenario).encode("utf-8")).hexdigest()
            self._active = {"summary": {
                "run_id": run_id, "scenario_id": scenario["scenario_id"], "description": scenario["description"],
                "speed": float(speed), "started_at": started_at, "ended_at": None, "status": "running",
                "outcome": "in_progress", "event_count": len(scenario["events"]), "alerts_count": 0,
                "incidents_count": 0, "forecasts_count": 0, "actions_count": 0,
                "metrics": self.world.metrics(), "scenario_fingerprint": fingerprint,
            }, "scenario": deepcopy(scenario), "snapshots": [], "final_state": None}
            self._snapshots.clear()
            self._out("run_summary", self._active["summary"])
            self._capture(0, None)
            return run_id

    def _state_for_history(self):
        current = self.world.snapshot()
        state = {
            "version": current.get("version", 0), "graph": current.get("graph", {}),
            "alerts": current.get("alerts", []), "forecasts": self.world.forecasts(),
            "actions": current.get("actions", []), "replay": current.get("replay", {}),
            "metrics": current.get("metrics", {}), "session": self.world.session(),
        }
        incidents = self.hooks.get("incidents")
        if incidents is not None:
            try:
                state["incidents"] = incidents.snapshot_records()
            except Exception:
                state["incidents"] = []
        else:
            state["incidents"] = []
        return state

    def _capture(self, position, event):
        with self._lock:
            if self._active is None:
                return
            state = self._state_for_history()
            item = {"run_id": self._active["summary"]["run_id"], "version": position,
                    "position": position, "event_seq": event.get("seq") if event else None,
                    "event_kind": event.get("kind") if event else ("start" if position == 0 else "end"),
                    "captured_at": utc_now(), "state": state}
            self._out("run_snapshot", item)
            self._snapshots = deque((previous for previous in self._snapshots if previous["position"] != position), maxlen=MAX_SNAPSHOTS)
            self._snapshots.append(item)
            # A seek branches the timeline. Keep one snapshot per position and drop the old future.
            snapshots = self._active["snapshots"]
            snapshots[:] = [previous for previous in snapshots if previous["position"] < position]
            snapshots.append(deepcopy(item))
            self._active["final_state"] = state

    def capture(self, position, event):
        self._capture(position, event)

    def rewind(self, position):
        with self._lock:
            self._snapshots = deque((item for item in self._snapshots if item["position"] <= position), maxlen=MAX_SNAPSHOTS)
            if self._active is not None:
                self._active["snapshots"] = [item for item in self._active["snapshots"] if item["position"] <= position]
                self._active["final_state"] = self._active["snapshots"][-1]["state"] if self._active["snapshots"] else None

    def finish(self, replay, error=None):
        with self._lock:
            if self._active is None:
                return
            state = self._state_for_history()
            summary = self._active["summary"]
            summary.update({
                "ended_at": utc_now(), "status": "finished", "outcome": "error" if error else "completed",
                "alerts_count": len(state["alerts"]), "incidents_count": len(state.get("incidents", [])),
                "forecasts_count": len(state["forecasts"]), "actions_count": len(state["actions"]),
                "metrics": state["metrics"],
            })
            self._active["final_state"] = state
            self._active["snapshots"] = list(self._snapshots)[-MAX_SNAPSHOTS:]
            self._active["replay_error"] = error
            record = deepcopy(self._active)
            self._out("run_summary", summary)
            self._runs[summary["run_id"]] = record
            self._write_run(record)
            self._active = None
            self._revision += 1
            self._prune_runs()

    def _write_run(self, record):
        run_id = record["summary"]["run_id"]
        self._atomic_json(self.runs_dir / (run_id + ".json"), record)

    def _prune_runs(self):
        keys = sorted(self._runs, key=lambda item: int(item[-6:]))
        for old_id in keys[:-MAX_FINISHED_RUNS]:
            self._runs.pop(old_id, None)
            path = self.runs_dir / (old_id + ".json")
            if path.parent == self.runs_dir:
                path.unlink(missing_ok=True)

    @property
    def revision(self):
        return self._revision

    def active(self):
        with self._lock:
            if self._active:
                return {"run_id": self._active["summary"]["run_id"], "summary": deepcopy(self._active["summary"])}
            return None

    def list_runs(self, limit=50):
        with self._lock:
            items = [deepcopy(self._runs[key]["summary"]) for key in sorted(self._runs, key=lambda item: int(item[-6:]), reverse=True)]
            return items[:limit]

    def get_run(self, run_id):
        with self._lock:
            record = self._runs.get(run_id)
            if record is None and self._active and self._active["summary"]["run_id"] == run_id:
                record = self._active
            return deepcopy(record) if record else None

    def snapshot_index(self, run_id):
        record = self.get_run(run_id)
        if record is None:
            return None
        items = [{key: item.get(key) for key in ("version", "position", "event_seq", "event_kind", "captured_at")} for item in record["snapshots"]]
        return self._out("snapshot_index", {"run_id": run_id, "items": items})

    def get_snapshot(self, run_id, version=None):
        record = self.get_run(run_id)
        if record is None:
            return None
        snapshots = record["snapshots"]
        if version is None:
            return [self._out("run_snapshot", item) for item in snapshots]
        for item in snapshots:
            if item["version"] == version:
                return self._out("run_snapshot", item)
        return None

    def compare(self, first_id, second_id):
        with self._lock:
            left, right = deepcopy(self._runs.get(first_id)), deepcopy(self._runs.get(second_id))
        if left is None or right is None:
            raise KeyError(first_id if left is None else second_id)
        a, b = left["final_state"] or {}, right["final_state"] or {}
        changes = {}
        identical = True
        for key in ("alerts", "incidents", "forecasts", "actions"):
            l_values, r_values = a.get(key, []), b.get(key, [])
            l_counts = Counter(_canonical(item) for item in l_values)
            r_counts = Counter(_canonical(item) for item in r_values)
            l_map = {_canonical(item): _stable(item) for item in l_values}
            r_map = {_canonical(item): _stable(item) for item in r_values}
            removed = [l_map[item] for item in sorted(l_counts) for _ in range(max(0, l_counts[item] - r_counts[item]))]
            added = [r_map[item] for item in sorted(r_counts) for _ in range(max(0, r_counts[item] - l_counts[item]))]
            changes[key] = {"left_count": len(l_values), "right_count": len(r_values), "added": added, "removed": removed}
            identical = identical and not added and not removed
        left_outcome, right_outcome = left["summary"]["outcome"], right["summary"]["outcome"]
        changes["outcome"] = {"left": left_outcome, "right": right_outcome}
        identical = identical and left_outcome == right_outcome
        left_metrics, right_metrics = _stable(a.get("metrics", {})), _stable(b.get("metrics", {}))
        changes["metrics"] = {"left": left_metrics, "right": right_metrics}
        identical = identical and left_metrics == right_metrics
        result = {"left_run_id": first_id, "right_run_id": second_id, "identical": identical,
                  "changes": changes, "simulation_note": "Differences compare scripted simulation runs; metrics do not predict real-world protection."}
        return self._out("run_comparison", result)

    def _out(self, name, value):
        if self.contracts is not None:
            try:
                self.contracts.validate(name, value)
            except (ContractError, KeyError) as exc:
                raise ValueError("Invalid %s record: %s" % (name, exc))
        return value


def register(ctx):
    replay = ctx.hooks.get("replay")
    if replay is None:
        raise RuntimeError("Replay Studio requires the GRAPH replay controller.")
    service = ReplayStudio(ctx, replay)
    ctx.hooks.register("studio", service)
    ctx.flask_app.extensions["precog_studio"] = service

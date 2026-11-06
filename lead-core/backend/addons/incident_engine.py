"""Incident grouping layered over the existing event, graph and response hooks.

Incidents are scoped to the active replay. Their identifiers and timeline sequence numbers
restart at each replay so a scripted scenario is repeatable. Notes and status decisions are
kept in memory; their audit entries use DETECT's existing append-only audit log.
"""
from copy import deepcopy
from datetime import datetime, timezone
import re
import threading


SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
TACTIC_ORDER = {
    "reconnaissance": 0,
    "resource-development": 1,
    "initial-access": 2,
    "execution": 3,
    "persistence": 4,
    "privilege-escalation": 5,
    "defense-evasion": 6,
    "credential-access": 7,
    "discovery": 8,
    "lateral-movement": 9,
    "collection": 10,
    "command-and-control": 11,
    "exfiltration": 12,
    "impact": 13,
}
MAX_INCIDENTS = 50
MAX_INCIDENT_ALERTS = 200
MAX_NOTES_PER_INCIDENT = 50
MAX_NOTE_LENGTH = 2000
INCIDENT_ID_RE = re.compile(r"^INC-[0-9]{4}$")


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        text = value.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _unique(items):
    return list(dict.fromkeys(value for value in items if value))


def _iso_sort(value):
    parsed = _parse_time(value)
    return parsed.timestamp() if parsed else 0.0


def validate_note(body):
    """Validate a plain-text note. React renders the returned value as text, never markup."""
    if not isinstance(body, str):
        raise ValueError("Note text must be a string.")
    body = body.replace("\r\n", "\n").strip()
    if not body:
        raise ValueError("Note text cannot be empty.")
    if len(body) > MAX_NOTE_LENGTH:
        raise ValueError("Note text must be 2000 characters or fewer.")
    if any((ord(char) < 32 and char not in "\n\t") or ord(char) == 127 for char in body):
        raise ValueError("Note text contains a control character.")
    if "<" in body or ">" in body:
        raise ValueError("Note text must be plain text; markup characters are not allowed.")
    return body


class IncidentAwareEvents:
    """Forward the existing DETECT hook while observing its returned events."""

    def __init__(self, delegate, service):
        self._delegate = delegate
        self._service = service

    def __getattr__(self, name):
        return getattr(self._delegate, name)

    def process_packets(self, rows, severity_override=None):
        if severity_override in SEVERITY_RANK:
            default_risk = {"LOW": 35.0, "MEDIUM": 65.0, "HIGH": 90.0}[severity_override]
            rows = [dict(row, severity=severity_override, risk_score=default_risk) for row in rows]
        events = self._delegate.process_packets(rows)
        for event in events:
            self._service.ingest_alert(event, compromised=False)
        return events

    def process_technique(self, host, technique_id, note=None, compromise=False, **kwargs):
        event = self._delegate.process_technique(
            host, technique_id, note=note, compromise=compromise, **kwargs
        )
        self._service.ingest_alert(event, compromised=bool(compromise))
        return event

    def process_dataset_event(self, row, compromised=False):
        event = self._delegate.process_dataset_event(row, compromise=compromised)
        if event is not None:
            self._service.ingest_alert(event, compromised=bool(compromised))
        return event

    def reset(self, *args, **kwargs):
        result = self._delegate.reset(*args, **kwargs)
        self._service.reset()
        return result


class IncidentService:
    def __init__(self, world, hooks, contracts=None, correlation_window_seconds=300, clock=utc_now, audit_log=None):
        self.world = world
        self.hooks = hooks
        self.contracts = contracts
        self.correlation_window_seconds = max(1, int(correlation_window_seconds))
        self.clock = clock
        self.audit_log = audit_log
        self._lock = threading.RLock()
        self._incidents = {}
        self._timelines = {}
        self._counter = 0
        self._timeline_counters = {}
        self._note_counter = 0
        self._seen_alerts = set()
        self._forecast_states = {}
        self._forecast_incident = {}
        self._action_states = {}
        self._session_id = None
        self._last_session_id = None
        self._versions = {"incidents": 0, "runs": 0, "actions": 0, "notes": 0}
        self._revision = 0

    # ---------- registration and versioning ----------
    def reset(self):
        with self._lock:
            self._clear_run_locked()

    def checkpoint_state(self):
        """Capture mutable incident state for replay step-back, excluding locks and services."""
        names = ("_incidents", "_timelines", "_counter", "_timeline_counters", "_note_counter",
                 "_seen_alerts", "_forecast_states", "_forecast_incident", "_action_states",
                 "_session_id", "_last_session_id", "_versions", "_revision")
        with self._lock:
            return {name: deepcopy(getattr(self, name)) for name in names}

    def restore_checkpoint(self, state):
        names = ("_incidents", "_timelines", "_counter", "_timeline_counters", "_note_counter",
                 "_seen_alerts", "_forecast_states", "_forecast_incident", "_action_states",
                 "_session_id", "_last_session_id")
        with self._lock:
            old_versions, old_revision = self._versions, self._revision
            for name in names:
                setattr(self, name, deepcopy(state[name]))
            restored_versions = state.get("_versions", {})
            self._versions = {key: max(old_versions.get(key, 0), restored_versions.get(key, 0)) + 1 for key in old_versions}
            self._revision = max(old_revision, state.get("_revision", 0)) + 1

    def _clear_run_locked(self):
        self._incidents.clear()
        self._timelines.clear()
        self._counter = 0
        self._timeline_counters.clear()
        self._note_counter = 0
        self._seen_alerts.clear()
        self._forecast_states.clear()
        self._forecast_incident.clear()
        self._action_states.clear()
        self._session_id = None
        self._bump("incidents")
        self._bump("notes")

    def _bump(self, domain):
        self._versions[domain] += 1
        self._revision += 1

    def _ensure_session_locked(self):
        record = self.world.session() or {}
        session_id = record.get("session_id") or "sample"
        if self._session_id is None:
            self._session_id = session_id
        elif self._session_id != session_id:
            self._clear_run_locked()
            self._session_id = session_id
        if self._last_session_id != session_id:
            self._last_session_id = session_id
            self._bump("runs")
        return record

    def feed(self, since=None):
        self.refresh()
        with self._lock:
            return {
                "revision": self._revision,
                "changed": since is None or since != self._revision,
                "versions": deepcopy(self._versions),
            }

    def set_run_version(self, version):
        with self._lock:
            self._versions["runs"] = max(self._versions["runs"], int(version))
            self._revision = max(self._revision, sum(self._versions.values()))

    # ---------- correlation ----------
    def _techniques(self):
        events = self.hooks.get("events")
        table = getattr(events, "techniques", None)
        if table is None and isinstance(events, IncidentAwareEvents):
            table = getattr(events._delegate, "techniques", None)
        return table

    def _tactics(self, technique_id):
        if not technique_id:
            return []
        table = self._techniques()
        try:
            return list(table.require(technique_id).get("tactics", [])) if table else []
        except (KeyError, ValueError, AttributeError):
            return []

    def _technique_name(self, event):
        if event.get("technique_name"):
            return event["technique_name"]
        table = self._techniques()
        try:
            return table.require(event.get("technique_id"))["name"]
        except (KeyError, ValueError, TypeError, AttributeError):
            return event.get("technique_id") or "Security activity"

    def _host_name(self, host_id):
        graph = self.hooks.get("graph")
        if graph is not None:
            try:
                for host in graph.snapshot().get("hosts", []):
                    if host.get("host_id") == host_id:
                        return host.get("name") or host_id
                topology = getattr(graph, "topology", None)
                if topology is not None:
                    host = topology.hosts.get(host_id, {})
                    return host.get("name") or host_id
            except (AttributeError, KeyError, TypeError):
                pass
        return host_id

    def _forward_tactic(self, event, incident):
        new_orders = [TACTIC_ORDER[t] for t in self._tactics(event.get("technique_id")) if t in TACTIC_ORDER]
        old_orders = [
            TACTIC_ORDER[t]
            for item in incident["techniques"]
            for t in item.get("tactics", [])
            if t in TACTIC_ORDER
        ]
        if not new_orders or not old_orders:
            return None
        old_order = max(old_orders)
        new_order = min(new_orders)
        if new_order <= old_order:
            return None
        old_name = next((name for name, order in TACTIC_ORDER.items() if order == old_order), "earlier tactic")
        new_name = next((name for name, order in TACTIC_ORDER.items() if order == new_order), "later tactic")
        return (
            "Same replay session; technique %s continues the ATT&CK tactic chain "
            "from %s to %s."
        ) % (event.get("technique_id"), old_name.replace("-", " "), new_name.replace("-", " "))

    def correlation_reason(self, event, incident):
        """Return the deterministic rule explanation, or None if the alert starts a new case."""
        session_id = self._session_id or "sample"
        if incident.get("session_id") != session_id:
            return None
        if incident.get("status") not in ("open", "reopened"):
            return None
        event_time = _parse_time(event.get("ts"))
        last_time = _parse_time(incident.get("last_alert_at"))
        within_window = bool(
            event_time and last_time
            and abs((event_time - last_time).total_seconds()) <= self.correlation_window_seconds
        )
        event_host = event.get("host")
        if within_window and event_host in incident["affected_hosts"]:
            return (
                "Same replay session; host %s is already in this incident; "
                "the alerts are inside the configured %d second window."
            ) % (event_host, self.correlation_window_seconds)
        graph = self.hooks.get("graph")
        topology = getattr(graph, "topology", None) if graph else None
        if within_window and topology is not None and event_host:
            for source in incident["affected_hosts"]:
                try:
                    if event_host in topology.connections(source):
                        return (
                            "Same replay session; %s is one feasible hop from incident host %s; "
                            "the alerts are inside the configured %d second window."
                        ) % (event_host, source, self.correlation_window_seconds)
                except (ValueError, KeyError):
                    continue
        return self._forward_tactic(event, incident)

    # ---------- creating incidents and timeline events ----------
    def _new_incident_locked(self, event):
        self._counter += 1
        incident_id = "INC-%04d" % self._counter
        stamp = event.get("ts") or self.clock()
        session = self.world.session() or {}
        incident = {
            "incident_id": incident_id,
            "session_id": self._session_id or session.get("session_id") or "sample",
            "scenario_id": session.get("scenario_id"),
            "title": "Security activity from %s" % self._host_name(event.get("host", "unknown")),
            "status": "open",
            "severity": event.get("severity", "LOW"),
            "created_at": stamp,
            "updated_at": stamp,
            "first_alert_at": stamp,
            "last_alert_at": stamp,
            "alert_ids": [],
            "evidence": [],
            "affected_hosts": [],
            "compromised_hosts": [],
            "attack_path": [],
            "techniques": [],
            "forecast_ids": [],
            "forecasts": [],
            "forecast_outcome": None,
            "action_ids": [],
            "actions": [],
            "correlation_reasons": [],
            "notes": [],
            "closed_reason": None,
            "containment_basis": None,
            "duration_seconds": 0,
        }
        self._incidents[incident_id] = incident
        self._timelines[incident_id] = []
        self._timeline_counters[incident_id] = 0
        self._bump("incidents")
        self._add_timeline_locked(incident_id, "alert", stamp, "Incident opened by the first alert.", event.get("event_id"), [event.get("host")], {"severity": event.get("severity")})
        return incident

    def _add_timeline_locked(self, incident_id, event_type, timestamp, summary, ref_id=None, host_ids=None, data=None, actor=None, role=None):
        self._timeline_counters[incident_id] += 1
        sequence = self._timeline_counters[incident_id]
        event = {
            "event_id": "%s-E%04d" % (incident_id, sequence),
            "incident_id": incident_id,
            "sequence": sequence,
            "type": event_type,
            "timestamp": timestamp or self.clock(),
            "summary": summary,
            "ref_id": ref_id,
            "host_ids": _unique(host_ids or []),
            "data": deepcopy(data or {}),
            "actor": actor,
            "role": role,
        }
        timeline = self._timelines[incident_id]
        timeline.append(event)
        del timeline[:-2000]
        return event

    def _set_title_locked(self, incident, event, compromised):
        if not compromised:
            if len(incident["alert_ids"]) == 1:
                tactics = self._tactics(event.get("technique_id"))
                if "reconnaissance" in tactics or "discovery" in tactics:
                    incident["title"] = "Reconnaissance from %s" % self._host_name(event.get("host"))
                elif event.get("technique_id"):
                    incident["title"] = "%s from %s" % (
                        self._technique_name(event), self._host_name(event.get("host"))
                    )
            return
        tactics = self._tactics(event.get("technique_id"))
        if "credential-access" in tactics:
            label = "Credential attack"
        elif "lateral-movement" in tactics:
            label = "Lateral movement"
        else:
            label = self._technique_name(event)
        incident["title"] = "%s from %s" % (label, self._host_name(event.get("host")))

    def ingest_alert(self, event, compromised=False):
        if not isinstance(event, dict) or not event.get("event_id"):
            return None
        with self._lock:
            self._ensure_session_locked()
            event_id = event["event_id"]
            if event_id in self._seen_alerts:
                return None
            if len(self._seen_alerts) >= MAX_INCIDENTS * MAX_INCIDENT_ALERTS:
                return None
            matches = []
            for incident in self._incidents.values():
                reason = self.correlation_reason(event, incident)
                if reason:
                    matches.append((incident, reason))
            if matches:
                incident, reason = matches[-1]
            else:
                incident = self._new_incident_locked(event)
                reason = "First alert in this replay session."
            incident["alert_ids"].append(event_id)
            incident["evidence"].append(deepcopy(event))
            incident["alert_ids"] = incident["alert_ids"][-MAX_INCIDENT_ALERTS:]
            incident["evidence"] = incident["evidence"][-MAX_INCIDENT_ALERTS:]
            incident["affected_hosts"] = _unique(incident["affected_hosts"] + [event.get("host")])
            if event.get("severity") in SEVERITY_RANK and SEVERITY_RANK[event["severity"]] > SEVERITY_RANK.get(incident["severity"], 0):
                incident["severity"] = event["severity"]
            if event.get("technique_id") and all(t["technique_id"] != event["technique_id"] for t in incident["techniques"]):
                incident["techniques"].append({
                    "technique_id": event["technique_id"],
                    "name": self._technique_name(event),
                    "tactics": self._tactics(event["technique_id"]),
                })
            if compromised:
                incident["compromised_hosts"] = _unique(incident["compromised_hosts"] + [event.get("host")])
            incident["correlation_reasons"].append({"event_id": event_id, "reason": reason})
            incident["last_alert_at"] = event.get("ts") or incident["last_alert_at"]
            incident["updated_at"] = event.get("ts") or self.clock()
            self._set_title_locked(incident, event, compromised)
            if len(incident["alert_ids"]) > 1:
                self._add_timeline_locked(
                    incident["incident_id"], "alert", event.get("ts"),
                    "%s alert joined: %s" % (event.get("severity", "LOW"), reason),
                    event_id, [event.get("host")], {"severity": event.get("severity"), "grouping_reason": reason},
                )
            if event.get("technique_id"):
                self._add_timeline_locked(
                    incident["incident_id"], "technique", event.get("ts"),
                    "%s (%s)" % (self._technique_name(event), event["technique_id"]),
                    event_id, [event.get("host")], {"technique_id": event["technique_id"]},
                )
            if compromised:
                self._add_timeline_locked(
                    incident["incident_id"], "compromise", event.get("ts"),
                    "%s became compromised in the simulation." % self._host_name(event.get("host")),
                    event_id, [event.get("host")], {"simulated": True},
                )
            self._seen_alerts.add(event_id)
            self._bump("incidents")
            self._trim_locked()
            return deepcopy(incident)

    # ---------- synchronizing forecasts, actions and host state ----------
    def _incident_for_host_locked(self, host_id, forecast_id=None):
        if forecast_id and forecast_id in self._forecast_incident:
            return self._incidents.get(self._forecast_incident[forecast_id])
        candidates = list(self._incidents.values())
        candidates.reverse()
        for incident in candidates:
            if host_id and host_id in incident["affected_hosts"] + incident["compromised_hosts"]:
                return incident
        graph = self.hooks.get("graph")
        topology = getattr(graph, "topology", None) if graph else None
        if topology and host_id:
            for incident in candidates:
                for source in incident["affected_hosts"]:
                    try:
                        if host_id in topology.connections(source):
                            return incident
                    except (ValueError, KeyError):
                        continue
        return None

    def _record_forecast_outcome_locked(self, incident, forecast):
        if forecast.get("status") not in ("hit", "miss"):
            return
        outcome = forecast.get("outcome") or {}
        blocked = bool(outcome.get("blocked"))
        rank = outcome.get("rank_hit")
        result = "blocked hit" if blocked and rank else ("hit" if rank else "miss")
        target_name = self._host_name(outcome.get("attempted_host")) if outcome.get("attempted_host") else "an unknown host"
        summary = "Forecast %s: the scripted move toward %s was %s." % (
            result, target_name, "blocked" if blocked else "observed"
        )
        forecast_id = forecast["forecast_id"]
        item = next((record for record in incident["forecasts"] if record["forecast_id"] == forecast_id), None)
        if item is not None:
            item["status"] = forecast.get("status")
            item["outcome"] = deepcopy(outcome)
        incident["forecast_outcome"] = {
            "forecast_id": forecast_id,
            "status": forecast.get("status"),
            "blocked": blocked,
            "rank_hit": rank,
            "attempted_host": outcome.get("attempted_host"),
            "label": result,
        }
        self._add_timeline_locked(
            incident["incident_id"], "forecast_outcome", forecast.get("ts") or self.clock(), summary,
            forecast_id, [outcome.get("attempted_host")], deepcopy(incident["forecast_outcome"]),
        )
        self._bump("incidents")

    def _refresh_forecasts_locked(self):
        for forecast in self.world.forecasts():
            forecast_id = forecast.get("forecast_id")
            if not forecast_id:
                continue
            incident = self._incident_for_host_locked(forecast.get("from_host"), forecast_id)
            if incident is None:
                continue
            old = self._forecast_states.get(forecast_id)
            signature = (forecast.get("status"), repr(forecast.get("outcome")))
            if old is None:
                item = {
                    "forecast_id": forecast_id,
                    "from_host": forecast.get("from_host"),
                    "status": forecast.get("status"),
                    "targets": deepcopy(forecast.get("targets", [])),
                    "outcome": deepcopy(forecast.get("outcome")),
                    "ts": forecast.get("ts"),
                }
                incident["forecasts"].append(item)
                incident["forecast_ids"] = _unique(incident["forecast_ids"] + [forecast_id])
                self._forecast_incident[forecast_id] = incident["incident_id"]
                self._add_timeline_locked(
                    incident["incident_id"], "forecast", forecast.get("ts"),
                    "Precog model estimate ranked %d feasible host(s)." % len(forecast.get("targets", [])),
                    forecast_id, [forecast.get("from_host")], {"source": forecast.get("source"), "targets": forecast.get("targets", [])},
                )
                self._forecast_states[forecast_id] = signature
                self._bump("incidents")
                if forecast.get("status") in ("hit", "miss"):
                    self._record_forecast_outcome_locked(incident, forecast)
            elif signature != old:
                old_status, _ = old
                if forecast.get("status") in ("hit", "miss") and old_status != forecast.get("status"):
                    self._record_forecast_outcome_locked(incident, forecast)
                self._forecast_states[forecast_id] = signature
            else:
                self._forecast_states[forecast_id] = signature

    def _refresh_actions_locked(self):
        for action in self.world.actions():
            action_id = action.get("action_id")
            if not action_id:
                continue
            incident = self._incident_for_host_locked(action.get("target_host"), action.get("forecast_id"))
            signature = (action.get("status"), action.get("confirmed_at"), action.get("result"))
            old = self._action_states.get(action_id)
            if signature != old:
                self._versions["actions"] += 1
                self._revision += 1
                if incident is not None:
                    existing = next((item for item in incident["actions"] if item.get("action_id") == action_id), None)
                    if existing is None:
                        incident["actions"].append(deepcopy(action))
                        incident["action_ids"] = _unique(incident["action_ids"] + [action_id])
                        incident["affected_hosts"] = _unique(incident["affected_hosts"] + [action.get("target_host")])
                        self._add_timeline_locked(
                            incident["incident_id"], "containment_proposed", action.get("proposed_at"),
                            "Simulated containment proposed for %s." % self._host_name(action.get("target_host")),
                            action_id, [action.get("target_host")], {"status": action.get("status")},
                        )
                    else:
                        existing.update(deepcopy(action))
                        if action.get("status") == "executed":
                            event_type, summary, timestamp = "confirmed", "Simulated containment was confirmed and executed.", action.get("confirmed_at")
                        elif action.get("status") == "cancelled":
                            event_type, summary, timestamp = "cancelled", "Simulated containment proposal was cancelled.", self.clock()
                        elif action.get("status") == "expired":
                            event_type, summary, timestamp = "expired", "Simulated containment proposal expired without confirmation.", self.clock()
                        else:
                            event_type = summary = timestamp = None
                        if event_type:
                            self._add_timeline_locked(
                                incident["incident_id"], event_type, timestamp, summary,
                                action_id, [action.get("target_host")], {"status": action.get("status"), "result": action.get("result")},
                            )
                            self._bump("incidents")
                self._action_states[action_id] = signature

    def _refresh_graph_locked(self, graph_snapshot):
        hosts = {host.get("host_id"): host for host in graph_snapshot.get("hosts", [])}
        compromised_path = graph_snapshot.get("compromised_path", [])
        for incident in self._incidents.values():
            incident["attack_path"] = [h for h in compromised_path if h in incident["affected_hosts"] or h in incident["compromised_hosts"]]
            for host_id in incident["affected_hosts"]:
                if hosts.get(host_id, {}).get("state") == "compromised":
                    incident["compromised_hosts"] = _unique(incident["compromised_hosts"] + [host_id])
            latest = incident["created_at"]
            end = incident.get("last_alert_at") or latest
            start_dt, end_dt = _parse_time(latest), _parse_time(end)
            incident["duration_seconds"] = max(0, int((end_dt - start_dt).total_seconds())) if start_dt and end_dt else 0

    def _auto_contained_locked(self):
        for incident in self._incidents.values():
            outcome = incident.get("forecast_outcome") or {}
            executed = any(action.get("status") == "executed" for action in incident["actions"])
            if executed and outcome.get("blocked") and incident["status"] == "open":
                incident["status"] = "contained"
                incident["containment_basis"] = (
                    "A confirmed simulated response blocked the forecasted next move. "
                    "The compromised-host list still shows hosts that remain compromised in the replay."
                )
                incident["updated_at"] = self.clock()
                self._add_timeline_locked(
                    incident["incident_id"], "status_change", self.clock(),
                    "Incident marked contained after the confirmed response blocked the scripted move.",
                    incident["forecast_outcome"].get("forecast_id"), incident["affected_hosts"],
                    {"from": "open", "to": "contained", "basis": "blocked simulated move"},
                )
                self._bump("incidents")

    def refresh(self):
        snapshot = self.world.snapshot()
        if not snapshot.get("changed", True):
            return
        graph = snapshot.get("graph", {})
        alerts = snapshot.get("alerts", [])
        with self._lock:
            self._ensure_session_locked()
            for event in sorted(alerts, key=lambda item: (_iso_sort(item.get("ts")), item.get("event_id", ""))):
                host_id = event.get("host")
                host_state = next((h.get("state") for h in graph.get("hosts", []) if h.get("host_id") == host_id), None)
                self.ingest_alert(event, compromised=host_state == "compromised")
            self._refresh_forecasts_locked()
            self._refresh_actions_locked()
            self._refresh_graph_locked(graph)
            self._auto_contained_locked()

    def _trim_locked(self):
        while len(self._incidents) > MAX_INCIDENTS:
            old_id = next(iter(self._incidents))
            self._incidents.pop(old_id, None)
            self._timelines.pop(old_id, None)
            self._timeline_counters.pop(old_id, None)

    # ---------- reads and filtering ----------
    def get(self, incident_id):
        self.refresh()
        with self._lock:
            item = self._incidents.get(incident_id)
            return deepcopy(item) if item else None

    def timeline(self, incident_id):
        self.refresh()
        with self._lock:
            return deepcopy(self._timelines.get(incident_id, []))

    def list_page(self, status=None, severity=None, host=None, technique=None, start=None, end=None, sort="updated_desc", limit=25, cursor=None):
        self.refresh()
        with self._lock:
            items = list(self._incidents.values())
            if status:
                items = [item for item in items if item["status"] == status]
            if severity:
                items = [item for item in items if item["severity"] == severity]
            if host:
                items = [item for item in items if host in item["affected_hosts"]]
            if technique:
                needle = technique.lower()
                items = [item for item in items if any(needle == t["technique_id"].lower() or needle in t["name"].lower() for t in item["techniques"])]
            if start:
                items = [item for item in items if _iso_sort(item["created_at"]) >= start.timestamp()]
            if end:
                items = [item for item in items if _iso_sort(item["created_at"]) <= end.timestamp()]
            if sort == "updated_desc":
                items.sort(key=lambda item: (_iso_sort(item["updated_at"]), item["incident_id"]), reverse=True)
            elif sort == "created_asc":
                items.sort(key=lambda item: (_iso_sort(item["created_at"]), item["incident_id"]))
            else:
                items.sort(key=lambda item: (SEVERITY_RANK.get(item["severity"], 0), _iso_sort(item["updated_at"])), reverse=True)
            total = len(items)
            if cursor:
                positions = [index for index, item in enumerate(items) if item["incident_id"] == cursor]
                if not positions:
                    raise ValueError("The cursor does not identify an incident in this result set.")
                items = items[positions[0] + 1:]
            page = items[:limit]
            next_cursor = page[-1]["incident_id"] if len(items) > limit and page else None
            return {"items": deepcopy(page), "next_cursor": next_cursor, "total": total}

    def snapshot_records(self):
        """Read incident records without refreshing from the world or changing lifecycle state."""
        with self._lock:
            return deepcopy(list(self._incidents.values()))

    # ---------- notes and analyst status ----------
    def add_note(self, incident_id, body, author, role):
        text = validate_note(body)
        with self._lock:
            incident = self._incidents.get(incident_id)
            if incident is None:
                raise KeyError(incident_id)
            if len(incident["notes"]) >= MAX_NOTES_PER_INCIDENT:
                raise ValueError("This incident has reached its 50-note limit.")
            self._note_counter += 1
            note = {
                "note_id": "NOTE-%04d" % self._note_counter,
                "incident_id": incident_id,
                "body": text,
                "created_at": self.clock(),
                "author": author,
                "role": role,
            }
            incident["notes"].append(note)
            incident["updated_at"] = note["created_at"]
            self._add_timeline_locked(
                incident_id, "note", note["created_at"], text,
                note["note_id"], incident["affected_hosts"], {}, actor=author, role=role,
            )
            self._bump("notes")
            self._bump("incidents")
            self._audit("note", incident_id, "%s (%s) added an incident note." % (author, role), author, role, text=text)
            return deepcopy(note)

    def change_status(self, incident_id, status, reason, confirm, author, role):
        if status not in ("closed", "reopened"):
            raise ValueError("Status may be closed or reopened. Contained is set by a verified simulated response.")
        if confirm is not True:
            raise ValueError("Confirm this status change explicitly.")
        if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 500:
            raise ValueError("A reason of 1 to 500 characters is required.")
        reason = reason.strip()
        with self._lock:
            incident = self._incidents.get(incident_id)
            if incident is None:
                raise KeyError(incident_id)
            previous = incident["status"]
            allowed = (previous in ("open", "reopened", "contained") and status == "closed") or (previous == "closed" and status == "reopened")
            if not allowed:
                raise ValueError("The incident cannot move from %s to %s." % (previous, status))
            incident["status"] = status
            incident["closed_reason"] = reason if status == "closed" else None
            incident["updated_at"] = self.clock()
            self._add_timeline_locked(
                incident_id, "status_change", incident["updated_at"],
                "Incident %s by %s (%s): %s" % (status, author, role, reason),
                incident_id, incident["affected_hosts"], {"from": previous, "to": status, "reason": reason},
                actor=author, role=role,
            )
            self._bump("incidents")
            self._audit(
                "status_change", incident_id,
                "%s (%s) changed status from %s to %s." % (author, role, previous, status),
                author, role, reason=reason,
            )
            return deepcopy(incident)

    def _audit(self, event_type, incident_id, summary, actor, role, text=None, reason=None):
        if self.audit_log is not None:
            self.audit_log.record(event_type, incident_id, summary, actor, role, text=text, reason=reason)


class IncidentEngine:
    """Public hook facade used by the add-on routes."""

    def __init__(self, service):
        self.service = service

    def feed(self, since=None):
        return self.service.feed(since)

    def set_run_version(self, version):
        return self.service.set_run_version(version)

    def refresh(self):
        return self.service.refresh()

    def get(self, incident_id):
        return self.service.get(incident_id)

    def timeline(self, incident_id):
        return self.service.timeline(incident_id)

    def list_page(self, **kwargs):
        return self.service.list_page(**kwargs)

    def snapshot_records(self):
        return self.service.snapshot_records()

    def add_note(self, *args, **kwargs):
        return self.service.add_note(*args, **kwargs)

    def change_status(self, *args, **kwargs):
        return self.service.change_status(*args, **kwargs)

    def reset(self):
        return self.service.reset()

    def checkpoint_state(self):
        return self.service.checkpoint_state()

    def restore_checkpoint(self, state):
        return self.service.restore_checkpoint(state)


def register(ctx):
    base = ctx.hooks.get("events")
    if base is None:
        return
    window = getattr(ctx.config, "incident_correlation_window_seconds", 300)
    from .incident_audit import IncidentAuditLog

    audit_path = ctx.config.data_dir / "audit" / "incidents.json"
    audit_log = IncidentAuditLog(audit_path, ctx.contracts)
    service = IncidentService(ctx.world, ctx.hooks, ctx.contracts, window, audit_log=audit_log)
    ctx.hooks.register("incidents", IncidentEngine(service))
    ctx.hooks.register("events", IncidentAwareEvents(base, service))
    ctx.flask_app.extensions["precog_incidents"] = service

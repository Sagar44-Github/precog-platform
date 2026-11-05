"""The one in-memory picture of the whole system (the "single source of truth").

Every change goes through a method here. Each change adds 1 to the version number,
so a polling client can ask "anything new since version N?" and get a tiny answer.
All methods are safe to call from several threads at once.
"""
import copy
import threading
from collections import deque
from datetime import datetime, timezone

MAX_ALERTS = 200

MAX_SESSIONS = 20
MAX_TIME_TRAVEL_SNAPSHOTS = 200


def _empty_graph():
    return {"hosts": [], "edges": [], "compromised_path": []}


def _empty_replay():
    return {"state": "idle", "scenario_id": None, "speed": 1.0, "position": 0}


def _empty_metrics():

    return {
        "forecasts_resolved": 0, "hits": 0, "hit_rate": None, "precision_at_1": None,
        "precision_at_3": None, "calibration_bins": [], "containment_success_rate": None,
    }


class WorldState:
    def __init__(self, contracts=None):
        """contracts: an addons.contracts.Contracts object, or None to skip checking."""

        self._lock = threading.RLock()
        self._contracts = contracts
        self._history = deque(maxlen=MAX_TIME_TRAVEL_SNAPSHOTS)

        self.version = 0
        self._reset_locked()

        self._sessions = []
        self._incident_annotations = {}

        self._push_tokens = []
        self._detection_report = None

    # ---------- helpers ----------
    def _check(self, name, data):
        if self._contracts is not None:
            self._contracts.validate(name, data)
        return data

    def _bump(self):
        self.version += 1
        snapshot = {
            "version": self.version,
            "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "session_id": self._session.get("session_id") if self._session else None,
            "graph": copy.deepcopy(self._graph),
            "alerts": copy.deepcopy(self._alerts[:20]),
            "forecast": copy.deepcopy(self._forecasts[-1]) if self._forecasts else None,
            "actions": copy.deepcopy(self._actions[-20:]),
            "replay": copy.deepcopy(self._replay),
            "metrics": copy.deepcopy(self._metrics),
        }
        self._check("time_travel_snapshot", snapshot)
        self._history.append(snapshot)
        return self.version

    def _reset_locked(self):
        self._graph = _empty_graph()
        self._host_history = {}
        self._alerts = []
        self._session_alerts = []

        self._forecasts = []
        self._actions = []

        self._replay = _empty_replay()
        self._metrics = _empty_metrics()

        self._session = None

    # ---------- reading ----------
    def snapshot(self, since=None):
        """What /api/x/state returns. since = the version the client already has."""

        with self._lock:
            if since is not None and since == self.version:
                return {"version": self.version, "changed": False}

            return copy.deepcopy({
                "version": self.version, "changed": True, "graph": self._graph,
                "alerts": self._alerts, "forecast": self._current_forecast_locked(),
                "actions": self._actions, "replay": self._replay, "metrics": self._metrics,
            })

    def _current_forecast_locked(self):

        for forecast in reversed(self._forecasts):
            if forecast["status"] == "pending":
                return forecast
        return None

    def graph(self):

        with self._lock:
            return copy.deepcopy(self._graph)

    def host_state_history(self, host_id):
        with self._lock:
            return copy.deepcopy(self._host_history.get(host_id, []))

    def alerts(self, limit=50):

        with self._lock:
            return copy.deepcopy(self._alerts[: max(0, limit)])

    def get_alert(self, event_id):

        with self._lock:
            for alert in self._alerts:
                if alert["event_id"] == event_id:
                    return copy.deepcopy(alert)
        return None


    def forecasts(self, status=None, include_archived=False):
        with self._lock:
            items = []
            if include_archived:
                active_id = self._session.get("session_id") if self._session is not None else None
                for record in reversed(self._sessions):
                    if active_id is not None and record.get("session_id") == active_id:
                        continue
                    items.extend(record.get("forecasts", []))
            items.extend(self._forecasts)
            items = [f for f in items if status is None or f["status"] == status]
            return copy.deepcopy(items)

    def current_forecast(self):

        with self._lock:
            return copy.deepcopy(self._current_forecast_locked())

    def actions(self, include_archived=False):
        with self._lock:
            items = []
            if include_archived:
                active_id = self._session.get("session_id") if self._session is not None else None
                for record in reversed(self._sessions):
                    if active_id is not None and record.get("session_id") == active_id:
                        continue
                    items.extend(record.get("actions", []))
            items.extend(self._actions)
            return copy.deepcopy(items)

    def get_action(self, action_id):

        with self._lock:
            for action in self._actions:
                if action["action_id"] == action_id:
                    return copy.deepcopy(action)
        return None

    def replay(self):

        with self._lock:
            return copy.deepcopy(self._replay)

    def metrics(self):
        with self._lock:
            return copy.deepcopy(self._metrics)

    def session(self):
        with self._lock:
            return copy.deepcopy(self._session)

    def sessions(self):
        with self._lock:
            return copy.deepcopy(self._sessions)

    def time_travel(self, session_id=None, limit=120):
        """Return bounded read-only snapshots in chronological order."""
        with self._lock:
            snapshots = list(self._history)
            if session_id:
                snapshots = [item for item in snapshots if item.get("session_id") == session_id]
            return copy.deepcopy(snapshots[-max(1, min(int(limit), MAX_TIME_TRAVEL_SNAPSHOTS)):])

    def incident_sessions(self):
        """Return the bounded session history plus the live session with its alert evidence."""
        with self._lock:
            records = copy.deepcopy(self._sessions)
            if self._session is not None:
                current = copy.deepcopy(self._session)
                current["alerts"] = copy.deepcopy(self._session_alerts)
                current["forecasts"] = copy.deepcopy(self._forecasts)
                current["actions"] = copy.deepcopy(self._actions)
                records = [item for item in records if item.get("session_id") != current.get("session_id")]
                records.insert(0, current)
            for record in records:
                incident_id = "inc-" + record["session_id"]
                annotation = self._incident_annotations.get(incident_id, {})
                record["status"] = annotation.get("status")
                record["notes"] = copy.deepcopy(annotation.get("notes", []))
            return records

    def add_incident_note(self, incident_id, note):
        with self._lock:
            annotation = self._incident_annotations.setdefault(incident_id, {"status": None, "notes": []})
            annotation["notes"].append(copy.deepcopy(note))
            del annotation["notes"][:-100]
            self._bump()
            return copy.deepcopy(note)

    def set_incident_status(self, incident_id, status):
        with self._lock:
            annotation = self._incident_annotations.setdefault(incident_id, {"status": None, "notes": []})
            annotation["status"] = status
            self._bump()
            return status

    def detection_report(self):
        with self._lock:
            return copy.deepcopy(self._detection_report)

    def push_tokens(self):
        with self._lock:
            return list(self._push_tokens)

    # ---------- writing (each one bumps the version) ----------
    def set_graph(self, graph):
        with self._lock:
            checked = self._check("graph_snapshot", graph)
            previous = {host["host_id"]: host["state"] for host in self._graph.get("hosts", [])}
            now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            for host in checked.get("hosts", []):
                host_id, state = host["host_id"], host["state"]
                prior_state = previous.get(host_id)
                history = self._host_history.setdefault(host_id, [])
                if prior_state != state:
                    history.append({"ts": now, "from_state": prior_state, "state": state})
                    del history[:-20]
            self._graph = copy.deepcopy(checked)
            return self._bump()

    def add_alert(self, alert):
        with self._lock:
            self._check("security_event", alert)
            self._alerts.insert(0, copy.deepcopy(alert))
            del self._alerts[MAX_ALERTS:]
            if self._session is not None:
                self._session_alerts.append(copy.deepcopy(alert))
                del self._session_alerts[:-MAX_ALERTS]
            return self._bump()

    def set_forecast(self, forecast):
        """Store a new forecast. An older pending forecast becomes 'superseded'."""
        with self._lock:
            forecast = copy.deepcopy(forecast)
            if self._session is not None:
                forecast.setdefault("session_id", self._session.get("session_id"))
            self._check("forecast", forecast)
            for old in self._forecasts:
                if old["status"] == "pending" and old["forecast_id"] != forecast["forecast_id"]:
                    old["status"] = "superseded"
            self._forecasts = [f for f in self._forecasts if f["forecast_id"] != forecast["forecast_id"]]
            self._forecasts.append(forecast)
            return self._bump()

    def resolve_forecast(self, forecast_id, status, outcome):
        """status is 'hit' or 'miss'. outcome follows the forecast contract."""
        if status not in ("hit", "miss"):
            raise ValueError("status must be 'hit' or 'miss'")
        with self._lock:
            for forecast in self._forecasts:
                if forecast["forecast_id"] == forecast_id:
                    updated = dict(forecast, status=status, outcome=outcome)
                    self._check("forecast", updated)
                    forecast.update(updated)
                    return self._bump()
        raise KeyError("No forecast with id %s" % forecast_id)

    def upsert_action(self, action):
        with self._lock:
            action = copy.deepcopy(action)
            if self._session is not None:
                action.setdefault("session_id", self._session.get("session_id"))
            self._check("containment_action", action)
            for index, existing in enumerate(self._actions):
                if existing["action_id"] == action["action_id"]:
                    self._actions[index] = copy.deepcopy(action)
                    break
            else:
                self._actions.append(copy.deepcopy(action))
            return self._bump()

    def set_replay(self, replay):
        with self._lock:
            self._replay = copy.deepcopy(self._check("replay_status", replay))
            return self._bump()

    def set_metrics(self, metrics):
        with self._lock:
            self._metrics = copy.deepcopy(self._check("session_metrics", metrics))
            return self._bump()

    def set_session(self, record):
        with self._lock:
            prior_id = self._session.get("session_id") if self._session else None
            self._session = copy.deepcopy(self._check("session_record", record))
            if prior_id != record["session_id"]:
                self._session_alerts = copy.deepcopy(record.get("alerts", self._alerts))
            return self._bump()

    def archive_session(self):
        """Move the current session into the history list (used when a replay ends)."""
        with self._lock:
            if self._session is not None:
                archived = copy.deepcopy(self._session)
                archived["alerts"] = copy.deepcopy(self._session_alerts)
                archived["forecasts"] = copy.deepcopy(self._forecasts)
                archived["actions"] = copy.deepcopy(self._actions)
                session_id = archived.get("session_id")
                for forecast in archived["forecasts"]:
                    forecast.setdefault("session_id", session_id)
                self._check("session_record", archived)
                self._sessions = [item for item in self._sessions if item["session_id"] != archived["session_id"]]
                self._sessions.insert(0, archived)
                del self._sessions[MAX_SESSIONS:]
            return self._bump()

    def set_detection_report(self, report):
        with self._lock:
            self._detection_report = copy.deepcopy(self._check("detection_report", report))
            return self._bump()

    def add_push_token(self, token):
        with self._lock:
            if token not in self._push_tokens:
                self._push_tokens.append(token)
            return len(self._push_tokens)

    def reset(self):
        """Forget everything about the current replay (used when a replay restarts)."""
        with self._lock:
            self._reset_locked()
            return self._bump()

    def load_full_state(self, state):
        """Replace the whole picture at once (used by sample mode). state is a world_state dict."""
        with self._lock:
            self._check("world_state", state)
            self._graph = copy.deepcopy(state["graph"])
            self._alerts = copy.deepcopy(state["alerts"])
            forecast = state.get("forecast")
            self._forecasts = [copy.deepcopy(forecast)] if forecast else []
            self._actions = copy.deepcopy(state["actions"])
            self._replay = copy.deepcopy(state["replay"])
            self._metrics = copy.deepcopy(state["metrics"])
            return self._bump()

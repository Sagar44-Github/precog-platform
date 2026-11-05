"""Governed, simulation-only response playbooks and release actions.

The service records decisions beneath the add-on data directory and delegates host
containment to the existing propose/confirm service. It never changes a real network.
"""
import json
import os
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .errors import ApiError


RECORD_LIMIT = 2000
REASON_LIMIT = 500
PLAYBOOK_POLICY = {
    "contain-host": {"label": "Contain one host", "scope": "host", "roles": ["analyst", "admin"]},
    "contain-zone": {"label": "Contain a zone", "scope": "zone", "roles": ["admin"]},
    "contain-predicted-path": {"label": "Contain predicted path", "scope": "path", "roles": ["admin"]},
    "contain-top-three": {"label": "Contain Top-3 targets", "scope": "forecast", "roles": ["admin"]},
    "release-host": {"label": "Release one host", "scope": "host", "roles": ["admin"]},
}


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_reason(value, required=True):
    if not isinstance(value, str):
        if required:
            raise ApiError("bad_request", "A plain-text reason is required.", 400)
        return ""
    value = "".join(char for char in value.strip() if char >= " " and char != "\x7f")
    if required and not value:
        raise ApiError("bad_request", "A plain-text reason is required.", 400)
    if len(value) > REASON_LIMIT:
        raise ApiError("bad_request", "Reason text must be 500 characters or fewer.", 400)
    return value


class GovernanceService:
    def __init__(self, ctx, clock=utc_now, confirm_seconds=60):
        self.ctx = ctx
        self.world = ctx.world
        self.hooks = ctx.hooks
        self.contracts = ctx.contracts
        self.clock = clock
        self.confirm_seconds = int(confirm_seconds)
        self.two_person_zone = os.environ.get("REQUIRE_TWO_PERSON_ZONE_APPROVAL", "0").strip().lower() in ("1", "true", "yes", "on")
        self.path = Path(ctx.config.data_dir) / "governance" / "records.json"
        self._lock = threading.RLock()
        self._approvals = []
        self._releases = []
        self._counter = 0
        self.revision = 0
        self._load()

    def list_playbooks(self):
        return [{
            "playbook_id": playbook_id,
            "label": data["label"],
            "scope": data["scope"],
            "allowed_roles": list(data["roles"]),
            "requires_second_approval": playbook_id == "contain-zone" and self.two_person_zone,
            "description": self._description(playbook_id),
            "simulation_only": True,
        } for playbook_id, data in PLAYBOOK_POLICY.items()]

    def preview(self, playbook_id, actor_role, host_id=None, zone=None, forecast_id=None):
        policy = self._policy(playbook_id, actor_role)
        graph = self._graph()
        topology = graph.topology
        forecast = self._forecast(forecast_id) if forecast_id else self._latest_forecast()
        states = graph.states()

        if playbook_id == "contain-host":
            targets = [self._known_host(host_id)]
        elif playbook_id == "contain-zone":
            if not isinstance(zone, str) or not zone.strip():
                raise ApiError("bad_request", "Choose a zone to contain.", 400)
            targets = [item for item in topology.host_ids() if topology.hosts[item].get("zone") == zone.strip()]
            if not targets:
                raise ApiError("not_found", "There is no demo zone named '%s'." % zone.strip(), 404)
        elif playbook_id in ("contain-predicted-path", "contain-top-three"):
            if forecast is None:
                raise ApiError("no_forecast", "Run a replay to create a forecast first.", 409)
            ranked = sorted(forecast["targets"], key=lambda row: row["rank"])
            if playbook_id == "contain-top-three":
                targets = [row["host_id"] for row in ranked[:3]]
            else:
                targets = []
                if ranked:
                    source, destination = forecast["from_host"], ranked[0]["host_id"]
                    paths = topology.paths(source, destination, limit=1)
                    path = paths[0] if paths else [source, destination]
                    targets = path[1:]
        else:
            if not isinstance(host_id, str) or not host_id.strip():
                raise ApiError("bad_request", "Choose a host to release.", 400)
            target = self._known_host(host_id)
            if states[target] != "contained":
                raise ApiError("invalid_state", "Only a currently contained host can be released.", 409)
            targets = [target]

        targets = list(dict.fromkeys(targets))
        targets = [item for item in targets if item in states]
        if playbook_id == "release-host":
            eligible = targets
        else:
            eligible = [item for item in targets if states[item] != "contained"]
        if not eligible:
            raise ApiError("no_targets", "This playbook has no eligible hosts in the current simulated state.", 409)

        target_set = set(eligible)
        changed_edges = [
            {"from_host": source, "to_host": destination}
            for source, destination in topology.feasible_edges()
            if source in target_set or destination in target_set
        ]
        affected = []
        confidence_by_host = {row["host_id"]: float(row["confidence"]) for row in (forecast or {}).get("targets", [])}
        criticality_total = 0.0
        probability_removed = 0.0
        probability_restored = 0.0
        for item in eligible:
            asset = topology._assets.get(item, {})
            criticality = float(asset.get("criticality", 0.5))
            criticality_total += criticality
            confidence = confidence_by_host.get(item, 0.0)
            if playbook_id == "release-host":
                probability_restored += confidence
            else:
                probability_removed += confidence
            affected.append({
                "host_id": item,
                "name": topology.hosts[item].get("name", item),
                "state": states[item],
                "criticality": round(criticality, 4),
                "forecast_probability": round(confidence, 6),
            })
        preview = {
            "playbook_id": playbook_id,
            "forecast_id": forecast.get("forecast_id") if forecast else None,
            "hosts_affected": affected,
            "feasible_edges_changed": changed_edges,
            "probability_removed": round(probability_removed, 6),
            "probability_restored": round(probability_restored, 6),
            "criticality_total": round(criticality_total, 4),
            "side_effects": [
                "The affected host cannot be reached or used by the simulated attacker.",
                "Legitimate use is also interrupted in this simulation.",
                "No firewall, endpoint, account, or real network setting is changed.",
            ] if playbook_id != "release-host" else [
                "The host returns to normal simulated state and can be reached again.",
                "This does not change any real network setting.",
            ],
            "expected_reevaluation": "After confirmation, the simulation re-evaluates the next scripted response against the forecast and updates its outcome.",
            "simulation_only": True,
        }
        self._validate("playbook_preview", preview)
        return preview

    def propose(self, playbook_id, actor, actor_role, reason, host_id=None, zone=None, forecast_id=None, incident_id=None):
        reason = _clean_reason(reason)
        preview = self.preview(playbook_id, actor_role, host_id, zone, forecast_id)
        self._policy(playbook_id, actor_role)
        now = self.clock()
        action_id = self._next_id()
        require_approval = playbook_id == "contain-zone" and self.two_person_zone
        common = {
            "action_id": action_id,
            "playbook_id": playbook_id,
            "status": "pending_confirmation" if playbook_id == "release-host" else ("pending_approval" if require_approval else "pending_confirmation"),
            "proposed_by": actor,
            "proposed_role": actor_role,
            "proposed_at": _iso(now),
            "expires_at": _iso(now + timedelta(seconds=self.confirm_seconds)),
            "reason": reason,
            "preview_snapshot": preview,
            "run_id": (self.world.session() or {}).get("session_id"),
            "updated_at": None,
            "cancelled_by": None,
            "cancelled_role": None,
            "cancellation_reason": None,
        }
        if playbook_id == "release-host":
            host = preview["hosts_affected"][0]
            record = dict(common, host_id=host["host_id"], host_name=host["name"], previous_state=host["state"],
                          confirmed_by=None, confirmed_role=None, confirmed_at=None,
                          execution_summary=None)
            self._validate("release_record", record)
        else:
            record = dict(common, status="pending_approval" if require_approval else "pending_confirmation",
                          host_action_ids=[], incident_id=incident_id if isinstance(incident_id, str) and incident_id[:4] == "INC-" else None,
                          approval=None, execution_summary=None)
            self._validate("approval_record", record)
        with self._lock:
            self._expire_locked()
            self._check_conflicts(record)
            (self._releases if playbook_id == "release-host" else self._approvals).append(record)
            self._trim_locked()
            self._changed_locked()
            self._audit(action_id, "Playbook proposal recorded: %s by %s (%s)." % (playbook_id, actor, actor_role))
            return dict(record)

    def approve(self, action_id, actor, actor_role, decision, reason=""):
        with self._lock:
            self._expire_locked()
            record = self._find(self._approvals, action_id)
            if record["status"] != "pending_approval":
                raise ApiError("not_pending", "This proposal is not waiting for approval.", 409)
            if actor == record["proposed_by"]:
                raise ApiError("two_person_required", "A different administrator must approve this zone action.", 403)
            if decision not in ("approve", "reject"):
                raise ApiError("bad_request", "Decision must be 'approve' or 'reject'.", 400)
            reason = _clean_reason(reason, required=decision == "reject")
            now = _iso(self.clock())
            record["approval"] = {"actor": actor, "role": actor_role, "decision": decision, "at": now, "reason": reason}
            record["status"] = "pending_confirmation" if decision == "approve" else "rejected"
            record["updated_at"] = now
            self._save_record_locked("approval_record", record)
            self._changed_locked()
            verb = "approved" if decision == "approve" else "rejected"
            self._audit(action_id, "Zone playbook %s by %s (%s)." % (verb, actor, actor_role))
            return dict(record)

    def confirm(self, action_id, actor, actor_role):
        with self._lock:
            record = self._find_pending(action_id)
            self._check_run(record)
            if record["status"] == "pending_approval":
                raise ApiError("approval_required", "A second administrator must approve this proposal first.", 409)
            if record["status"] != "pending_confirmation":
                raise ApiError("not_pending", "This proposal is already %s." % record["status"], 409)
            if record["playbook_id"] == "release-host":
                return self._confirm_release(record, actor, actor_role)
            containment = self.hooks.require("containment")
            live_pending = set(getattr(containment, "_pending", {}))
            pending = [item for item in self.world.actions() if item.get("action_id") in live_pending]
            if pending:
                raise ApiError("action_conflict", "Resolve the existing single-host containment request first.", 409)
            executed = []
            try:
                for target in record["preview_snapshot"]["hosts_affected"]:
                    child = containment.propose(self.world, target["host_id"], record["preview_snapshot"].get("forecast_id"), "console")
                    final = containment.confirm(self.world, child["action_id"])
                    executed.append(final["action_id"])
            except Exception as exc:
                record["host_action_ids"] = executed
                record["status"] = "partially_executed" if executed else "cancelled"
                record["execution_summary"] = "Some simulated host actions completed before an error: %s" % str(exc)[:240]
                record["updated_at"] = _iso(self.clock())
                self._save_record_locked("approval_record", record)
                self._changed_locked()
                self._audit(action_id, "Playbook execution stopped with status %s." % record["status"])
                raise ApiError("execution_failed", record["execution_summary"], 409)
            record["host_action_ids"] = executed
            record["status"] = "executed"
            record["execution_summary"] = "Executed simulated containment for %d host(s); the replay will re-evaluate its next response." % len(executed)
            record["updated_at"] = _iso(self.clock())
            self._save_record_locked("approval_record", record)
            self._changed_locked()
            self._audit(action_id, "Playbook execution confirmed by %s (%s); %d host(s) contained in simulation." % (actor, actor_role, len(executed)))
            return dict(record)

    def cancel(self, action_id, actor, actor_role, reason="Cancelled by an administrator."):
        reason = _clean_reason(reason)
        with self._lock:
            record = self._find_pending(action_id)
            if record["status"] not in ("pending_approval", "pending_confirmation"):
                raise ApiError("not_pending", "This proposal cannot be cancelled in its current state.", 409)
            record["status"] = "cancelled"
            record["updated_at"] = _iso(self.clock())
            record["cancelled_by"] = actor
            record["cancelled_role"] = actor_role
            record["cancellation_reason"] = reason
            kind = "release_record" if record["playbook_id"] == "release-host" else "approval_record"
            self._save_record_locked(kind, record)
            self._changed_locked()
            self._audit(action_id, "Playbook request cancelled by %s (%s): %s" % (actor, actor_role, reason))
            return dict(record)

    def records(self, limit=100):
        if not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ApiError("bad_request", "Limit must be between 1 and 200.", 400)
        with self._lock:
            self._expire_locked()
            return {
                "approvals": [dict(item) for item in self._approvals[-limit:][::-1]],
                "releases": [dict(item) for item in self._releases[-limit:][::-1]],
                "revision": self.revision,
            }

    def _confirm_release(self, record, actor, actor_role):
        graph = self._graph()
        host_id = record["preview_snapshot"]["hosts_affected"][0]["host_id"]
        if graph.host_state(host_id) != "contained":
            raise ApiError("invalid_state", "The host is no longer contained; this release proposal is stale.", 409)
        graph.set_host_state(host_id, "normal")
        now = _iso(self.clock())
        record["status"] = "released"
        record["confirmed_by"] = actor
        record["confirmed_role"] = actor_role
        record["confirmed_at"] = now
        record["updated_at"] = now
        record["execution_summary"] = "Host returned to normal simulated state."
        self._save_record_locked("release_record", record)
        self._changed_locked()
        self._audit(record["action_id"], "Simulated host release confirmed by %s (%s): %s" % (actor, actor_role, record["reason"]))
        return dict(record)

    def _policy(self, playbook_id, role):
        policy = PLAYBOOK_POLICY.get(playbook_id)
        if policy is None:
            raise ApiError("unknown_playbook", "Unknown response playbook.", 404)
        if role not in policy["roles"]:
            raise ApiError("forbidden", "The %s role cannot run this playbook." % role, 403)
        return policy

    def _description(self, playbook_id):
        return {
            "contain-host": "Simulated single-host containment. Analysts and administrators may propose and confirm.",
            "contain-zone": "Simulated containment of every eligible host in one demo zone. Administrator only.",
            "contain-predicted-path": "Simulated containment of the hosts along the most likely forecast route. Administrator only.",
            "contain-top-three": "Simulated containment of eligible hosts in Precog's ranked top three. Administrator only.",
            "release-host": "Restore one contained host to normal simulated state after a mandatory reason. Administrator only.",
        }[playbook_id]

    def _graph(self):
        return self.hooks.require("graph")

    def _known_host(self, host_id):
        if not isinstance(host_id, str) or not host_id.strip():
            raise ApiError("bad_request", "Choose a host id.", 400)
        graph = self._graph()
        try:
            graph.host_state(host_id.strip())
        except ValueError:
            raise ApiError("unknown_host", "Unknown demo host id.", 404)
        return host_id.strip()

    def _forecast(self, forecast_id):
        for item in self.world.forecasts():
            if item.get("forecast_id") == forecast_id:
                return item
        raise ApiError("unknown_forecast", "Unknown forecast id.", 404)

    def _latest_forecast(self):
        forecasts = self.world.forecasts()
        return next((item for item in reversed(forecasts) if item.get("status") in ("pending", "hit", "miss")), None)

    def _next_id(self):
        with self._lock:
            self._counter += 1
            return "PB-ACT-%06d" % self._counter

    def _check_conflicts(self, record):
        new_hosts = {item["host_id"] for item in record["preview_snapshot"]["hosts_affected"]}
        for existing in self._approvals + self._releases:
            if existing.get("status") not in ("pending_approval", "pending_confirmation"):
                continue
            old_hosts = {item["host_id"] for item in existing.get("preview_snapshot", {}).get("hosts_affected", [])}
            if new_hosts & old_hosts:
                raise ApiError("overlapping_action", "Another pending response already covers one of these hosts.", 409)

    def _find(self, records, action_id):
        for record in records:
            if record["action_id"] == action_id:
                return record
        raise ApiError("unknown_action", "No governance request exists with that action id.", 404)

    def _find_pending(self, action_id):
        self._expire_locked()
        record = next((item for item in self._approvals + self._releases if item["action_id"] == action_id), None)
        if record is None:
            raise ApiError("unknown_action", "No governance request exists with that action id.", 404)
        return record

    def _check_run(self, record):
        current = (self.world.session() or {}).get("session_id")
        if record.get("run_id") != current:
            record["status"] = "cancelled"
            record["updated_at"] = _iso(self.clock())
            self._save_record_locked("release_record" if record["playbook_id"] == "release-host" else "approval_record", record)
            self._changed_locked()
            self._audit(record["action_id"], "Stale response request cancelled because the replay session changed.")
            raise ApiError("stale_request", "The replay changed after this proposal. Preview and propose again.", 409)

    def _expire_locked(self):
        now = self.clock()
        for record in self._approvals + self._releases:
            if record.get("status") not in ("pending_approval", "pending_confirmation"):
                continue
            try:
                expires = datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00"))
            except (TypeError, ValueError, KeyError):
                expires = now
            if now >= expires:
                record["status"] = "expired"
                record["updated_at"] = _iso(now)
                self._save_record_locked("release_record" if record["playbook_id"] == "release-host" else "approval_record", record)
                self._changed_locked()
                self._audit(record["action_id"], "Response proposal expired without confirmation.")

    def _save_record_locked(self, kind, record):
        self._validate(kind, record)
        self._persist_locked()

    def _validate(self, name, record):
        if self.contracts is not None:
            self.contracts.validate(name, record)

    def _changed_locked(self):
        self.revision += 1
        self._persist_locked()

    def _audit(self, action_id, summary):
        events = self.hooks.get("events")
        if events is not None:
            try:
                events.audit_record("containment", action_id, "Governance: " + summary)
            except Exception:
                # The durable governance record remains available if the optional audit hook fails.
                pass

    def _trim_locked(self):
        combined = [(record.get("proposed_at", ""), kind, record) for kind, records in (("approval_record", self._approvals), ("release_record", self._releases)) for record in records]
        if len(combined) > RECORD_LIMIT:
            keep = {id(item[2]) for item in sorted(combined, key=lambda item: item[0])[-RECORD_LIMIT:]}
            self._approvals = [item for item in self._approvals if id(item) in keep]
            self._releases = [item for item in self._releases if id(item) in keep]
        self._persist_locked()

    def _persist_locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entries = ([{"kind": "approval_record", "record": item} for item in self._approvals]
                   + [{"kind": "release_record", "record": item} for item in self._releases])
        fd, temporary = tempfile.mkstemp(prefix=".governance-", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(entries[-RECORD_LIMIT:], stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _load(self):
        if not self.path.is_file():
            return
        try:
            entries = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                return
            for entry in entries[-RECORD_LIMIT:]:
                kind, record = entry.get("kind"), entry.get("record")
                if kind not in ("approval_record", "release_record") or not isinstance(record, dict):
                    continue
                self._validate(kind, record)
                (self._releases if kind == "release_record" else self._approvals).append(record)
                suffix = record.get("action_id", "").rsplit("-", 1)[-1]
                if suffix.isdigit():
                    self._counter = max(self._counter, int(suffix))
            self.revision = len(self._approvals) + len(self._releases)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            # The platform starts in-memory and remains usable if old optional demo data is unreadable.
            self._approvals, self._releases, self._counter, self.revision = [], [], 0, 0


def register(ctx):
    service = GovernanceService(ctx)
    ctx.flask_app.extensions["precog_governance"] = service

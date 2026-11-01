"""Containment and re-evaluation (simulated). Nothing real is ever changed: a host's state becomes 'contained' and a log entry is written.

The flow is two steps, so no client can skip the confirmation (TRD DD-10):
    propose(...)  -> an action in 'pending_confirmation'
    confirm(...)  -> the host becomes 'contained' (graph hook), the action becomes 'executed'
    cancel(...)   -> the action becomes 'cancelled'
A pending action that nobody answers becomes 'expired' after confirm_seconds (default 60).
The replay (GRAPH) notices the decision and carries on; the next move toward the contained host is blocked.

Re-evaluation: after a containment is executed, a small watcher waits until the forecast it was made for is resolved
(Precog does that when the attacker's next move is seen) and writes the result into the action's text, the audit log
and a reeval_result record.
"""
import logging
import threading
import time
from datetime import datetime, timezone

from addons.errors import HookError

log = logging.getLogger("precog.containment")


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ContainmentService:
    def __init__(self, world, hooks, confirm_seconds=60.0, contracts=None, clock=utc_now, reeval_wait=180.0, poll=0.1):
        self.world, self.hooks, self.contracts, self._clock = world, hooks, contracts, clock
        self.confirm_seconds = float(confirm_seconds)
        self.reeval_wait, self.poll = float(reeval_wait), float(poll)
        self._lock = threading.RLock()
        self._counter = 0
        self._pending = {}      # action_id -> {"timer": Timer, "expires": monotonic seconds}
        self._reeval = {}
        self._stopped = threading.Event()

    # ---------- the hook interface ----------
    def propose(self, world, target_host, forecast_id, requested_by):
        graph = self._graph()
        with self._lock:
            self._prune()
            state = self._host_state(graph, target_host)
            if state == "contained":
                raise HookError("already_contained", "%s is already contained." % self._name(graph, target_host), 409)
            for action_id in self._pending:
                existing = self._get(action_id)
                if existing["target_host"] == target_host:
                    return existing  # asking again for the same host just returns the open request
                raise HookError("pending_exists", "Another containment request is waiting for an answer. Confirm or cancel it first.", 409)
            self._counter += 1
            action = {"action_id": "act-%06d" % self._counter, "target_host": target_host, "forecast_id": forecast_id,
                      "requested_by": requested_by, "status": "pending_confirmation", "proposed_at": self._clock(),
                      "confirmed_at": None, "result": None}
            self._validate(action)
            self.world.upsert_action(action)
            timer = threading.Timer(self.confirm_seconds, self._expire, args=(action["action_id"],))
            timer.daemon = True
            self._pending[action["action_id"]] = {"timer": timer}
            timer.start()
            self._audit(action["action_id"], "Containment of %s proposed from the %s." % (self._name(graph, target_host), requested_by))
            return dict(action)

    def confirm(self, world, action_id):
        graph = self._graph()
        with self._lock:
            self._prune()
            action = self._existing(action_id)
            if action["status"] != "pending_confirmation":
                raise HookError("not_pending", "This request is already %s." % action["status"], 409)
            entry = self._pending.pop(action_id, None)
            if entry is not None:
                entry["timer"].cancel()
            if self._host_state(graph, action["target_host"]) == "contained":
                action.update(status="cancelled", result="The host was already contained.")
                self.world.upsert_action(action)
                raise HookError("already_contained", "%s is already contained." % self._name(graph, action["target_host"]), 409)
            graph.set_host_state(action["target_host"], "contained")
            action.update(status="executed", confirmed_at=self._clock(), result="Contained (simulated). Nothing on a real network changed.")
            self._validate(action)
            self.world.upsert_action(action)
            self._audit(action_id, "Containment of %s confirmed and executed (simulated)." % self._name(graph, action["target_host"]))
            self._start_reeval(action_id)
            return dict(action)

    def cancel(self, world, action_id):
        with self._lock:
            self._prune()
            action = self._existing(action_id)
            if action["status"] != "pending_confirmation":
                raise HookError("not_pending", "This request is already %s." % action["status"], 409)
            entry = self._pending.pop(action_id, None)
            if entry is not None:
                entry["timer"].cancel()
            action.update(status="cancelled", result="Cancelled by the analyst.")
            self.world.upsert_action(action)
            self._audit(action_id, "Containment request cancelled by the analyst.")
            return dict(action)

    # ---------- extra (not part of the hook) ----------
    def reeval_results(self):
        with self._lock:
            return [dict(r) for r in self._reeval.values()]

    def shutdown(self):
        self._stopped.set()
        with self._lock:
            for entry in self._pending.values():
                entry["timer"].cancel()
            self._pending.clear()

    # ---------- internals ----------
    def _graph(self):
        graph = self.hooks.get("graph")
        if graph is None:
            raise HookError("not_built", "Containment needs the 'graph' part, which has not been built yet.", 501)
        return graph

    def _host_state(self, graph, host_id):
        try:
            return graph.host_state(host_id)
        except ValueError as exc:
            raise HookError("unknown_host", str(exc), 404)

    def _name(self, graph, host_id):
        for host in graph.snapshot()["hosts"]:
            if host["host_id"] == host_id:
                return host["name"]
        return host_id

    def _get(self, action_id):
        for action in self.world.actions():
            if action["action_id"] == action_id:
                return action
        return None

    def _existing(self, action_id):
        action = self._get(action_id)
        if action is None:
            raise HookError("unknown_action", "There is no containment request '%s'." % action_id, 404)
        return action

    def _prune(self):
        """Forget pending requests that the world no longer has (for example after a replay restart)."""
        known = {a["action_id"] for a in self.world.actions()}
        for action_id in [a for a in self._pending if a not in known]:
            self._pending.pop(action_id)["timer"].cancel()

    def _validate(self, action):
        if self.contracts is not None:
            self.contracts.validate("containment_action", action)

    def _audit(self, ref_id, summary):
        events = self.hooks.get("events")
        if events is not None:
            try:
                events.audit_record("containment", ref_id, summary)
            except Exception:  # an audit problem must never block a containment
                log.exception("Could not write the audit entry")

    def _expire(self, action_id):
        with self._lock:
            if self._pending.pop(action_id, None) is None:
                return
            action = self._get(action_id)
            if action is not None and action["status"] == "pending_confirmation":
                action.update(status="expired", result="Expired without confirmation.")
                self.world.upsert_action(action)
                self._audit(action_id, "Containment request expired without an answer.")

    # ---------- re-evaluation ----------
    def _start_reeval(self, action_id):
        thread = threading.Thread(target=self._reeval_loop, args=(action_id,), name="reeval-" + action_id, daemon=True)
        thread.start()

    def _reeval_loop(self, action_id):
        end = time.monotonic() + self.reeval_wait
        while time.monotonic() < end and not self._stopped.is_set():
            with self._lock:
                action = self._get(action_id)
                if action is None:
                    return
                forecast = self._resolved_forecast(action)
                if forecast is not None:
                    self._write_reeval(action, forecast)
                    return
            time.sleep(self.poll)

    def _resolved_forecast(self, action):
        for forecast in self.world.forecasts():
            if forecast["status"] in ("hit", "miss") and forecast.get("outcome") and (action["forecast_id"] in (None, forecast["forecast_id"])):
                return forecast
        return None

    def _write_reeval(self, action, forecast):
        graph = self.hooks.get("graph")
        outcome = forecast["outcome"]
        where = self._name(graph, outcome["attempted_host"]) if graph is not None else outcome["attempted_host"]
        if forecast["status"] == "hit" and outcome["blocked"]:
            progressed, ended = False, True
            summary = "The attacker tried to reach %s and was blocked. The attack chain ended early." % where
        else:
            progressed, ended = True, False
            summary = "The attacker went on to %s. The attack progressed elsewhere, so Precog forecasts again." % where
        result = {"action_id": action["action_id"], "attack_progressed": progressed, "chain_ended_early": ended, "summary": summary}
        if self.contracts is not None:
            self.contracts.validate("reeval_result", result)
        self._reeval[action["action_id"]] = result
        action["result"] = "Contained (simulated). Re-evaluation: " + summary
        self.world.upsert_action(action)
        self._audit(action["action_id"], "Re-evaluation: " + summary)

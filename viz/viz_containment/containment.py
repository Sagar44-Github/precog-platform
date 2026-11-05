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
        self._generation = 0

    def reset_for_replay(self):
        """Clear replay-local action ids and timers so repeated scenarios stay deterministic."""
        with self._lock:
            self._generation += 1
            for entry in self._pending.values():
                entry["timer"].cancel()
            self._pending.clear()
            self._counter = 0
            self._reeval = {}

    def checkpoint_state(self):
        with self._lock:
            return {"counter": self._counter, "reeval": dict(self._reeval)}

    def restore_checkpoint(self, state):
        with self._lock:
            self._generation += 1
            for entry in self._pending.values():
                entry["timer"].cancel()
            self._pending.clear()
            self._counter = int(state.get("counter", 0))
            self._reeval = dict(state.get("reeval", {}))
            for action in self.world.actions():
                if action.get("status") != "pending_confirmation":
                    continue
                timer = threading.Timer(self.confirm_seconds, self._expire, args=(action["action_id"],))
                timer.daemon = True
                self._pending[action["action_id"]] = {"timer": timer}
                timer.start()

    # ---------- the hook interface ----------
    def propose(self, world, target_host, forecast_id, requested_by):
        return self.propose_many(world, [target_host], forecast_id, requested_by, "host")

    def propose_many(self, world, target_hosts, forecast_id, requested_by, playbook):
        """Propose one confirmed action that affects a bounded, explicit set of simulated hosts."""
        graph = self._graph()
        targets = list(dict.fromkeys(target_hosts or []))
        if not targets:
            raise HookError("no_targets", "This playbook did not resolve to any hosts.", 409)
        with self._lock:
            self._prune()
            previous_states = []
            for host_id in targets:
                state = self._host_state(graph, host_id)
                if state == "contained":
                    raise HookError("already_contained", "%s is already contained." % self._name(graph, host_id), 409)
                previous_states.append({"host_id": host_id, "state": state})
            return self._propose_action(graph, targets, forecast_id, requested_by, "contain", playbook, previous_states)

    def propose_release(self, world, containment_action_id, requested_by):
        """Propose a two-step release for a previously executed containment action."""
        graph = self._graph()
        with self._lock:
            self._prune()
            source = self._existing(containment_action_id)
            if source.get("operation", "contain") != "contain" or source["status"] != "executed":
                raise HookError("not_releasable", "Only an executed containment action can be released.", 409)
            for action in self.world.actions():
                if action.get("operation") == "release" and action.get("related_action_id") == containment_action_id and action["status"] in ("pending_confirmation", "executed"):
                    raise HookError("release_exists", "This containment already has a pending or completed release.", 409)

            targets = source.get("target_hosts") or [source["target_host"]]
            for host_id in targets:
                if self._host_state(graph, host_id) != "contained":
                    raise HookError("not_contained", "%s is no longer contained." % self._name(graph, host_id), 409)
            saved = {entry["host_id"]: entry["state"] for entry in source.get("previous_states", [])}
            path = set(graph.snapshot().get("compromised_path", []))
            previous_states = [
                {"host_id": host_id, "state": saved.get(host_id, "compromised" if host_id in path else "normal")}
                for host_id in targets
            ]
            return self._propose_action(graph, targets, None, requested_by, "release", "release", previous_states, containment_action_id)

    def _propose_action(self, graph, targets, forecast_id, requested_by, operation, playbook, previous_states, related_action_id=None):
        for action_id in self._pending:
            existing = self._get(action_id)
            if existing and existing.get("operation", "contain") == operation and existing.get("target_hosts", [existing["target_host"]]) == targets:
                return existing
            raise HookError("pending_exists", "Another response request is waiting for an answer. Confirm or cancel it first.", 409)
        self._counter += 1
        action = {
            "action_id": "act-%06d" % self._counter,
            "target_host": targets[0],
            "target_hosts": targets,
            "operation": operation,
            "playbook": playbook,
            "related_action_id": related_action_id,
            "previous_states": previous_states,
            "forecast_id": forecast_id,
            "requested_by": requested_by,
            "status": "pending_confirmation",
            "proposed_at": self._clock(),
            "confirmed_at": None,
            "result": None,
        }
        self._validate(action)
        self.world.upsert_action(action)
        timer = threading.Timer(self.confirm_seconds, self._expire, args=(action["action_id"],))
        timer.daemon = True
        self._pending[action["action_id"]] = {"timer": timer}
        timer.start()
        names = ", ".join(self._name(graph, host_id) for host_id in targets)
        verb = "Release of" if operation == "release" else "Containment of"
        self._audit(action["action_id"], "%s %s proposed from the %s playbook by %s." % (verb, names, playbook, requested_by))
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
            targets = action.get("target_hosts") or [action["target_host"]]
            operation = action.get("operation", "contain")
            if operation == "release":
                for host_id in targets:
                    if self._host_state(graph, host_id) != "contained":
                        action.update(status="cancelled", result="Release cancelled because a target was no longer contained.")
                        self.world.upsert_action(action)
                        raise HookError("not_contained", "%s is no longer contained." % self._name(graph, host_id), 409)
                previous = {entry["host_id"]: entry["state"] for entry in action.get("previous_states", [])}
                for host_id in targets:
                    graph.set_host_state(host_id, previous.get(host_id, "normal"))
                result = "Released %d host%s (simulated). Nothing on a real network changed." % (len(targets), "" if len(targets) == 1 else "s")
            else:
                for host_id in targets:
                    if self._host_state(graph, host_id) == "contained":
                        action.update(status="cancelled", result="Containment cancelled because a target was already contained.")
                        self.world.upsert_action(action)
                        raise HookError("already_contained", "%s is already contained." % self._name(graph, host_id), 409)
                for host_id in targets:
                    graph.set_host_state(host_id, "contained")
                result = "Contained %d host%s (simulated). Nothing on a real network changed." % (len(targets), "" if len(targets) == 1 else "s")
            action.update(status="executed", confirmed_at=self._clock(), result=result)
            self._validate(action)
            self.world.upsert_action(action)
            names = ", ".join(self._name(graph, host_id) for host_id in targets)
            verb = "Release of" if operation == "release" else "Containment of"
            self._audit(action_id, "%s %s confirmed and executed (simulated)." % (verb, names))
            if operation == "contain":
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
        generation = self._generation
        thread = threading.Thread(target=self._reeval_loop, args=(action_id, generation), name="reeval-" + action_id, daemon=True)
        thread.start()

    def _reeval_loop(self, action_id, generation=None):
        end = time.monotonic() + self.reeval_wait
        while time.monotonic() < end and not self._stopped.is_set():
            with self._lock:
                if generation is not None and generation != self._generation:
                    return
                action = self._get(action_id)
                if action is None:
                    return
                forecast = self._resolved_forecast(action)
                if forecast is not None:
                    self._write_reeval(action, forecast, generation)
                    return
            time.sleep(self.poll)

    def _resolved_forecast(self, action):
        for forecast in self.world.forecasts():
            if forecast["status"] in ("hit", "miss") and forecast.get("outcome") and (action["forecast_id"] in (None, forecast["forecast_id"])):
                return forecast
        return None

    def _write_reeval(self, action, forecast, generation=None):
        if generation is not None and generation != self._generation:
            return
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

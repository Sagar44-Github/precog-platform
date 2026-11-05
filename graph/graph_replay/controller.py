"""The replay controller: plays a scripted attack through the real pipeline, on a background thread.

For every scenario event it does the work of the pipeline's front half:
  traffic    write packets into NIDS's table, call NIDS's detector at once, hand the labelled packets to DETECT's
             'events' hook, and record the connections in the live graph;
  technique  hand the scripted technique to the 'events' hook; if it says compromise, mark the host compromised and
             tell Precog;
  attempt    ask the live graph whether the move succeeds (a contained target blocks it), record it as an alert,
             tell Precog, and if it succeeded treat the new host as compromised.
An event marked pause_for_decision stops the replay BEFORE it runs, until the analyst decides (a containment is
confirmed, cancelled or expires), someone calls resume(), or the decision time runs out.
"""
import logging
import inspect
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone

from addons.errors import HookError

from .packet_store import PACKET_FIELDS

log = logging.getLogger("precog.replay")

BUSY_STATES = ("running", "paused", "waiting_for_decision")


def _accepts_keyword(method, keyword):
    """Keep optional scenario metadata compatible with older event-hook implementations."""
    try:
        parameters = inspect.signature(method).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(parameter.name == keyword or parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters)


def _now_text():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ReplayController:
    def __init__(self, world, hooks, store, detector, library, hosts, decision_timeout=120.0, settle_seconds=1.5):
        """world: the shared WorldState. hooks: the Hooks object. store: a packet store. detector: a function that labels
        the unlabelled packets (NIDS's run_detection). library: a ScenarioLibrary. hosts: list of host dicts (host_id, address).
        decision_timeout: seconds to wait for the analyst (0 = wait forever). settle_seconds: a short pause after a decision so
        the audience sees the containment before the next move."""
        self.world, self.hooks, self.store, self.detector = world, hooks, store, detector
        self.library = library
        self._address = {h["host_id"]: h["address"] for h in hosts}
        self._name = {h["host_id"]: h.get("name", h["host_id"]) for h in hosts}
        self.decision_timeout = float(decision_timeout)
        self.settle_seconds = float(settle_seconds)
        self._cond = threading.Condition()
        self._thread = None
        self._stop = False
        self._manual_resume = False
        self._session_counter = 0
        self._status = {"state": "idle", "scenario_id": None, "speed": 1.0, "position": 0}
        self._studio = None
        self._scenario = None
        self._breakpoints = set()
        self._step_budget = None
        self._checkpoints = {}
        self.last_error = None
        self.last_decision = None  # why the last wait ended: executed, cancelled, expired, manual or timeout

    # ---------- the hook interface ----------
    def list_scenarios(self):
        return self.library.summaries()

    def status(self):
        with self._cond:
            return dict(self._status)

    def attach_studio(self, studio):
        self._studio = studio

    def set_speed(self, speed):
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0.25 <= float(speed) <= 8:
            raise HookError("bad_request", "Studio speed must be between 0.25x and 8x.", 400)
        with self._cond:
            if self._status["state"] not in BUSY_STATES:
                raise HookError("not_running", "There is no active replay to change speed for.", 409)
            self._status["speed"] = float(speed)
            self._publish_locked()
            self._cond.notify_all()
            return dict(self._status)

    def set_breakpoints(self, sequences):
        if not isinstance(sequences, list) or any(isinstance(value, bool) or not isinstance(value, int) for value in sequences):
            raise HookError("bad_request", "Breakpoints must be a list of event sequence numbers.", 400)
        allowed = {event["seq"] for event in self._scenario["events"]} if self._scenario else set()
        if any(value not in allowed for value in sequences):
            raise HookError("bad_request", "A breakpoint must identify an event in the active scenario.", 400)
        with self._cond:
            self._breakpoints = set(sequences)
            return sorted(self._breakpoints)

    def step(self, timeout=30.0):
        with self._cond:
            if self._status["state"] != "paused":
                raise HookError("not_paused", "Pause the replay before stepping to the next event.", 409)
            target = self._status["position"] + 1
            self._step_budget = 1
            self._status["state"] = "running"
            self._publish_locked()
            self._cond.notify_all()
            deadline = time.monotonic() + timeout
            while True:
                terminal = self._status["state"] in ("waiting_for_decision", "finished", "idle")
                checkpoint_ready = target in self._checkpoints
                if terminal or (self._status["position"] >= target and self._status["state"] != "running" and checkpoint_ready):
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise HookError("step_timeout", "The next replay event did not finish in time.", 504)
                self._cond.wait(min(remaining, 0.1))
            return dict(self._status)

    def step_back(self):
        with self._cond:
            position = self._status["position"]
        return self.seek(max(0, position - 1))

    def seek(self, position):
        if isinstance(position, bool) or not isinstance(position, int) or position < 0:
            raise HookError("bad_request", "Snapshot position must be a non-negative whole number.", 400)
        with self._cond:
            state = self._status["state"]
            scenario = self._scenario
            if state not in BUSY_STATES or scenario is None:
                raise HookError("replay_not_seekable", "Pause or step through an active replay before seeking.", 409)
            if position not in self._checkpoints:
                raise HookError("snapshot_not_found", "There is no recorded snapshot at position %d." % position, 404)
            speed = self._status["speed"]
            thread = self._thread
            self._stop = True
            self._cond.notify_all()
        if thread is not None and thread is not threading.current_thread():
            thread.join(10.0)
            if thread.is_alive():
                raise HookError("replay_busy", "The replay did not stop in time to restore the snapshot.", 409)
        self._restore_runtime_state(deepcopy(self._checkpoints[position]))
        self._checkpoints = {key: value for key, value in self._checkpoints.items() if key <= position}
        if self._studio is not None:
            self._studio.rewind(position)
        previous_offset = scenario["events"][position - 1]["offset_ms"] if position else 0
        with self._cond:
            self._stop = False
            self._manual_resume = False
            self._step_budget = None
            self._status = {"state": "paused", "scenario_id": scenario["scenario_id"], "speed": speed, "position": position}
            self._thread = None
            self._publish_locked()
            self._cond.notify_all()
            self._thread = threading.Thread(target=self._run, args=(scenario, speed, position, previous_offset), name="replay", daemon=True)
            self._thread.start()
            return dict(self._status)

    def start(self, scenario_id, speed=1.0, paused=False):
        scenario = self.library.get(scenario_id)
        if scenario is None:
            raise HookError("unknown_scenario", "There is no scenario called '%s'. Available: %s." % (scenario_id, ", ".join(self.library.ids())), 404)
        if not speed or speed <= 0:
            raise HookError("bad_request", "Speed must be above 0.", 400)
        with self._cond:
            if self._status["state"] in BUSY_STATES:
                raise HookError("replay_busy", "A replay is already running. Use restart to begin again.", 409)
        for needed in ("events", "graph"):
            if not self.hooks.has(needed):
                raise HookError("not_built", "The replay needs the '%s' part, which has not been built yet." % needed, 501)
        return self._begin(scenario, float(speed), initially_paused=paused)

    def pause(self):
        with self._cond:
            if self._status["state"] != "running":
                raise HookError("not_running", "There is nothing running to pause.", 409)
            self._status["state"] = "paused"
            self._publish_locked()
            return dict(self._status)

    def resume(self):
        with self._cond:
            state = self._status["state"]
            if state == "paused":
                self._status["state"] = "running"
                self._step_budget = None
            elif state == "waiting_for_decision":
                self._manual_resume = True
            else:
                raise HookError("not_paused", "The replay is not paused.", 409)
            self._publish_locked()
            self._cond.notify_all()
            return dict(self._status)

    def restart(self):
        with self._cond:
            scenario_id, speed = self._status["scenario_id"], self._status["speed"]
        if scenario_id is None:
            raise HookError("nothing_to_restart", "Start a scenario first.", 409)
        self.stop()
        return self.start(scenario_id, speed)

    # ---------- extra controls (not part of the hook) ----------
    def stop(self, timeout=5.0):
        """Ends a running replay and waits for its thread. Safe to call at any time."""
        with self._cond:
            self._stop = True
            self._cond.notify_all()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        with self._cond:
            self._thread = None
            if self._status["state"] in BUSY_STATES:
                self._status["state"] = "idle"
                self._publish_locked()

    def wait_until_done(self, timeout=30.0):
        """For tests and the demo: blocks until the replay finishes. Returns True if it did."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._cond:
                thread = self._thread
                settled = thread is None or not thread.is_alive()
                if self._status["state"] in ("finished", "idle") and settled:
                    return True
            time.sleep(0.01)
        return False

    # ---------- internals ----------
    def _publish_locked(self):
        self.world.set_replay(dict(self._status))

    def _set(self, **changes):
        with self._cond:
            self._status.update(changes)
            self._publish_locked()
            self._cond.notify_all()

    def _begin(self, scenario, speed, initially_paused=False):
        self._session_counter += 1
        self.world.reset()
        self.store.clear()
        self.hooks.get("events").reset()
        self.hooks.get("graph").reset()
        containment = self.hooks.get("containment")
        if containment is not None and hasattr(containment, "reset_for_replay"):
            containment.reset_for_replay()
        precog = self.hooks.get("precog")
        if precog is not None:
            precog.reset()
        session_id = "ses-%06d" % self._session_counter
        self._session = {"session_id": session_id, "scenario_id": scenario["scenario_id"], "started_at": _now_text(),
                         "ended_at": None, "forecasts": [], "actions": []}
        self.world.set_session(self._session)
        with self._cond:
            self._stop = False
            self._manual_resume = False
            self._step_budget = None
            self.last_error = None
            self.last_decision = None
            self._scenario = deepcopy(scenario)
            self._breakpoints = set()
            self._checkpoints = {}
            self._status = {"state": "paused" if initially_paused else "running", "scenario_id": scenario["scenario_id"], "speed": speed, "position": 0}
            self._publish_locked()
            if self._studio is not None:
                self._studio.begin(scenario, speed)
            self._save_checkpoint(0, None)
            self._thread = threading.Thread(target=self._run, args=(scenario, speed, 0, 0), name="replay", daemon=True)
            self._thread.start()
            return dict(self._status)

    def _capture_runtime_state(self):
        events = self.hooks.get("events")
        delegate = getattr(events, "_delegate", events)
        counter = getattr(delegate, "_counter", None)
        next_event_id = counter.__reduce__()[1][0] if counter is not None else 1
        precog = self.hooks.get("precog")
        graph = self.hooks.get("graph")
        incidents = self.hooks.get("incidents")
        containment = self.hooks.get("containment")
        return {
            "world": self.world.capture_replay_state(),
            "graph": deepcopy(graph.snapshot()) if graph is not None else None,
            "event_next_id": next_event_id,
            "event_skipped_unlabelled": getattr(delegate, "skipped_unlabelled", 0),
            "precog": {key: deepcopy(getattr(precog, key)) for key in ("_counter", "_pending", "_resolved") if precog is not None and hasattr(precog, key)},
            "incidents": incidents.checkpoint_state() if incidents is not None and hasattr(incidents, "checkpoint_state") else None,
            "containment": containment.checkpoint_state() if containment is not None and hasattr(containment, "checkpoint_state") else None,
            "packets": self.store.checkpoint() if hasattr(self.store, "checkpoint") else None,
            "session": deepcopy(getattr(self, "_session", None)),
        }

    def _save_checkpoint(self, position, event):
        checkpoint = self._capture_runtime_state()
        with self._cond:
            self._checkpoints[position] = checkpoint
        if self._studio is not None:
            self._studio.capture(position, event)
        with self._cond:
            self._cond.notify_all()

    def _restore_runtime_state(self, checkpoint):
        self.world.restore_replay_state(checkpoint["world"])
        graph = self.hooks.get("graph")
        if graph is not None and checkpoint.get("graph") is not None and hasattr(graph, "restore"):
            graph.restore(checkpoint["graph"], publish=False)
        events = self.hooks.get("events")
        delegate = getattr(events, "_delegate", events)
        if hasattr(delegate, "_counter"):
            import itertools
            delegate._counter = itertools.count(checkpoint["event_next_id"])
            delegate.skipped_unlabelled = checkpoint.get("event_skipped_unlabelled", 0)
        precog = self.hooks.get("precog")
        if precog is not None:
            for key, value in checkpoint.get("precog", {}).items():
                setattr(precog, key, deepcopy(value))
        incidents = self.hooks.get("incidents")
        if incidents is not None and checkpoint.get("incidents") is not None and hasattr(incidents, "restore_checkpoint"):
            incidents.restore_checkpoint(checkpoint["incidents"])
        containment = self.hooks.get("containment")
        if containment is not None and checkpoint.get("containment") is not None and hasattr(containment, "restore_checkpoint"):
            containment.restore_checkpoint(checkpoint["containment"])
        if checkpoint.get("packets") is not None and hasattr(self.store, "restore_checkpoint"):
            self.store.restore_checkpoint(checkpoint["packets"])
        self._session = deepcopy(checkpoint.get("session"))

    def _sleep(self, seconds):
        """Waits `seconds` of replay time, in small steps, while honouring pause and stop. False means stop."""
        end = time.monotonic() + seconds
        with self._cond:
            while True:
                if self._stop:
                    return False
                if self._status["state"] == "paused":
                    end += 0.05  # time spent paused does not count
                    self._cond.wait(0.05)
                    continue
                remaining = end - time.monotonic()
                if remaining <= 0:
                    return True
                self._cond.wait(min(remaining, 0.05))

    def _wait_for_decision(self):
        """Stops before a decision point. Returns False when the replay was stopped."""
        seen = {a["action_id"]: a["status"] for a in self.world.actions()}
        with self._cond:
            self._manual_resume = False
            self._status["state"] = "waiting_for_decision"
            self._publish_locked()
        started = time.monotonic()
        reason = None
        while reason is None:
            with self._cond:
                if self._stop:
                    return False
                if self._manual_resume:
                    reason = "manual"
                else:
                    for action in self.world.actions():
                        if action["status"] in ("executed", "cancelled", "expired") and seen.get(action["action_id"]) != action["status"]:
                            reason = action["status"]
                            break
                    if reason is None and self.decision_timeout > 0 and time.monotonic() - started >= self.decision_timeout:
                        reason = "timeout"
                if reason is None:
                    self._cond.wait(0.05)
        self.last_decision = reason
        log.info("Decision point finished: %s", reason)
        with self._cond:
            self._status["state"] = "running"
            self._publish_locked()
        return self._sleep(self.settle_seconds) if reason == "executed" else True

    def _run(self, scenario, speed, start_index=0, previous_offset=0):
        events = scenario["events"]
        try:
            for index in range(start_index, len(events)):
                event = events[index]
                with self._cond:
                    current_speed = self._status["speed"]
                    step_mode = self._step_budget is not None
                delay = 0.0 if step_mode else (event["offset_ms"] - previous_offset) / 1000.0 / current_speed
                if not self._sleep(delay):
                    return
                previous_offset = event["offset_ms"]
                if event.get("pause_for_decision") and not self._wait_for_decision():
                    return
                self._handle(event)
                self._set(position=index + 1)
                with self._cond:
                    if self._step_budget is not None:
                        self._step_budget -= 1
                        if self._step_budget <= 0:
                            self._step_budget = None
                            self._status["state"] = "paused"
                            self._publish_locked()
                    if event.get("seq") in self._breakpoints:
                        self._status["state"] = "paused"
                        self._publish_locked()
                    self._cond.notify_all()
                self._save_checkpoint(index + 1, event)
            self._finish()
        except Exception as exc:  # the demo must never hang on a bug: stop and say why
            log.exception("Replay stopped by an error")
            self.last_error = "%s: %s" % (type(exc).__name__, exc)
            with self._cond:
                self._status["state"] = "finished"
                self._publish_locked()
                self._cond.notify_all()
            if self._studio is not None:
                self._studio.finish(self, self.last_error)

    def _finish(self):
        session = dict(self._session, ended_at=_now_text(), forecasts=self.world.forecasts(), actions=self.world.actions())
        self.world.set_session(session)
        self.world.archive_session()
        incidents = self.hooks.get("incidents")
        if incidents is not None and hasattr(incidents, "refresh"):
            incidents.refresh()
        with self._cond:
            self._status["state"] = "finished"
            self._publish_locked()
            self._cond.notify_all()
        self._save_checkpoint(self._status["position"], None)
        if self._studio is not None:
            self._studio.finish(self)

    # ---------- the events ----------
    def _handle(self, event):
        kind = event["kind"]
        if kind == "traffic":
            self._handle_traffic(event)
        elif kind == "technique":
            self._handle_technique(event)
        else:
            self._handle_attempt(event)

    def _handle_traffic(self, event):
        rows, pairs = [], []
        for index, packet in enumerate(event["packets"]):
            for repeat in range(packet.get("repeat", 1)):
                rows.append({"src_ip": self._address[packet["src_host"]], "dst_ip": self._address[packet["dst_host"]],
                             "protocol": packet["protocol"], "src_port": packet.get("src_port", 40000 + index + repeat),
                             "dst_port": packet["dst_port"], "packet_size": packet["size"], "flags": packet.get("flags")})
            pairs.append((packet["src_host"], packet["dst_host"]))
        ids = self.store.insert(rows)
        self.detector()  # NIDS labels every unlabelled packet right now
        events = self.hooks.get("events")
        rows = self.store.fetch(ids)
        if event.get("severity") and _accepts_keyword(events.process_packets, "severity_override"):
            events.process_packets(rows, severity_override=event["severity"])
        else:
            events.process_packets(rows)
        graph = self.hooks.get("graph")
        for source, target in pairs:
            graph.add_connection(source, target)

    def _handle_technique(self, event):
        compromise = bool(event.get("compromise"))
        events = self.hooks.get("events")
        if event.get("severity") and _accepts_keyword(events.process_technique, "severity"):
            events.process_technique(event["host"], event["technique_id"], note=event.get("note"), compromise=compromise, severity=event["severity"])
        else:
            events.process_technique(event["host"], event["technique_id"], note=event.get("note"), compromise=compromise)
        if compromise and self.hooks.get("graph").mark_compromised(event["host"]):
            precog = self.hooks.get("precog")
            if precog is not None:
                precog.on_compromise(event["host"])

    def _handle_attempt(self, event):
        graph, source, target = self.hooks.get("graph"), event["from_host"], event["to_host"]
        outcome = graph.attempt(source, target)
        blocked = outcome["result"] == "blocked"
        shown = self._name.get(target, target)
        words = "The move toward %s was blocked." % shown if blocked else "The move toward %s succeeded." % shown
        note = ((event.get("note") or "").strip().rstrip(".") + ". " if event.get("note") else "") + words
        events = self.hooks.get("events")
        if event.get("severity") and _accepts_keyword(events.process_technique, "severity"):
            events.process_technique(source, event["technique_id"], note=note.rstrip("."), severity=event["severity"])
        else:
            events.process_technique(source, event["technique_id"], note=note.rstrip("."))
        precog = self.hooks.get("precog")
        if precog is not None:
            precog.on_attempt(source, target, blocked)
            if not blocked:
                precog.on_compromise(target)

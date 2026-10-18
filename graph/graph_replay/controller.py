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
import threading
import time
from datetime import datetime, timezone

from addons.errors import HookError

from .packet_store import PACKET_FIELDS

log = logging.getLogger("precog.replay")

BUSY_STATES = ("running", "paused", "waiting_for_decision")


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
        self.last_error = None
        self.last_decision = None  # why the last wait ended: executed, cancelled, expired, manual or timeout

    # ---------- the hook interface ----------
    def list_scenarios(self):
        return self.library.summaries()

    def status(self):
        with self._cond:
            return dict(self._status)

    def start(self, scenario_id, speed=1.0):
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
        return self._begin(scenario, float(speed))

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
                if self._status["state"] in ("finished", "idle"):
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

    def _begin(self, scenario, speed):
        self._session_counter += 1
        self.world.reset()
        self.store.clear()
        self.hooks.get("events").reset()
        self.hooks.get("graph").reset()
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
            self.last_error = None
            self.last_decision = None
            self._status = {"state": "running", "scenario_id": scenario["scenario_id"], "speed": speed, "position": 0}
            self._publish_locked()
            self._thread = threading.Thread(target=self._run, args=(scenario, speed), name="replay", daemon=True)
            self._thread.start()
            return dict(self._status)

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

    def _run(self, scenario, speed):
        events = scenario["events"]
        previous_offset = 0
        try:
            for index, event in enumerate(events):
                if not self._sleep((event["offset_ms"] - previous_offset) / 1000.0 / speed):
                    return
                previous_offset = event["offset_ms"]
                if event.get("pause_for_decision") and not self._wait_for_decision():
                    return
                self._handle(event)
                self._set(position=index + 1)
            self._finish()
        except Exception as exc:  # the demo must never hang on a bug: stop and say why
            log.exception("Replay stopped by an error")
            self.last_error = "%s: %s" % (type(exc).__name__, exc)
            with self._cond:
                self._status["state"] = "finished"
                self._publish_locked()

    def _finish(self):
        session = dict(self._session, ended_at=_now_text(), forecasts=self.world.forecasts(), actions=self.world.actions())
        self.world.set_session(session)
        self.world.archive_session()
        with self._cond:
            self._status["state"] = "finished"
            self._publish_locked()

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
        self.hooks.get("events").process_packets(self.store.fetch(ids))
        graph = self.hooks.get("graph")
        for source, target in pairs:
            graph.add_connection(source, target)

    def _handle_technique(self, event):
        compromise = bool(event.get("compromise"))
        self.hooks.get("events").process_technique(event["host"], event["technique_id"], note=event.get("note"), compromise=compromise)
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
        self.hooks.get("events").process_technique(source, event["technique_id"], note=note.rstrip("."))
        precog = self.hooks.get("precog")
        if precog is not None:
            precog.on_attempt(source, target, blocked)
            if not blocked:
                precog.on_compromise(target)

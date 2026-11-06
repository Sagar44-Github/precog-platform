"""Bounded, read-only playback of installed dataset-pack events.

The pipeline never writes to ``pack.sqlite``. Detector output, simulated state changes,
and analyst containment live only in the current in-memory workspace.
"""
from __future__ import annotations

import copy
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone

from .dataset_packs import DatasetPack
from .errors import ApiError


COUNTERFACTUAL_NOTE = "Simulated what-if on recorded data. Recorded events are immutable."
MAX_BATCH_SIZE = 10_000
MAX_SPEED = 1000.0
MAX_DECISION_POINTS = 50
MAX_NOVELTY_PAIRS = 50_000
MAX_RECENT_BLOCKS = 20


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _event_time(value):
    """Map deterministic pack-relative milliseconds onto a stable UTC timeline."""
    return (datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=int(value or 0))) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty_status(workspace_id="demo-6", state="idle", version=0):
    return {
        "workspace_id": workspace_id,
        "session_id": None,
        "state": state,
        "detector_mode": None,
        "speed": 1.0,
        "batch_size": 1000,
        "processed_events": 0,
        "total_events": 0,
        "alerts": 0,
        "forecasts": 0,
        "incidents": 0,
        "blocked_events": 0,
        "suppressed_events": 0,
        "decision_points": 0,
        "decision_point_limit": 1,
        "decision_point": None,
        "recent_counterfactual": [],
        "simulation_note": COUNTERFACTUAL_NOTE,
        "detector_note": None,
        "error": None,
        "version": version,
    }


class DatasetPipeline:
    """One worker per Flask process, keeping memory and response state bounded."""

    def __init__(self, addon_context, workspaces):
        self.ctx = addon_context
        self.workspaces = workspaces
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._worker = None
        self._stop = False
        self._paused = False
        self._manual_resume = False
        self._revision = 0
        self._run_counter = 0
        self._status = _empty_status(workspaces.active.pack_id)
        self._manifest = None
        self._time_range = (None, None)
        self._speed = 1.0
        self._batch_size = 1000
        self._decision_timeout = 120.0
        self._decision_point_limit = 1
        self._novelty_pairs = set()
        self._novelty_cap_hit = False
        self._warmup_events = 0
        self._session_id = None

    @property
    def revision(self):
        with self._lock:
            return self._revision

    def _publish_locked(self, **updates):
        self._status.update(updates)
        self._revision += 1
        self._status["version"] = self._revision
        if self.ctx.contracts is not None:
            self.ctx.contracts.validate("dataset_pipeline_status", self._status)
        self._condition.notify_all()

    def status(self):
        with self._lock:
            if self._status["workspace_id"] != self.workspaces.active.pack_id and self._status["state"] in ("idle", "finished", "stopped", "error"):
                return _empty_status(self.workspaces.active.pack_id, version=self._revision)
            return copy.deepcopy(self._status)

    def start(self, *, speed=1.0, batch_size=1000, detector_mode=None, start_t=None, end_t=None,
              decision_point_limit=1):
        context = self.workspaces.active
        manifest = context.manifest
        if context.pack_id == "demo-6":
            raise ApiError("pipeline_not_applicable", "demo-6 keeps its original NIDS replay. Use the existing replay controls.", 409)
        if not isinstance(speed, (int, float)) or isinstance(speed, bool) or not 0.25 <= float(speed) <= MAX_SPEED:
            raise ApiError("bad_request", "speed must be between 0.25 and 1000.", 400)
        if not isinstance(batch_size, int) or isinstance(batch_size, bool) or not 1 <= batch_size <= MAX_BATCH_SIZE:
            raise ApiError("bad_request", "batch_size must be a whole number between 1 and 10000.", 400)
        if not isinstance(decision_point_limit, int) or isinstance(decision_point_limit, bool) or not 0 <= decision_point_limit <= MAX_DECISION_POINTS:
            raise ApiError("bad_request", "decision_point_limit must be between 0 and 50.", 400)
        for name, value in (("start_t", start_t), ("end_t", end_t)):
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise ApiError("bad_request", "%s must be a non-negative whole number." % name, 400)
        if start_t is not None and end_t is not None and start_t > end_t:
            raise ApiError("bad_request", "start_t must not be later than end_t.", 400)
        allowed = set(manifest.get("detector_options", []))
        if detector_mode is not None and not isinstance(detector_mode, str):
            raise ApiError("bad_request", "detector_mode must be a text value.", 400)
        mode = context.detector_mode if detector_mode is None else detector_mode
        if mode not in allowed:
            raise ApiError("unsupported_detector", "Choose a detector mode declared by this workspace: %s." % ", ".join(sorted(allowed)), 400)
        if mode == "nids-live":
            raise ApiError("unsupported_detector", "NIDS live detection is reserved for demo-6 and its original replay pipeline.", 409)
        if mode == "model":
            raise ApiError("unsupported_detector", "This pack does not include a held-out, pack-specific traffic detector model.", 409)

        with self._condition:
            if self._worker is not None and self._worker.is_alive():
                raise ApiError("pipeline_busy", "A dataset stream is already active. Stop it before starting another.", 409)
            self._run_counter += 1
            # Replay-local ids intentionally reset so the same pack and settings reproduce
            # event, forecast and incident identifiers on every run.
            session_id = "ses-000001"
            scenario_id = "dataset-stream-%s" % context.pack_id
            self._stop = False
            self._paused = False
            self._manual_resume = False
            self._manifest = copy.deepcopy(manifest)
            self._time_range = (start_t, end_t)
            self._speed = float(speed)
            self._batch_size = batch_size
            self._decision_point_limit = decision_point_limit
            replay = self.ctx.hooks.get("replay")
            self._decision_timeout = max(0.0, float(getattr(replay, "decision_timeout", 120.0)))
            self._session_id = session_id
            self._novelty_pairs.clear()
            self._novelty_cap_hit = False
            self._warmup_events = 0

            # Large graph copies in the legacy time-travel ring are the dominant memory
            # multiplier. Preserve demo-6's 200 entries and shrink large workspaces
            # before reset publishes any new 300-host snapshots.
            if len(context.hosts) >= 100:
                self.ctx.world._history = deque(self.ctx.world._history, maxlen=32)
            self.ctx.world.reset()
            events = self.ctx.hooks.require("events")
            events.reset()
            graph = self.ctx.hooks.require("graph")
            graph.reset()
            containment = self.ctx.hooks.get("containment")
            if containment is not None and hasattr(containment, "reset_for_replay"):
                containment.reset_for_replay()
            precog = self.ctx.hooks.get("precog")
            if precog is not None:
                precog.reset()
            started = _utc_now()
            self.ctx.world.set_session({"session_id": session_id, "scenario_id": scenario_id,
                                        "started_at": started, "ended_at": None,
                                        "forecasts": [], "actions": []})
            self.ctx.world.set_replay({"state": "running", "scenario_id": scenario_id,
                                       "speed": self._speed, "position": 0})
            pack = DatasetPack(context.pack_path, manifest)
            total = self._count_events(pack, start_t, end_t)
            detector_note = self._detector_note(mode)
            initial_status = _empty_status(context.pack_id, "running", self._revision)
            initial_status.update({"session_id": session_id, "detector_mode": mode, "speed": self._speed,
                                   "batch_size": batch_size, "total_events": total,
                                   "decision_point_limit": decision_point_limit,
                                   "detector_note": detector_note})
            self._publish_locked(**initial_status)
            self._worker = threading.Thread(target=self._run, args=(pack,), name="dataset-pipeline", daemon=True)
            self._worker.start()
            return copy.deepcopy(self._status)

    @staticmethod
    def _count_events(pack, start_t, end_t):
        import sqlite3
        uri = "file:%s?mode=ro" % (pack.path / "pack.sqlite").as_posix()
        conn = sqlite3.connect(uri, uri=True)
        try:
            clauses, args = [], []
            if start_t is not None:
                clauses.append("t >= ?"); args.append(start_t)
            if end_t is not None:
                clauses.append("t <= ?"); args.append(end_t)
            query = "SELECT COUNT(*) FROM events" + (" WHERE " + " AND ".join(clauses) if clauses else "")
            return int(conn.execute(query, args).fetchone()[0])
        finally:
            conn.close()

    @staticmethod
    def _detector_note(mode):
        if mode == "labels":
            return "Dataset labels are replayed directly. This is ground-truth playback, not prospective detection."
        return "Graph novelty is a simple simulation estimate: first-seen source-destination pairs after a 20% warm-up window are alerts."

    def pause(self):
        with self._condition:
            if self._status["state"] != "running":
                raise ApiError("pipeline_not_running", "Only a running dataset stream can be paused.", 409)
            self._paused = True
            self.ctx.world.set_replay({"state": "paused", "scenario_id": "dataset-stream-%s" % self.workspaces.active.pack_id,
                                       "speed": self._speed, "position": self._status["processed_events"]})
            self._publish_locked(state="paused")
            return copy.deepcopy(self._status)

    def resume(self):
        with self._condition:
            if self._status["state"] == "paused":
                self._paused = False
                self.ctx.world.set_replay({"state": "running", "scenario_id": "dataset-stream-%s" % self.workspaces.active.pack_id,
                                           "speed": self._speed, "position": self._status["processed_events"]})
                self._publish_locked(state="running")
            elif self._status["state"] == "waiting_for_decision":
                self._manual_resume = True
                self._condition.notify_all()
                self._publish_locked()
            else:
                raise ApiError("pipeline_not_paused", "The dataset stream is not paused or waiting for a decision.", 409)
            return copy.deepcopy(self._status)

    def stop(self):
        with self._condition:
            worker = self._worker
            if worker is None or not worker.is_alive():
                return self.status()
            self._stop = True
            self._condition.notify_all()
        if worker is not threading.current_thread():
            worker.join(5.0)
        with self._condition:
            if worker.is_alive():
                raise ApiError("pipeline_busy", "The dataset stream did not stop within 5 seconds.", 409)
            if self._status["state"] not in ("finished", "stopped", "error"):
                self._publish_locked(state="stopped", decision_point=None)
            return copy.deepcopy(self._status)

    def _await_active(self, delay=0.0):
        deadline = time.monotonic() + max(0.0, delay)
        with self._condition:
            while True:
                if self._stop:
                    return False
                if self._paused:
                    self._condition.wait(0.05)
                    deadline += 0.05
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return True
                self._condition.wait(min(remaining, 0.05))

    def _should_pause(self, row):
        with self._lock:
            if self._status["decision_points"] >= self._decision_point_limit or self._decision_point_limit == 0:
                return None
        if row.get("kind") != "attempt" and self._semantics(row) not in ("lateral-movement", "command-and-control"):
            return None
        engine = self.ctx.hooks.get("precog")
        forecast = self.ctx.world.current_forecast()
        if engine is None or forecast is None:
            return None
        policy = self._manifest.get("default_decision_policy", {})
        mode = policy.get("mode", "never")
        if mode == "never":
            return None
        explanation = engine.explanation_context(forecast["forecast_id"]) or {}
        candidates = explanation.get("candidate_ids", [])
        top_probability = float(forecast.get("targets", [{}])[0].get("confidence", 0.0))
        if mode == "scenario-pauses":
            eligible = True
        else:
            eligible = (top_probability >= float(policy.get("threshold", 1.0)) or
                        len(candidates) >= int(policy.get("minimum_candidates", 1)))
        if not eligible:
            return None
        reason = ("Scenario decision point before recorded lateral movement." if mode == "scenario-pauses"
                  else "Automatic policy: forecast confidence or candidate count reached its threshold.")
        return {"event_id": row.get("event_id"), "from_host": row.get("src"),
                "to_host": row.get("dst"), "reason": reason}

    def _wait_for_decision(self, decision):
        with self._condition:
            self._status["decision_points"] += 1
            self._publish_locked(state="waiting_for_decision", decision_point=decision)
            self.ctx.world.set_replay({"state": "waiting_for_decision",
                                       "scenario_id": "dataset-stream-%s" % self.workspaces.active.pack_id,
                                       "speed": self._speed, "position": self._status["processed_events"]})
        started = time.monotonic()
        reason = None
        while reason is None:
            if not self._await_active(0):
                return False
            if self._manual_resume:
                reason = "manual"
            else:
                terminal = {"executed", "cancelled", "expired"}
                if any(action.get("status") in terminal for action in self.ctx.world.actions()):
                    reason = "action"
                elif self._decision_timeout <= 0 or time.monotonic() - started >= self._decision_timeout:
                    reason = "timeout"
                else:
                    with self._condition:
                        self._condition.wait(0.05)
        with self._condition:
            self._manual_resume = False
            self._status["decision_point"] = None
            self._publish_locked(state="running")
            self.ctx.world.set_replay({"state": "running", "scenario_id": "dataset-stream-%s" % self.workspaces.active.pack_id,
                                       "speed": self._speed, "position": self._status["processed_events"]})
        return True

    def _warmup_count(self, total):
        return max(1, int(total * 0.2)) if total else 0

    @staticmethod
    def _safe_summary(value):
        if not isinstance(value, str):
            return "recorded event"
        text = "".join(char for char in value if ord(char) >= 32 and ord(char) != 127).strip()
        return text[:160] or "recorded event"

    def _mode_detects(self, row, mode, processed_before):
        if mode == "labels":
            label = row.get("label")
            return bool(label and str(label).casefold() not in ("benign", "normal", "0") and row.get("severity") in ("HIGH", "MEDIUM", "LOW")), "dataset_labels"
        if mode != "graph-novelty":
            return False, "graph_novelty"
        source, target = row.get("src"), row.get("dst")
        if not source or not target or source == target:
            return False, "graph_novelty"
        pair = (source, target)
        if processed_before < self._warmup_events:
            if len(self._novelty_pairs) < MAX_NOVELTY_PAIRS:
                self._novelty_pairs.add(pair)
            else:
                self._novelty_cap_hit = True
            return False, "graph_novelty"
        if pair in self._novelty_pairs:
            return False, "graph_novelty"
        if len(self._novelty_pairs) < MAX_NOVELTY_PAIRS:
            self._novelty_pairs.add(pair)
        else:
            self._novelty_cap_hit = True
            return False, "graph_novelty"
        return True, "graph_novelty"

    def _semantics(self, row):
        attack_class = row.get("attack_class")
        return next((item.get("compromise_semantics") for item in self._manifest.get("attack_classes", [])
                     if item.get("id") == attack_class), None)

    def _technique(self, row):
        attack_class = row.get("attack_class")
        mapping = next((item for item in self._manifest.get("technique_mapping", [])
                        if item.get("attack_class") == attack_class), None)
        candidates = mapping.get("technique_ids", []) if mapping else []
        events = self.ctx.hooks.get("events")
        delegate = getattr(events, "_delegate", events)
        table = getattr(delegate, "techniques", None)
        return next((item for item in candidates if table is not None and table.get(item) is not None), None)

    def _emit(self, row, source, compromised=False, blocked=False):
        events = self.ctx.hooks.require("events")
        event = {
            "host": row.get("dst") or row.get("src"),
            "timestamp": _event_time(row.get("t")),
            "packet_id": row.get("event_id") if isinstance(row.get("event_id"), int) else None,
            "label": row.get("label"), "attack_class": row.get("attack_class"),
            "source": source, "severity": row.get("severity") or "LOW",
            "technique_id": self._technique(row),
            "blocked": bool(blocked),
        }
        return events.process_dataset_event(event, compromised=compromised)

    def _process_row(self, row, processed_before):
        graph = self.ctx.hooks.require("graph")
        precog = self.ctx.hooks.get("precog")
        source, target = row.get("src"), row.get("dst")
        kind = row.get("kind")
        semantics = self._semantics(row)
        is_attempt = kind == "attempt" or (semantics in ("lateral-movement", "command-and-control") and source and target)
        if source and graph.host_state(source) == "contained":
            if is_attempt and precog is not None and target:
                precog.on_attempt(source, target, blocked=True)
            with self._condition:
                self._status["suppressed_events"] += 1
                self._condition.notify_all()
            return 0

        target_contained = bool(target and graph.host_state(target) == "contained")
        mode = self._status["detector_mode"]
        detected, detection_source = self._mode_detects(row, mode, processed_before)
        compromise_semantics = {"access-attempt", "command-and-control", "lateral-movement"}
        can_compromise = (self._manifest.get("capabilities", {}).get("host_compromise") != "none" and
                          semantics in compromise_semantics and kind in ("attempt", "technique", "traffic"))
        if target_contained:
            if is_attempt and precog is not None and source and target:
                precog.on_attempt(source, target, blocked=True)
            if detected or can_compromise:
                self._emit(row, "recorded_counterfactual", compromised=False, blocked=True)
            sample = {"event_id": row.get("event_id"), "source_host": source, "target_host": target,
                      "result": "blocked", "label": self._safe_summary(row.get("label"))}
            with self._condition:
                self._status["blocked_events"] += 1
                self._status["recent_counterfactual"].append(sample)
                del self._status["recent_counterfactual"][:-MAX_RECENT_BLOCKS]
                self._condition.notify_all()
            return 1

        emitted = 0
        if detected:
            self._emit(row, detection_source, compromised=can_compromise)
            emitted += 1
        if kind == "traffic" and mode == "graph-novelty" and source and target:
            # The graph overlay tracks detected and attack-path edges, not every benign
            # background connection. This keeps full-state polling bounded at 300 hosts.
            if detected:
                graph.add_connection(source, target)
        if can_compromise and target:
            if is_attempt and source:
                result = graph.attempt(source, target)
                blocked = result.get("result") == "blocked"
                if precog is not None:
                    precog.on_attempt(source, target, blocked=blocked)
                if blocked:
                    with self._condition:
                        self._status["blocked_events"] += 1
                    return emitted
                if result.get("result") == "success" and precog is not None:
                    precog.on_compromise(target)
            elif graph.mark_compromised(target) and precog is not None:
                precog.on_compromise(target)
        return emitted

    def _refresh_counts_locked(self):
        self._status["forecasts"] = len(self.ctx.world.forecasts(include_archived=False))
        incidents = self.ctx.hooks.get("incidents")
        service = getattr(incidents, "service", None)
        if service is not None:
            self._status["incidents"] = len(service.snapshot_records())

    def _run(self, pack):
        previous_t = None
        batch = self._batch_size
        start_t, end_t = self._time_range
        try:
            total = self._status["total_events"]
            self._warmup_events = self._warmup_count(total)
            for rows in pack.iter_events(start_t=start_t, end_t=end_t, batch_size=batch):
                batch_delay = 0.0
                for row in rows:
                    event_t = int(row.get("t") or 0)
                    if not self._await_active(0):
                        raise InterruptedError("Dataset stream stopped by an analyst or workspace switch.")
                    if previous_t is not None and event_t >= previous_t:
                        # Accumulate elapsed replay time and wait once per bounded
                        # batch. Per-event sub-millisecond waits are rounded up by
                        # Windows schedulers and would turn 1000x playback into 60 Hz.
                        batch_delay += (event_t - previous_t) / 1000.0 / self._speed
                    decision = self._should_pause(row)
                    if decision is not None and not self._wait_for_decision(decision):
                        raise InterruptedError("Dataset stream stopped while waiting for a decision.")
                    emitted = self._process_row(row, self._status["processed_events"])
                    previous_t = event_t
                    with self._condition:
                        self._status["processed_events"] += 1
                        self._status["alerts"] += emitted
                    # Batch-level feed updates provide back-pressure to clients and avoid
                    # publishing 100,000 status writes for a 100k-event pack.
                if batch_delay and not self._await_active(batch_delay):
                    raise InterruptedError("Dataset stream stopped during playback pacing.")
                with self._condition:
                    self._refresh_counts_locked()
                    state = self._status["state"]
                    self._publish_locked()
            current = self.ctx.world.session() or {}
            self.ctx.world.set_session(dict(current, ended_at=_utc_now(), forecasts=self.ctx.world.forecasts(),
                                             actions=self.ctx.world.actions()))
            self.ctx.world.archive_session()
            incidents = self.ctx.hooks.get("incidents")
            if incidents is not None and hasattr(incidents, "refresh"):
                incidents.refresh()
            with self._condition:
                self._refresh_counts_locked()
                self._publish_locked(state="finished", decision_point=None)
            self.ctx.world.set_replay({"state": "finished", "scenario_id": "dataset-stream-%s" % pack.manifest["id"],
                                       "speed": self._speed, "position": self._status["processed_events"]})
        except InterruptedError:
            current = self.ctx.world.session() or {}
            if current.get("session_id") == self._session_id and current.get("ended_at") is None:
                self.ctx.world.set_session(dict(current, ended_at=_utc_now(), forecasts=self.ctx.world.forecasts(),
                                                 actions=self.ctx.world.actions()))
                self.ctx.world.archive_session()
            if self.workspaces.active.pack_id == pack.manifest["id"]:
                with self._condition:
                    self._publish_locked(state="stopped", decision_point=None)
                self.ctx.world.set_replay({"state": "finished", "scenario_id": "dataset-stream-%s" % pack.manifest["id"],
                                           "speed": self._speed, "position": self._status["processed_events"]})
        except Exception as exc:
            import logging
            logging.getLogger("precog.dataset_pipeline").exception("Dataset stream stopped after an error")
            with self._condition:
                self._publish_locked(state="error", error="%s: %s" % (type(exc).__name__, str(exc)[:300]), decision_point=None)
            if self.workspaces.active.pack_id == pack.manifest["id"]:
                self.ctx.world.set_replay({"state": "finished", "scenario_id": "dataset-stream-%s" % pack.manifest["id"],
                                           "speed": self._speed, "position": self._status["processed_events"]})

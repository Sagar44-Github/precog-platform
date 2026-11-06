"""Per-process dataset context and safe activation of already installed packs.

Pack installation is deliberately local and identifier-based. D2 does not accept an
arbitrary filesystem path, download a remote archive, or change the web runtime's data.
"""
from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from .dataset_packs import PackError, PackStore


@dataclass
class DatasetContext:
    pack_id: str
    pack_path: Path
    manifest: dict
    topology: dict
    hosts: list[dict]
    scenarios: list[dict]
    training_routes: list[dict]
    model: dict
    evaluation: dict
    detector_mode: str
    decision_policy: dict
    display_hints: dict


class WorkspaceManager:
    def __init__(self, addon_context, store=None):
        self.ctx = addon_context
        self.root = Path(addon_context.config.repo_root)
        self.data_root = Path(addon_context.config.data_dir) / "workspaces"
        self.store = store or PackStore(self.root / "packs", addon_context.config.contracts_dir)
        self._lock = threading.RLock()
        self.version = 1
        self._buckets = {}
        self.active = self._context(self.store.open("demo-6"))
        self._configure(self.active, initial=True)

    @staticmethod
    def _context(pack):
        path = pack.path
        topology = json.loads((path / "topology.json").read_text(encoding="utf-8"))
        scenarios = [json.loads(item.read_text(encoding="utf-8")) for item in sorted((path / "scenarios").glob("*.json"))]
        routes = [json.loads(line) for line in (path / "routes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        model = json.loads((path / "model.json").read_text(encoding="utf-8"))
        evaluation = json.loads((path / "evaluation.json").read_text(encoding="utf-8"))
        manifest = pack.manifest
        return DatasetContext(pack.manifest["id"], path, manifest, topology, copy.deepcopy(topology["hosts"]), scenarios,
                              routes, model, evaluation, manifest["detector_options"][0],
                              copy.deepcopy(manifest["default_decision_policy"]), copy.deepcopy(manifest["display_hints"]))

    def _workspace_data(self, pack_id):
        if pack_id == "demo-6":
            # Keep the historical demo paths intact for existing local sessions.
            return Path(self.ctx.config.data_dir)
        return self.data_root / pack_id

    def _atomic_json(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=".workspace-", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def _save_bucket(self):
        if self.active is None:
            return
        world = self.ctx.world
        incidents = self.ctx.hooks.get("incidents")
        incident_service = getattr(incidents, "service", None)
        incident_state = incident_service.checkpoint_state() if incident_service is not None else None
        if incident_state is not None:
            incident_state["_seen_alerts"] = sorted(incident_state.get("_seen_alerts", []))
        bucket = {
            "sessions": copy.deepcopy(world._sessions),
            "snapshots": world.time_travel(limit=200),
            "incident_state": incident_state,
        }
        self._buckets[self.active.pack_id] = bucket
        self._atomic_json(self.data_root / self.active.pack_id / "state.json", bucket)

    def _load_bucket(self, pack_id):
        cached = self._buckets.get(pack_id)
        path = self.data_root / pack_id / "state.json"
        if cached is None and path.is_file():
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                cached = None
        return cached or {"sessions": [], "snapshots": [], "incident_state": None}

    def _configure(self, context, initial=False):
        from graph_net.live_graph import LiveGraph
        from graph_net.topology import Topology
        from graph_replay.scenario import ScenarioLibrary
        from detect_events.hosts import HostMap
        from precog_engine.model import NodeModel

        topology_data = context.topology
        legacy_topology = {
            "feasible_connections": {},
            "assets": topology_data.get("assets", {}),
        }
        for host in context.hosts:
            legacy_topology["feasible_connections"][host["host_id"]] = []
        for edge in topology_data.get("feasible_edges", []):
            legacy_topology["feasible_connections"].setdefault(edge["src"], []).append(edge["dst"])
        topology = Topology(context.hosts, legacy_topology)
        graph = LiveGraph(topology, world=self.ctx.world)
        self.ctx.hooks.register("graph", graph)
        self.ctx.dataset_context = context
        base = self.ctx.hooks.get("events")
        delegate = getattr(base, "_delegate", base)
        if delegate is not None and hasattr(delegate, "hosts"):
            delegate.hosts = HostMap(context.hosts)
            if getattr(delegate, "audit", None) is not None:
                delegate.audit.path = self._workspace_data(context.pack_id) / "audit" / "audit.jsonl"
        incidents_hook = self.ctx.hooks.get("incidents")
        incident_service = getattr(incidents_hook, "service", None)
        if incident_service is not None and incident_service.audit_log is not None:
            incident_service.audit_log.path = self._workspace_data(context.pack_id) / "audit" / "incidents.json"
        replay = self.ctx.hooks.get("replay")
        if replay is not None:
            custom_dir = self._workspace_data(context.pack_id) / "scenarios"
            replay.library = ScenarioLibrary(context.pack_path / "scenarios", known_hosts={host["host_id"] for host in context.hosts})
            replay._address = {h["host_id"]: h.get("address", "") for h in context.hosts}
            replay._name = {h["host_id"]: h.get("name", h["host_id"]) for h in context.hosts}
        engine = self.ctx.hooks.get("precog")
        if engine is not None:
            engine.model = NodeModel.from_dict(context.model)
            engine.reset()
            engine.sessions_dir = self._workspace_data(context.pack_id) / "sessions"
        studio = self.ctx.hooks.get("studio")
        if studio is not None:
            studio.topology = topology
            studio.known_hosts = set(topology.host_ids())
            studio.data_dir = self._workspace_data(context.pack_id)
            studio.scenarios_dir = studio.data_dir / "scenarios"
            studio.runs_dir = studio.data_dir / "runs"
            studio._runs = {}
            studio._revision = 0
            studio._active = None
            studio._snapshots.clear()
            studio._load_user_scenarios()
            studio._load_runs()
        governance = self.ctx.flask_app.extensions.get("precog_governance")
        if governance is not None:
            governance.path = self._workspace_data(context.pack_id) / "governance" / "records.json"
            governance._approvals, governance._releases, governance._counter, governance.revision = [], [], 0, 0
            governance._load()
        lab = self.ctx.flask_app.extensions.get("precog_lab")
        if lab is not None:
            lab.data_dir = self._workspace_data(context.pack_id) / "analytics"
            lab._cache.clear()
            lab._experiments = []
            lab._load_experiments()
        if not initial:
            self.ctx.world.reset()
            graph.reset()
            containment = self.ctx.hooks.get("containment")
            if containment is not None and hasattr(containment, "reset_for_replay"):
                containment.reset_for_replay()
            incidents = self.ctx.hooks.get("incidents")
            service = getattr(incidents, "service", None)
            if service is not None:
                saved = self._load_bucket(context.pack_id).get("incident_state")
                if saved:
                    saved["_seen_alerts"] = set(saved.get("_seen_alerts", []))
                    service.restore_checkpoint(saved)
                else:
                    service.reset()
            bucket = self._load_bucket(context.pack_id)
            from .world_state import MAX_TIME_TRAVEL_SNAPSHOTS
            self.ctx.world._history = deque(bucket.get("snapshots", [])[-MAX_TIME_TRAVEL_SNAPSHOTS:], maxlen=MAX_TIME_TRAVEL_SNAPSHOTS)
        self.ctx.world.set_graph(graph.snapshot())

    def activate(self, pack_id):
        with self._lock:
            pack = self.store.open(pack_id)
            replay = self.ctx.hooks.get("replay")
            if replay is not None and replay.status().get("state") in ("running", "paused", "waiting_for_decision"):
                replay.stop()
            self._save_bucket()
            events = self.ctx.hooks.get("events")
            delegate = getattr(events, "_delegate", events)
            if delegate is not None and hasattr(delegate, "reset"):
                try:
                    delegate.reset(clear_audit=False)
                except TypeError:
                    delegate.reset()
            incident_service = getattr(self.ctx.hooks.get("incidents"), "service", None)
            if incident_service is not None:
                incident_service.reset()
            containment = self.ctx.hooks.get("containment")
            if containment is not None and hasattr(containment, "reset_for_replay"):
                containment.reset_for_replay()
            context = self._context(pack)
            self.active = context
            self.version += 1
            self._configure(context)
            sessions = self._load_bucket(pack_id).get("sessions", [])[-20:]
            self.ctx.world._sessions = sessions
            replay = self.ctx.hooks.get("replay")
            if replay is not None:
                numbers = [int(item["session_id"].rsplit("-", 1)[-1]) for item in sessions
                           if isinstance(item.get("session_id"), str) and item["session_id"].startswith("ses-")
                           and item["session_id"].rsplit("-", 1)[-1].isdigit()]
                replay._session_counter = max(numbers, default=0)
            return self.summary(context, active=True)

    def summary(self, context, active=False):
        manifest = context.manifest
        return {"id": context.pack_id, "name": manifest["name"], "version": manifest["version"],
                "status": "active" if active else "available", "counts": manifest["counts"],
                "capabilities": manifest["capabilities"], "redistribution": manifest["redistribution"]}

    def list_workspaces(self):
        summaries = []
        installed = {item["id"]: item for item in self.store.list_packs()}
        try:
            registry = json.loads((self.root / "datasets" / "registry.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            registry = {"workspaces": []}
        for item in registry.get("workspaces", []):
            if item["id"] in installed:
                pack = self.store.open(item["id"])
                summaries.append(self.summary(self._context(pack), active=item["id"] == self.active.pack_id))
            else:
                summaries.append({"id": item["id"], "name": item["name"], "version": "0.0.0", "status": "unavailable",
                                  "counts": item.get("counts", {"hosts": 0, "edges": 0, "events": 0, "labelled_events": 0, "routes": 0, "time_span_ms": 0}),
                                  "capabilities": item["capabilities"], "redistribution": item["redistribution_status"]})
        registry_ids = {item["id"] for item in registry.get("workspaces", [])}
        for pack_id in sorted(set(installed) - registry_ids):
            pack = self.store.open(pack_id)
            summaries.append(self.summary(self._context(pack), active=pack_id == self.active.pack_id))
        return summaries

    def card(self, pack_id):
        try:
            pack = self.store.open(pack_id)
        except PackError:
            registry_path = self.root / "datasets" / "registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            item = next((entry for entry in registry.get("workspaces", []) if entry.get("id") == pack_id), None)
            if item is None:
                raise PackError("Workspace is not registered or installed")
            card_path = self.root / item["dataset_card"]
            if card_path.parent.resolve() != (self.root / "docs" / "datasets").resolve() or not card_path.is_file():
                raise PackError("Registered dataset card is unavailable")
            card_text = card_path.read_text(encoding="utf-8")
            return {"id": pack_id, "name": item["name"], "summary": card_text[:2000],
                    "source": {"id": pack_id, "name": item["name"], "citation": item.get("citation") or "See dataset card.",
                               "licence": item.get("licence_summary", "See dataset card."),
                               "terms_summary": item.get("redistribution_status", "See dataset card.")},
                    "redistribution": item["redistribution_status"], "capabilities": item["capabilities"],
                    "limitations": ["Pack is not installed; card claims do not imply that data or a builder is available locally."]}
        ctx = self._context(pack)
        card_text = (pack.path / "card.md").read_text(encoding="utf-8")
        return {"id": pack_id, "name": pack.manifest["name"], "summary": card_text[:2000],
                "source": pack.manifest["source"], "redistribution": pack.manifest["redistribution"],
                "capabilities": pack.manifest["capabilities"], "limitations": ctx.evaluation.get("limitations", [])}

    def feed_version(self):
        return self.version

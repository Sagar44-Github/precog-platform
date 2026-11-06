"""Read-only network digital-twin data and projections."""
import networkx as nx
from collections import defaultdict


MAX_PATHS = 25
MAX_HOST_HISTORY = 500
MAX_TOPOLOGY_PAGE = 200
MAX_TOPOLOGY_PAGE_EDGES = 1000


class NetworkTwin:
    def __init__(self, ctx):
        self.ctx = ctx
        self.world = ctx.world
        self.hooks = ctx.hooks

    @property
    def graph(self):
        return self.hooks.require("graph")

    @property
    def topology(self):
        return self.graph.topology

    def _host(self, host_id):
        host = self.topology.hosts.get(host_id)
        if host is None:
            raise KeyError(host_id)
        assets = self.topology._assets.get(host_id, {})
        state = self.graph.host_state(host_id)
        weaknesses = [{
            "weakness_id": item["id"], "service": item["service"], "cvss": float(item["cvss"]),
            "description": item.get("description", "Simulated demo weakness"), "simulated": True,
        } for item in assets.get("vulns", [])]
        connections = self.topology.connections(host_id)
        incoming = self.topology.incoming_count(host_id)
        return {
            "host_id": host_id, "name": host["name"], "zone": host["zone"],
            "address": host.get("address", ""), "role": host.get("role", "Demo asset"),
            "state": state, "services": list(assets.get("services", [])),
            "weaknesses": weaknesses, "criticality": float(assets.get("criticality", 0.5)),
            "risk": round(self.topology.risk(host_id), 2), "exposure": len(connections) + incoming,
        }

    def topology_view(self):
        live = self.graph.snapshot()
        observed = live.get("edges", [])
        hosts = [self._host(host_id) for host_id in self.topology.host_ids()]
        zones = {}
        for host in hosts:
            zones.setdefault(host["zone"], []).append(host["host_id"])
        feasible = [{
            "from_host": source, "to_host": target,
            "likelihood": round(float(self.topology.edge_probability(source, target)), 4),
        } for source, target in self.topology.feasible_edges()]
        return {
            "hosts": hosts,
            "zones": [{"zone": zone, "host_ids": ids} for zone, ids in sorted(zones.items())],
            "feasible_edges": feasible,
            "observed_edges": [{
                "from_host": item["from_host"], "to_host": item["to_host"],
                "first_seen": item.get("first_seen"),
            } for item in observed],
            "compromised_path": list(live.get("compromised_path", [])),
            "engine": self.topology.engine,
            "risk_basis": "attackgraph" if self.topology.engine == "attackgraph" else "networkx fallback with simulated CVSS and asset criticality",
            "basis": "Risk and edge likelihoods are simulated model estimates for the active workspace topology; they are not measured real-world exposure.",
        }

    def topology_summary(self, offset=0, limit=100, query="", zone=None):
        """Search and page host inventory while returning graph-level zone aggregates."""
        if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 1_000_000:
            raise ValueError("Topology offset must be an integer between 0 and 1000000.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_TOPOLOGY_PAGE:
            raise ValueError("Topology page size must be between 1 and %d." % MAX_TOPOLOGY_PAGE)
        if not isinstance(query, str) or len(query) > 120:
            raise ValueError("Topology search must be at most 120 characters.")
        if zone is not None and (not isinstance(zone, str) or len(zone) > 80):
            raise ValueError("Zone filter must be at most 80 characters.")

        query_key = query.casefold().strip()
        zone_filter = zone.casefold().strip() if zone else ""
        ordered = sorted(self.topology.hosts.values(), key=lambda item: (item.get("zone", ""), item.get("name", ""), item["host_id"]))
        matching = []
        for host in ordered:
            if zone_filter and host.get("zone", "").casefold() != zone_filter:
                continue
            if query_key:
                profile = self.topology.asset_profile(host["host_id"])
                haystack = " ".join([host["host_id"], host.get("name", ""), host.get("zone", ""),
                    host.get("role", ""), *profile.get("services", [])]).casefold()
                if query_key not in haystack:
                    continue
            matching.append(host)
        page = matching[offset:offset + limit]
        items = [self._host(host["host_id"]) for host in page]

        graph_snapshot = self.graph.snapshot()
        states = {item["host_id"]: item.get("state", "normal") for item in graph_snapshot.get("hosts", [])}
        zone_stats = defaultdict(lambda: {"host_count": 0, "normal_count": 0, "compromised_count": 0,
            "contained_count": 0, "edge_count": 0})
        for host in ordered:
            stats = zone_stats[host.get("zone", "unknown")]
            stats["host_count"] += 1
            stats[states.get(host["host_id"], "normal") + "_count"] += 1
        edge_bundles = defaultdict(int)
        page_edges = []
        page_ids = {host["host_id"] for host in page}
        truncated_edges = False
        for source, targets in self.topology._connections.items():
            source_zone = self.topology.hosts[source].get("zone", "unknown")
            for target in targets:
                target_zone = self.topology.hosts[target].get("zone", "unknown")
                zone_stats[source_zone]["edge_count"] += 1
                edge_bundles[(source_zone, target_zone)] += 1
                if source in page_ids:
                    if len(page_edges) < MAX_TOPOLOGY_PAGE_EDGES:
                        page_edges.append({"from_host": source, "to_host": target,
                            "likelihood": round(float(self.topology.edge_probability(source, target)), 4)})
                    else:
                        truncated_edges = True
        zones = [{"zone": name, **values} for name, values in sorted(zone_stats.items())]
        bundles = [{"from_zone": left, "to_zone": right, "count": count}
            for (left, right), count in sorted(edge_bundles.items())]
        next_offset = offset + len(page)
        if next_offset >= len(matching):
            next_offset = None
        return {
            "items": items, "total_hosts": len(ordered), "total_edges": sum(len(targets) for targets in self.topology._connections.values()),
            "total_matches": len(matching), "offset": offset, "limit": limit, "next_offset": next_offset,
            "query": query, "zone": zone, "zones": zones, "edge_bundles": bundles,
            "page_edges": page_edges, "page_edges_truncated": truncated_edges,
            "basis": "Host pages are exact records from the active topology. Zone link bundles aggregate feasible edges; risk and likelihood remain simulated estimates.",
        }

    def paths(self, source, target, limit=10):
        self._known(source)
        self._known(target)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PATHS:
            raise ValueError("Path limit must be between 1 and %d." % MAX_PATHS)
        result = []
        for hosts in self.topology.paths(source, target, limit=limit):
            edges = [{
                "from_host": left, "to_host": right,
                "likelihood": round(float(self.topology.edge_probability(left, right)), 6),
            } for left, right in zip(hosts, hosts[1:])]
            likelihood = 1.0
            for left, right in zip(hosts, hosts[1:]):
                likelihood *= float(self.topology.edge_probability(left, right))
            result.append({"hosts": hosts, "edges": edges, "likelihood": round(likelihood, 6)})
        return {"from_host": source, "to_host": target, "paths": result, "basis": "Product of simulated edge likelihood estimates; routes are feasible in the active workspace topology."}

    def _known(self, host_id):
        if not isinstance(host_id, str) or host_id not in self.topology.hosts:
            raise KeyError(host_id)

    def _related(self, host_id):
        alerts = [item for item in self.world.alerts(200) if item.get("host") == host_id]
        forecasts = [item for item in self.world.forecasts() if item.get("from_host") == host_id or any(target.get("host_id") == host_id for target in item.get("targets", []))]
        actions = [item for item in self.world.actions() if item.get("target_host") == host_id]
        incident_service = self.hooks.get("incidents")
        incidents = []
        if incident_service is not None:
            incidents = [{
                "incident_id": item["incident_id"], "title": item["title"],
                "severity": item["severity"], "status": item["status"],
                "created_at": item["created_at"], "updated_at": item["updated_at"],
            } for item in incident_service.snapshot_records() if host_id in item.get("affected_hosts", []) or host_id in item.get("compromised_hosts", [])]
        return alerts, forecasts, actions, incidents

    def host_detail(self, host_id):
        self._known(host_id)
        alerts, forecasts, actions, incidents = self._related(host_id)
        return {
            "host": self._host(host_id), "alerts": alerts, "forecasts": forecasts,
            "actions": actions, "incidents": incidents,
            "basis": "Host state is live in-memory simulation state; weakness and risk values are demo estimates.",
        }

    def _history_event(self, events, seen, host_id, kind, timestamp, summary, reference_id=None, run_id=None, state=None):
        key = (kind, reference_id, state, run_id)
        if key in seen:
            return
        seen.add(key)
        events.append({
            "event_id": "%s:%s:%s:%s" % (run_id or "live", kind, reference_id or "state", state or ""),
            "kind": kind, "occurred_at": timestamp or "", "summary": summary,
            "reference_id": reference_id, "run_id": run_id, "state": state,
        })

    def host_history(self, host_id, limit=200):
        self._known(host_id)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_HOST_HISTORY:
            raise ValueError("History limit must be between 1 and %d." % MAX_HOST_HISTORY)
        events, seen = [], set()
        graph = self.graph
        studio = self.hooks.get("studio")
        if studio is not None:
            for summary in studio.list_runs(50):
                record = studio.get_run(summary["run_id"])
                previous_state = None
                for snapshot in (record or {}).get("snapshots", []):
                    state = snapshot.get("state", {})
                    host = next((item for item in state.get("graph", {}).get("hosts", []) if item.get("host_id") == host_id), None)
                    if host is not None and host.get("state") != previous_state:
                        previous_state = host.get("state")
                        self._history_event(events, seen, host_id, "state", snapshot.get("captured_at"), "%s state: %s" % (self.topology.hosts[host_id]["name"], previous_state), run_id=summary["run_id"], state=previous_state)
                    for alert in state.get("alerts", []):
                        if alert.get("host") == host_id:
                            self._history_event(events, seen, host_id, "alert", alert.get("ts"), "%s · %s alert" % (alert.get("severity", "LOW"), alert.get("technique_name", "Detection")), alert.get("event_id"), summary["run_id"])
                    for forecast in state.get("forecasts", []):
                        targets = [item for item in forecast.get("targets", []) if item.get("host_id") == host_id]
                        if forecast.get("from_host") == host_id or targets:
                            label = "Forecast for host" if forecast.get("from_host") == host_id else "Forecast target"
                            self._history_event(events, seen, host_id, "forecast", forecast.get("created_at"), "%s · %s" % (label, forecast.get("status", "pending")), forecast.get("forecast_id"), summary["run_id"])
                    for action in state.get("actions", []):
                        if action.get("target_host") == host_id:
                            self._history_event(events, seen, host_id, "action", action.get("created_at") or action.get("proposed_at"), "Simulated containment · %s" % action.get("status", "unknown"), action.get("action_id"), summary["run_id"])
                    for incident in state.get("incidents", []):
                        if host_id in incident.get("affected_hosts", []) or host_id in incident.get("compromised_hosts", []):
                            self._history_event(events, seen, host_id, "incident", incident.get("updated_at"), incident.get("title", "Related incident"), incident.get("incident_id"), summary["run_id"])

        current = graph.snapshot()
        state_map = {item["host_id"]: item["state"] for item in current.get("hosts", [])}
        self._history_event(events, seen, host_id, "state", (self.world.session() or {}).get("started_at"), "Current simulation state: %s" % state_map.get(host_id, "normal"), run_id=(self.world.session() or {}).get("session_id"), state=state_map.get(host_id, "normal"))
        alerts, forecasts, actions, incidents = self._related(host_id)
        for alert in alerts:
            self._history_event(events, seen, host_id, "alert", alert.get("ts"), "%s · %s alert" % (alert.get("severity", "LOW"), alert.get("technique_name", "Detection")), alert.get("event_id"))
        for forecast in forecasts:
            self._history_event(events, seen, host_id, "forecast", forecast.get("created_at"), "Forecast · %s" % forecast.get("status", "pending"), forecast.get("forecast_id"))
        for action in actions:
            self._history_event(events, seen, host_id, "action", action.get("created_at") or action.get("proposed_at"), "Simulated containment · %s" % action.get("status", "unknown"), action.get("action_id"))
        for incident in incidents:
            self._history_event(events, seen, host_id, "incident", incident.get("updated_at"), incident["title"], incident["incident_id"])
        events.sort(key=lambda item: (item["occurred_at"], item["event_id"]))
        return {"host_id": host_id, "events": events[-limit:], "total": len(events)}

    def segmentation_preview(self, source, remove_from, remove_to):
        for host_id in (source, remove_from, remove_to):
            self._known(host_id)
        if remove_to not in self.topology.connections(remove_from):
            raise ValueError("The selected edge is not a feasible connection in the active workspace topology.")
        graph = nx.DiGraph()
        graph.add_nodes_from(self.topology.host_ids())
        graph.add_edges_from(self.topology.feasible_edges())
        before = sorted(nx.descendants(graph, source))
        graph.remove_edge(remove_from, remove_to)
        after = sorted(nx.descendants(graph, source))
        return {
            "source_host": source,
            "removed_edge": {"from_host": remove_from, "to_host": remove_to},
            "reachable_before": before, "reachable_after": after,
            "newly_unreachable": sorted(set(before) - set(after)),
            "basis": "Read-only reachability projection over feasible demo edges. No live topology or host state was changed.",
        }


def register(ctx):
    ctx.hooks.register("twin", NetworkTwin(ctx))

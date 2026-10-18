"""The static side of the attack graph: which hosts can reach which, and how exploitable each step is.

Built with the open-source `attackgraph` package (MIT), which turns a topology plus (simulated) weaknesses into
an attack graph and scores risk. If `attackgraph` is not installed, a plain networkx version gives the same
connections and a simple likelihood (the fallback named in the TRD). `self.engine` says which one is in use.
"""
import json
from pathlib import Path

import networkx as nx

try:  # attackgraph is installed from GitHub (it is not on PyPI)
    from attackgraph import Asset, AttackGraphBuilder, Vulnerability
    from attackgraph.models import AttackVector
    from attackgraph.scoring import RiskScorer

    HAVE_ATTACKGRAPH = True
except ImportError:  # pragma: no cover - exercised through use_attackgraph=False in the tests
    HAVE_ATTACKGRAPH = False


class Topology:
    def __init__(self, hosts, data, use_attackgraph=True):
        """hosts: list of host dicts (host_id, name, zone, address). data: the parsed topology.json."""
        self.hosts = {h["host_id"]: dict(h) for h in hosts}
        self._connections = {}
        for source, targets in data["feasible_connections"].items():
            self._check_known(source)
            for target in targets:
                self._check_known(target)
                if target == source:
                    raise ValueError("A host cannot connect to itself: %s" % source)
            self._connections[source] = list(dict.fromkeys(targets))
        for host_id in self.hosts:
            self._connections.setdefault(host_id, [])
        self._assets = data["assets"]
        for host_id in self._assets:
            self._check_known(host_id)
        self.engine = "attackgraph" if (use_attackgraph and HAVE_ATTACKGRAPH) else "networkx-fallback"
        self._probability = {}
        self._risk = {}
        self._build()

    @classmethod
    def from_files(cls, hosts, topology_path, use_attackgraph=True):
        return cls(hosts, json.loads(Path(topology_path).read_text(encoding="utf-8")), use_attackgraph)

    def _check_known(self, host_id):
        if host_id not in self.hosts:
            raise ValueError("The topology mentions an unknown host '%s'" % host_id)

    # ---------- building ----------
    def _best_cvss(self, host_id):
        vulns = self._assets.get(host_id, {}).get("vulns", [])
        return max((v["cvss"] for v in vulns), default=0.0)

    def _build(self):
        self._graph = nx.DiGraph()
        self._graph.add_nodes_from(self.hosts)
        for source, targets in self._connections.items():
            for target in targets:
                self._graph.add_edge(source, target)
        if self.engine == "attackgraph":
            assets = []
            for host_id, host in self.hosts.items():
                info = self._assets.get(host_id, {})
                asset = Asset(id=host_id, ip=host["address"], hostname=host["name"], services=list(info.get("services", [])),
                              criticality=float(info.get("criticality", 0.5)), network_zone=host["zone"])
                for vuln in info.get("vulns", []):
                    asset.vulns.append(Vulnerability(cve_id=vuln["id"], cvss=float(vuln["cvss"]), affected_service=vuln["service"],
                                                     attack_vector=AttackVector.NETWORK, description=vuln.get("description", "")))
                assets.append(asset)
            self._attack_graph = AttackGraphBuilder(topology=self._connections, assets=assets).build()
            for step in self._attack_graph.attack_steps:
                key = (step.source_asset, step.target_asset)
                self._probability[key] = max(self._probability.get(key, 0.0), float(step.probability))
            self._risk = dict(RiskScorer(self._attack_graph).score_assets())
        else:
            self._attack_graph = None
        for source, target in self._graph.edges:  # a connection without a modelled weakness still gets a likelihood
            self._probability.setdefault((source, target), round(self._best_cvss(target) / 10.0, 4))
        if not self._risk:
            self._risk = {h: round(self._best_cvss(h) * float(self._assets.get(h, {}).get("criticality", 0.5)), 2) for h in self.hosts}

    # ---------- questions ----------
    def host_ids(self):
        return list(self.hosts)

    def connections(self, host_id):
        """The hosts one hop away from host_id."""
        self._check_known(host_id)
        return list(self._connections[host_id])

    def feasible_edges(self):
        return [(s, t) for s, ts in self._connections.items() for t in ts]

    def candidates(self, host_id, exclude=()):
        """One-hop targets the attacker could try next, without the hosts in `exclude`."""
        excluded = set(exclude)
        return [t for t in self.connections(host_id) if t not in excluded]

    def reachable_from(self, host_id):
        self._check_known(host_id)
        return sorted(nx.descendants(self._graph, host_id))

    def paths(self, source, target, limit=10):
        """Feasible routes (lists of host ids) from source to target, shortest first, at most `limit`."""
        self._check_known(source)
        self._check_known(target)
        routes = sorted(nx.all_simple_paths(self._graph, source, target), key=lambda p: (len(p), p))
        return routes[:limit]

    def distance(self, source, target):
        """Number of hops, or None when the target cannot be reached."""
        try:
            return nx.shortest_path_length(self._graph, source, target)
        except nx.NetworkXNoPath:
            return None

    def edge_probability(self, source, target):
        """How likely the step is to succeed (0 to 1), from the simulated weakness of the target."""
        return self._probability.get((source, target), 0.0)

    def risk(self, host_id):
        """Risk score of a host (0 to 10), from the simulated weaknesses and how critical the host is."""
        self._check_known(host_id)
        return float(self._risk.get(host_id, 0.0))

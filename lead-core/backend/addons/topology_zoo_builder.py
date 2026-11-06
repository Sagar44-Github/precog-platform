"""Build a synthetic replay pack over one individually cleared topology file."""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import sqlite3
import tempfile
from pathlib import Path

import networkx as nx

from .dataset_packs import PackError, _canonical_json, _payload_hash, validate_pack
from .real_dataset_builders import _evaluation, _scenario, _write_database


MAX_SOURCE_BYTES = 25 * 1024 * 1024
MAX_NODES = 400


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_topology_zoo_pack(graph_path, license_record_path, output_dir, *, seed=0, route_count=30, contracts_dir=None):
    """Build only after a per-topology license record explicitly permits redistribution."""
    graph_path = Path(graph_path)
    license_path = Path(license_record_path)
    if graph_path.is_symlink() or license_path.is_symlink() or not graph_path.is_file() or not license_path.is_file():
        raise PackError("Graph and license record must be regular files, not symbolic links")
    if graph_path.stat().st_size > MAX_SOURCE_BYTES:
        raise PackError("GraphML source exceeds 25 MiB")
    try:
        clearance = json.loads(license_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackError("Cannot read a valid UTF-8 per-topology license record") from exc
    required = ("source_url", "license", "citation", "redistribution_allowed", "graph_sha256")
    if any(key not in clearance for key in required):
        raise PackError("License record needs source_url, license, citation, redistribution_allowed, graph_sha256")
    if clearance["redistribution_allowed"] is not True:
        raise PackError("Per-topology terms do not permit redistribution; no pack was built")
    if clearance["graph_sha256"] != _sha256(graph_path):
        raise PackError("License record graph_sha256 does not match the input topology")
    if not all(isinstance(clearance[key], str) and clearance[key].strip() for key in ("source_url", "license", "citation")):
        raise PackError("License record source URL, license, and citation must be non-empty text")
    if not (0 <= int(seed) <= 2**31 - 1) or not (5 <= int(route_count) <= 500):
        raise PackError("seed or route_count is outside documented bounds")
    try:
        graph = nx.read_graphml(graph_path)
    except Exception as exc:
        raise PackError("Input must be a readable GraphML graph") from exc
    graph = nx.Graph(graph)
    graph.remove_edges_from(nx.selfloop_edges(graph))
    if graph.number_of_nodes() < 2 or graph.number_of_nodes() > MAX_NODES or graph.number_of_edges() < 1:
        raise PackError("Selected graph must have 2-400 nodes and at least one non-loop edge")
    raw_nodes = sorted((str(node) for node in graph.nodes()), key=lambda value: value)
    node_ids = {raw: "node-" + hashlib.sha256((str(seed) + "\0" + raw).encode("utf-8")).hexdigest()[:16] for raw in raw_nodes}
    adjacency = {node_ids[str(host)]: sorted(node_ids[str(n)] for n in graph.neighbors(host)) for host in graph.nodes()}
    hosts = [{"host_id": node_ids[raw], "name": "Topology node %03d" % index,
        # TEST-NET addresses are generated placeholders; source labels and addresses are discarded.
        "address": ("192.0.2.%d" % index) if index <= 254 else ("198.51.100.%d" % (index - 254)),
        "zone": "observed", "role": "topology node", "services": []} for index, raw in enumerate(raw_nodes, 1)]
    edges = sorted({tuple(sorted((node_ids[str(src)], node_ids[str(dst)]))) for src, dst in graph.edges() if src != dst})
    rng = random.Random(int(seed))
    routes, events = [], []
    starts = sorted(adjacency)
    max_attempts = int(route_count) * 20
    for _ in range(max_attempts):
        if len(routes) >= route_count:
            break
        current = starts[rng.randrange(len(starts))]
        path = [current]
        for _step in range(4):
            candidates = [node for node in adjacency[current] if node not in path]
            if not candidates:
                break
            current = candidates[rng.randrange(len(candidates))]
            path.append(current)
        if len(path) >= 2:
            routes.append({"route_id": "route-%06d" % (len(routes) + 1), "profile": "synthetic-topology-walk",
                "path": path, "provenance": "project-generated-simulation"})
    if len(routes) < 5:
        raise PackError("Selected graph has too few usable paths for a replay/evaluation")
    for route_index, route in enumerate(routes):
        for hop, dst in enumerate(route["path"][1:]):
            src = route["path"][hop]
            t = route_index * 3000 + hop * 500
            events.append({"event_id": len(events) + 1, "t": t, "src": src, "dst": dst, "kind": "attempt",
                "severity": "HIGH", "label": "simulated-lateral-movement", "attack_class": "simulated-lateral-movement",
                "protocol": "TCP", "port": 443, "bytes": 512,
                "extra": {"simulation": True, "route_id": route["route_id"], "source_topology": "Topology Zoo"}})
    edge_events = {}
    for event in events:
        edge = (event["src"], event["dst"])
        edge_events[edge] = edge_events.get(edge, 0) + 1
    edge_rows = [{"src": src, "dst": dst, "count": edge_events.get((src, dst), 0) + edge_events.get((dst, src), 0),
        "first_seen": min((event["t"] for event in events if {event["src"], event["dst"]} == {src, dst}), default=None),
        "last_seen": max((event["t"] for event in events if {event["src"], event["dst"]} == {src, dst}), default=None)}
        for src, dst in edges]
    topology = {"network_id": "synth-topology-zoo", "hosts": hosts,
        "feasible_edges": [{"src": src, "dst": dst} for src, dst in edges],
        "observed_edges": [{"src": edge["src"], "dst": edge["dst"], "count": edge["count"], "provenance": "source-topology-and-generated-replay"} for edge in edge_rows],
        "assets": {host["host_id"]: {"services": [], "criticality": 0.5, "source": "source-topology"} for host in hosts},
        "clusters": [{"id": "topology", "name": "Source topology", "host_ids": [host["host_id"] for host in hosts]}]}
    scenario = _scenario("synth-topology-zoo", events)
    output_dir = Path(output_dir)
    if output_dir.name != "synth-topology-zoo" or output_dir.is_symlink():
        raise PackError("Output must be a non-symlink directory named synth-topology-zoo")
    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".synth-topology-zoo-build-", dir=str(output_dir.parent)))
    backup = output_dir.parent / ".synth-topology-zoo-backup"
    try:
        (staging / "scenarios").mkdir()
        (staging / "topology.json").write_bytes(_canonical_json(topology))
        (staging / "scenarios" / "synth-topology-zoo.json").write_bytes(_canonical_json(scenario))
        (staging / "routes.jsonl").write_text("\n".join(json.dumps(route, sort_keys=True, separators=(",", ":")) for route in routes) + "\n", encoding="utf-8", newline="\n")
        _write_database(staging / "pack.sqlite", hosts, edge_rows, events, routes, 0, max(event["t"] for event in events), "synth-topology-zoo")
        counts = {}
        for route in routes:
            for src, dst in zip(route["path"], route["path"][1:]):
                counts.setdefault(src, {})[dst] = counts.setdefault(src, {}).get(dst, 0) + 1
        model = {"alpha": 0.1, "counts": counts, "meta": {"workspace_id": "synth-topology-zoo", "seed": int(seed), "model_type": "simulated topology-walk Markov model"}}
        (staging / "model.json").write_bytes(_canonical_json(model))
        limitations = [
            "Only topology comes from the cited source file; all attacks, labels, routes and event timing are generated by this project.",
            "The pack is a simulation over the selected graph, not observed threat activity or a real-attack dataset.",
            "Precog metrics describe only the deterministic synthetic walks generated for this topology.",
        ]
        evaluation = {"precog_evaluation": {"status": "generated-simulation-evaluation", "route_count": len(routes)},
            "limitations": limitations}
        (staging / "evaluation.json").write_bytes(_canonical_json(evaluation))
        (staging / "card.md").write_text("# Synthetic replay over a cleared topology\n\nOnly the graph structure comes from the attributed input. Events, attack labels, routes, and forecasts are project-generated simulation.\n\n- Source: %s\n- License: %s\n- Citation: %s\n- Input SHA-256: %s\n- Seed: %d; nodes: %d; edges: %d; generated routes: %d.\n- No raw addresses or source node labels are stored.\n- This is not observed attacker behavior or evidence of real-world protection.\n" % (
            clearance["source_url"], clearance["license"], clearance["citation"], clearance["graph_sha256"], int(seed), len(hosts), len(edges), len(routes)), encoding="utf-8", newline="\n")
        manifest = {"id": "synth-topology-zoo", "name": "Synthetic replay over a cleared topology", "version": "1.0.0",
            "builder_version": "precog-topology-zoo-builder/1.0.0", "seed": int(seed), "created_at": "1970-01-01T00:00:00Z",
            "source": {"id": "internet-topology-zoo", "name": "Individually cleared topology file",
                "citation": clearance["citation"] + " Source: " + clearance["source_url"], "licence": clearance["license"],
                "terms_summary": "Redistribution was explicitly attested for this exact input SHA-256; review the contributor license before publishing."},
            "redistribution": "per-topology-attribution-required", "size_bytes": 0,
            "counts": {"hosts": len(hosts), "edges": len(edges), "events": len(events), "labelled_events": len(events), "routes": len(routes), "time_span_ms": max(event["t"] for event in events)},
            "capabilities": {"detection_labels": "derived", "host_compromise": "derived", "lateral_movement_routes": "derived", "topology": "native"},
            "attack_classes": [{"id": "simulated-lateral-movement", "compromise_semantics": "lateral-movement"}],
            "technique_mapping": [{"attack_class": "simulated-lateral-movement", "technique_ids": ["T1021.001"], "assumption": "ATT&CK hint is assigned by this replay generator and does not describe the source topology."}],
            "detector_options": ["labels", "graph-novelty"], "default_decision_policy": {"mode": "never", "threshold": 1.0, "minimum_candidates": 0},
            "display_hints": {"zones": ["topology"], "clusters": "source-graph", "layout": "topology"},
            "source_file_checksums": [{"path": Path(graph_path).name, "sha256": clearance["graph_sha256"]}], "content_hash": "0" * 64}
        (staging / "manifest.json").write_bytes(_canonical_json(manifest))
        digest, size = _payload_hash(staging)
        manifest["content_hash"], manifest["size_bytes"] = digest, size
        (staging / "manifest.json").write_bytes(_canonical_json(manifest))
        validate_pack(staging, contracts_dir, require_matching_dir=False)
        from .synthetic_packs import _evaluate_pack_contents
        _evaluate_pack_contents(staging, contracts_dir, seed=seed, route_provenance="simulated", limitations=limitations)
        if output_dir.exists():
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(output_dir, backup)
        try:
            os.replace(staging, output_dir)
        except Exception:
            if backup.exists() and not output_dir.exists():
                os.replace(backup, output_dir)
            raise
        if backup.exists():
            shutil.rmtree(backup)
        return validate_pack(output_dir, contracts_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

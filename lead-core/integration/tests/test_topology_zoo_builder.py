"""Tests for the per-topology license gate and generated GraphML replay pack."""
import hashlib
import json
import sys
from pathlib import Path

import networkx as nx
import pytest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "lead-core" / "backend"))
from addons.dataset_packs import PackError, validate_pack
from addons.topology_zoo_builder import build_topology_zoo_pack
from tools.datasets.build_topology_zoo import main as build_cli


def _inputs(tmp_path, permitted=True):
    graph_path = tmp_path / "fixture.graphml"
    graph = nx.cycle_graph(8)
    nx.write_graphml(graph, graph_path)
    license_path = tmp_path / "license.json"
    record = {"source_url": "https://topology-zoo.org/", "license": "fixture CC-BY",
        "citation": "Handmade graph fixture; no source topology is redistributed.",
        "redistribution_allowed": permitted, "graph_sha256": hashlib.sha256(graph_path.read_bytes()).hexdigest()}
    license_path.write_text(json.dumps(record), encoding="utf-8")
    return graph_path, license_path


def test_license_cleared_graphml_builds_deterministic_simulation_pack(tmp_path):
    graph_path, license_path = _inputs(tmp_path)
    first = build_topology_zoo_pack(graph_path, license_path, tmp_path / "one" / "synth-topology-zoo",
        seed=22, route_count=10, contracts_dir=ROOT / "contracts")
    second = build_topology_zoo_pack(graph_path, license_path, tmp_path / "two" / "synth-topology-zoo",
        seed=22, route_count=10, contracts_dir=ROOT / "contracts")
    validate_pack(tmp_path / "one" / "synth-topology-zoo", ROOT / "contracts")
    assert first["content_hash"] == second["content_hash"]
    assert first["counts"]["hosts"] == 8
    assert first["counts"]["routes"] == 10
    assert first["capabilities"]["detection_labels"] == "derived"
    assert first["capabilities"]["host_compromise"] == "derived"
    assert first["capabilities"]["lateral_movement_routes"] == "derived"
    assert first["capabilities"]["topology"] == "native"
    assert first["source"]["terms_summary"].startswith("Redistribution was explicitly attested")


def test_license_and_source_hash_are_hard_gates(tmp_path):
    graph_path, license_path = _inputs(tmp_path, permitted=False)
    with pytest.raises(PackError, match="do not permit"):
        build_topology_zoo_pack(graph_path, license_path, tmp_path / "synth-topology-zoo", route_count=5)
    _inputs(tmp_path, permitted=True)
    record = json.loads(license_path.read_text(encoding="utf-8"))
    record["graph_sha256"] = "0" * 64
    license_path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(PackError, match="does not match"):
        build_topology_zoo_pack(graph_path, license_path, tmp_path / "synth-topology-zoo", route_count=5)


def test_cli_keeps_topology_output_in_ignored_backend_data(tmp_path):
    graph_path, license_path = _inputs(tmp_path)
    result = build_cli(["--graphml", str(graph_path), "--license-record", str(license_path),
        "--out", str(tmp_path / "synth-topology-zoo"), "--routes", "5"])
    assert result == 2
    assert not (tmp_path / "synth-topology-zoo").exists()

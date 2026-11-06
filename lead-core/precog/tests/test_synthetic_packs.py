"""D3 synthetic pack and per-pack evaluation reproducibility gates."""
import json
import shutil
from pathlib import Path

import pytest

from precog_helpers import REPO_ROOT
from addons.dataset_packs import validate_pack
from addons.synthetic_packs import SPECS, build_synthetic_pack, evaluate_pack


@pytest.mark.parametrize("pack_id", sorted(SPECS))
def test_seeded_packs_and_evaluation_reruns_are_byte_reproducible(tmp_path, pack_id):
    first = tmp_path / "first" / pack_id
    second = tmp_path / "second" / pack_id
    first_manifest = build_synthetic_pack(REPO_ROOT, pack_id, first)
    second_manifest = build_synthetic_pack(REPO_ROOT, pack_id, second)
    assert first_manifest == second_manifest
    assert first_manifest["seed"] == SPECS[pack_id]["seed"]
    assert first_manifest["counts"]["hosts"] == SPECS[pack_id]["hosts"]
    assert first_manifest["capabilities"] == {
        "detection_labels": "native", "host_compromise": "native",
        "lateral_movement_routes": "native", "topology": "native",
    }
    topology = json.loads((first / "topology.json").read_text(encoding="utf-8"))
    assert any(asset["decoy"] for asset in topology["assets"].values())
    first_files = {path.relative_to(first).as_posix(): path.read_bytes() for path in first.rglob("*") if path.is_file()}
    second_files = {path.relative_to(second).as_posix(): path.read_bytes() for path in second.rglob("*") if path.is_file()}
    assert first_files == second_files

    evaluation = json.loads((first / "evaluation.json").read_text(encoding="utf-8"))
    summary = evaluation["evaluation_result"]
    assert summary["route_provenance"] == "simulated"
    assert summary["metrics"]["forecasts"] == summary["split"]["test_forecasts"]
    assert summary["metrics"]["mean_reciprocal_rank"] > 0
    assert summary["candidate_set_distribution"]
    assert summary["calibration_bins"]
    assert validate_pack(first)["content_hash"] == first_manifest["content_hash"]

    rerun_manifest, rerun = evaluate_pack(second, REPO_ROOT / "contracts", seed=second_manifest["seed"])
    assert rerun_manifest["content_hash"] == first_manifest["content_hash"]
    assert rerun["evaluation_result"] == summary
    assert {path.relative_to(second).as_posix(): path.read_bytes() for path in second.rglob("*") if path.is_file()} == first_files


def test_changing_the_synthetic_seed_changes_the_pack_payload(tmp_path):
    first = build_synthetic_pack(REPO_ROOT, "synth-enterprise-30", tmp_path / "seed-17" / "synth-enterprise-30", seed=17)
    second = build_synthetic_pack(REPO_ROOT, "synth-enterprise-30", tmp_path / "seed-18" / "synth-enterprise-30", seed=18)
    assert first["seed"] == 17 and second["seed"] == 18
    assert first["content_hash"] != second["content_hash"]
    assert first["counts"]["hosts"] == second["counts"]["hosts"] == 30


def test_seed_zero_demo_evaluation_keeps_the_shipped_numbers(tmp_path):
    source_pack = REPO_ROOT / "packs" / "demo-6"
    pack_copy = tmp_path / "demo-6"
    shutil.copytree(source_pack, pack_copy)
    _manifest, result = evaluate_pack(pack_copy, REPO_ROOT / "contracts", seed=0, test_fraction=0.2)
    shipped = json.loads((REPO_ROOT / "lead-core" / "precog" / "results" / "precog_evaluation.json").read_text(encoding="utf-8"))
    for section in ("node_model", "baseline_rule_based", "baseline_uniform"):
        for metric in ("forecasts", "precision_at_1", "precision_at_1_std_error", "precision_at_3", "expected_calibration_error", "calibration_bins"):
            assert result[section][metric] == shipped[section][metric], (section, metric)
    assert result["split"] == shipped["split"]
    assert result["alpha"]["chosen"] == shipped["alpha"]["chosen"]

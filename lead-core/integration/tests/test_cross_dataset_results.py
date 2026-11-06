import hashlib
import json
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _manifest_hash(pack_id):
    return hashlib.sha256((ROOT / "packs" / pack_id / "manifest.json").read_bytes()).hexdigest()


def test_cross_dataset_report_recomputes_installed_packs_without_changing_source_packs():
    module = runpy.run_path(str(ROOT / "tools" / "datasets" / "build_cross_dataset_results.py"))
    ids = ("demo-6", "synth-enterprise-30", "synth-enterprise-120", "synth-enterprise-300", "synth-datacenter-300")
    before = {pack_id: _manifest_hash(pack_id) for pack_id in ids}

    report = module["render_results"]()

    after = {pack_id: _manifest_hash(pack_id) for pack_id in ids}
    assert before == after
    assert "| demo-6 | installed | 6 |" in report
    assert "| lanl-cyber1 | builder-ready-needs-manual-download | — |" in report
    assert "0.6510 ± 0.0390" in report
    assert "not installed; source/licence gate pending" in report

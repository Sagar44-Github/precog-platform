import runpy
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_hosted_pack_prepare_keeps_the_demo_and_selected_sizes_and_omits_local_only(tmp_path):
    module = runpy.run_path(str(ROOT / "deploy" / "prepare_hosted_packs.py"))
    pack_root = tmp_path / "packs"
    pack_root.mkdir()
    for pack_id in (*module["SHIPPED"], *module["LOCAL_ONLY"]):
        shutil.copytree(ROOT / "packs" / pack_id, pack_root / pack_id)

    summaries = module["prepare_hosted_packs"](pack_root, ROOT / "contracts")

    assert {item["id"] for item in summaries} == set(module["SHIPPED"])
    assert (pack_root / "demo-6").is_dir()
    assert not (pack_root / "synth-datacenter-300").exists()
    assert all(item["bytes"] <= 25 * 1024 * 1024 for item in summaries)

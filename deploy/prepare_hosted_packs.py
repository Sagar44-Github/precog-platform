"""Validate the hosted workspace set and omit the local-only large pack."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lead-core" / "backend"))

from addons.dataset_packs import PACK_MAX_BYTES, validate_pack

PACK_ROOT = REPO_ROOT / "packs"
CONTRACTS = REPO_ROOT / "contracts"
SHIPPED = ("demo-6", "synth-enterprise-30", "synth-enterprise-120", "synth-enterprise-300")
LOCAL_ONLY = ("synth-datacenter-300",)


def prepare_hosted_packs(pack_root=PACK_ROOT, contracts_dir=CONTRACTS):
    root = Path(pack_root).resolve()
    if not root.is_dir() or root.is_symlink():
        raise SystemExit("Hosted pack root is missing or unsafe: %s" % root)
    summaries = []
    for pack_id in SHIPPED:
        folder = root / pack_id
        if folder.is_symlink() or folder.resolve().parent != root:
            raise SystemExit("Hosted pack path is missing or unsafe: %s" % pack_id)
        try:
            manifest = validate_pack(folder, contracts_dir)
        except Exception as exc:
            raise SystemExit("Hosted pack %s failed validation: %s" % (pack_id, exc)) from exc
        if manifest["size_bytes"] > PACK_MAX_BYTES:
            raise SystemExit("Hosted pack exceeds the 25 MiB limit: %s" % pack_id)
        summaries.append({"id": pack_id, "hosts": manifest["counts"]["hosts"], "bytes": manifest["size_bytes"]})

    for pack_id in LOCAL_ONLY:
        folder = root / pack_id
        if folder.is_symlink() or folder.resolve().parent != root:
            raise SystemExit("Local-only pack path is unsafe: %s" % pack_id)
        if folder.exists():
            shutil.rmtree(folder)

    print(json.dumps({"shipped": summaries, "local_only": list(LOCAL_ONLY),
                      "shipped_bytes": sum(item["bytes"] for item in summaries)}, indent=2))
    return summaries


if __name__ == "__main__":
    prepare_hosted_packs()

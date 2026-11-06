"""Recompute a dataset pack's held-out Precog evaluation reproducibly.

Usage from the repository root: python tools/datasets/evaluate_pack.py synth-enterprise-30
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for folder in ("lead-core/backend", "lead-core/precog", "graph"):
    sys.path.insert(0, str(ROOT / folder))

from addons.dataset_packs import PackError
from addons.synthetic_packs import evaluate_pack


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack_id", help="an installed pack identifier, never a filesystem path")
    parser.add_argument("--packs-root", type=Path, default=ROOT / "packs")
    parser.add_argument("--seed", type=int, help="evaluation split seed (defaults to the manifest seed)")
    parser.add_argument("--test-fraction", type=float, default=0.2)
    args = parser.parse_args(argv)
    if not 0.05 <= args.test_fraction <= 0.5:
        parser.error("--test-fraction must be between 0.05 and 0.5")
    try:
        pack_dir = (args.packs_root / args.pack_id).resolve()
        if pack_dir.parent != args.packs_root.resolve():
            parser.error("pack_id must identify one direct child of --packs-root")
        manifest, evaluation = evaluate_pack(pack_dir, ROOT / "contracts", seed=args.seed, test_fraction=args.test_fraction)
    except (PackError, OSError, ValueError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2
    summary = evaluation["evaluation_result"]
    print(json.dumps({"workspace_id": manifest["id"], "content_hash": manifest["content_hash"],
                      "evaluation": summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

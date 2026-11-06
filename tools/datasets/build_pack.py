"""Build an offline dataset pack from project fixtures or the seeded synthetic generator."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lead-core" / "backend"))
sys.path.insert(0, str(ROOT / "lead-core" / "precog"))
sys.path.insert(0, str(ROOT / "graph"))
from addons.dataset_packs import PackError, build_demo6_pack, validate_existing_demo_equivalence
from addons.synthetic_packs import SPECS, build_synthetic_pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, choices=["demo-6", *sorted(SPECS)])
    parser.add_argument("--raw", type=Path, help="not applicable to the project-owned demo source")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--max-hosts", type=int)
    parser.add_argument("--window")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output = args.out or ROOT / "packs" / args.source
    if args.source == "demo-6" and args.seed not in (None, 0):
        parser.error("demo-6 seed is fixed at 0 to preserve the existing fixtures")
    if args.raw is not None or args.max_hosts is not None or args.window is not None:
        parser.error("this source uses checked-in or generated records; --raw/--max-hosts/--window are not applicable")
    if output.exists() and not args.force:
        parser.error("output exists; pass --force to replace it")
    try:
        if args.source == "demo-6":
            manifest = build_demo6_pack(ROOT, output, ROOT / "contracts")
            result = validate_existing_demo_equivalence(output, ROOT)
        else:
            manifest = build_synthetic_pack(ROOT, args.source, output, seed=args.seed, contracts_dir=ROOT / "contracts")
            result = {"seed": manifest["seed"], "evaluation": "held-out per-pack run embedded in evaluation.json"}
        print(json.dumps({"pack_id": manifest["id"], "hash": manifest["content_hash"], "counts": manifest["counts"], "equivalence": result}, indent=2))
        return 0
    except (PackError, OSError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

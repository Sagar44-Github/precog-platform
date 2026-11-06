"""Build an offline dataset pack from a supported source (D1: demo-6)."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lead-core" / "backend"))
from addons.dataset_packs import PackError, build_demo6_pack, validate_existing_demo_equivalence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, choices=["demo-6"])
    parser.add_argument("--raw", type=Path, help="not applicable to the project-owned demo source")
    parser.add_argument("--out", type=Path, default=ROOT / "packs" / "demo-6")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-hosts", type=int)
    parser.add_argument("--window")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.seed != 0:
        parser.error("demo-6 seed is fixed at 0 to preserve the existing fixtures")
    if args.raw is not None or args.max_hosts is not None or args.window is not None:
        parser.error("demo-6 uses checked-in fixtures; --raw/--max-hosts/--window are not applicable")
    if args.out.exists() and not args.force:
        parser.error("output exists; pass --force to replace it")
    try:
        manifest = build_demo6_pack(ROOT, args.out, ROOT / "contracts")
        result = validate_existing_demo_equivalence(args.out, ROOT)
        print(json.dumps({"pack_id": manifest["id"], "hash": manifest["content_hash"], "counts": manifest["counts"], "equivalence": result}, indent=2))
        return 0
    except (PackError, OSError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

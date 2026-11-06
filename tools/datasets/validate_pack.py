"""Validate an offline dataset pack directory."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lead-core" / "backend"))
from addons.dataset_packs import PackError, validate_pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path, nargs="?", default=ROOT / "packs" / "demo-6")
    args = parser.parse_args()
    try:
        manifest = validate_pack(args.pack, ROOT / "contracts")
        print(json.dumps({"valid": True, "id": manifest["id"], "content_hash": manifest["content_hash"], "counts": manifest["counts"]}, indent=2))
        return 0
    except (PackError, OSError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

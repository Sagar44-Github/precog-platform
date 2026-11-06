"""Inspect a valid pack without loading its event table into memory."""
import argparse
import json
import sqlite3
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
        pack_dir = args.pack.resolve()
        manifest = validate_pack(pack_dir, ROOT / "contracts")
        conn = sqlite3.connect("file:%s?mode=ro" % (pack_dir / "pack.sqlite").as_posix(), uri=True)
        try:
            row_counts = {name: conn.execute("SELECT COUNT(*) FROM " + name).fetchone()[0] for name in ("hosts", "edges", "events", "routes", "labels", "windows")}
        finally:
            conn.close()
        print(json.dumps({"id": manifest["id"], "name": manifest["name"], "content_hash": manifest["content_hash"], "counts": manifest["counts"], "sqlite_rows": row_counts, "size_bytes": manifest["size_bytes"]}, indent=2))
        return 0
    except (PackError, OSError, sqlite3.Error) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

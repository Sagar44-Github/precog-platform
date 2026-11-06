"""Verify and stage manually obtained real-dataset source files.

Dataset sources use registration forms, very large archives, or terms that do
not permit automatic mirroring. This helper never guesses URLs or checksums: pass
the SHA-256 published by the source or computed during a trusted download.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lead-core" / "backend"))
from addons.real_dataset_builders import SPECS


def _digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, choices=sorted(SPECS))
    parser.add_argument("--raw-dir", required=True, type=Path, help="directory containing manually downloaded files")
    parser.add_argument("--out", type=Path, help="defaults to ignored lead-core/backend/data/raw/<source>")
    parser.add_argument("--sha256", action="append", required=True, metavar="FILE=HEX", help="expected file hash; repeat for each selected file")
    args = parser.parse_args(argv)
    raw_input = args.raw_dir.absolute()
    if raw_input.is_symlink():
        parser.error("--raw-dir cannot be a symbolic link")
    raw_dir = raw_input.resolve()
    raw_out = args.out or ROOT / "lead-core" / "backend" / "data" / "raw" / args.source
    if raw_out.is_symlink():
        parser.error("--out cannot be a symbolic link")
    out = raw_out.resolve()
    if not raw_dir.is_dir():
        parser.error("--raw-dir must be a real directory")
    ignored_data = (ROOT / "lead-core" / "backend" / "data").resolve()
    if (out == ROOT or ROOT in out.parents) and ignored_data not in out.parents:
        parser.error("staged raw data must remain under ignored lead-core/backend/data")
    expected = {}
    for pair in args.sha256:
        if "=" not in pair:
            parser.error("each --sha256 must be FILE=64_HEX_CHARACTERS")
        name, digest = pair.split("=", 1)
        if Path(name).name != name or name in ("", ".", "..") or not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
            parser.error("invalid checksum entry: %r" % pair)
        if name in expected:
            parser.error("duplicate checksum for %s" % name)
        expected[name] = digest.lower()
    files = []
    for name, digest in sorted(expected.items()):
        source = raw_dir / name
        if not source.is_file() or source.is_symlink():
            parser.error("missing regular source file: %s" % name)
        actual = _digest(source)
        if actual != digest:
            parser.error("SHA-256 mismatch for %s: expected %s, got %s" % (name, digest, actual))
        files.append((source, actual))
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".%s-fetch-" % args.source, dir=str(out.parent)))
    try:
        for source, _ in files:
            target = staging / source.name
            with source.open("rb") as src, target.open("xb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
        (staging / "source_checksums.json").write_text(json.dumps({
            "schema_version": 1, "source_id": args.source,
            "files": [{"name": source.name, "sha256": digest} for source, digest in files],
        }, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        if out.exists():
            if out.is_symlink() or not out.is_dir():
                parser.error("output exists and is not a regular directory")
            backup = out.parent / (".%s-fetch-backup" % args.source)
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(out, backup)
            try:
                os.replace(staging, out)
            except Exception:
                os.replace(backup, out)
                raise
            shutil.rmtree(backup, ignore_errors=True)
        else:
            os.replace(staging, out)
        for source, digest in files:
            print("ok %s sha256=%s" % (source.name, digest))
        print("Staged verified source files at %s" % out)
        print("Source: %s" % SPECS[args.source].url)
        return 0
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

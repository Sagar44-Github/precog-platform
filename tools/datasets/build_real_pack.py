"""Build a local real-source dataset pack after its access and licence gate.

Raw files are never copied into the pack. Use fetch.py first to verify and stage
the exact files, then pass their paths here. Outputs default to ignored local data.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lead-core" / "backend"))
from addons.dataset_packs import PackError
from addons.real_dataset_builders import MAX_EVENTS, MAX_HOSTS, SPECS, build_real_dataset_pack


def _files(values):
    files = []
    for value in values:
        path = Path(value).absolute()
        if path.is_symlink():
            raise PackError("Input paths cannot be symbolic links")
        if path.is_dir():
            candidates = list(path.rglob("*"))
            if any(item.is_symlink() for item in candidates):
                raise PackError("Input directories cannot contain symbolic links")
            files.extend(sorted(item.resolve() for item in candidates if item.is_file()))
        elif path.is_file():
            files.append(path.resolve())
        else:
            raise PackError("Input does not exist: %s" % path)
    # LANL needs only these two sources. Other CSV collections may contain
    # readme files; filter to supported record formats.
    return [path for path in files if path.name.lower().endswith((".csv", ".txt", ".txt.gz", ".csv.gz", ".binetflow"))]


def _verify_source_checksums(values, files, source_id):
    expected = {}
    processed_manifests = set()
    for value in values:
        path = Path(value).resolve()
        base = path if path.is_dir() else path.parent
        manifest_path = base / "source_checksums.json"
        if manifest_path in processed_manifests:
            continue
        processed_manifests.add(manifest_path)
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise PackError("Raw inputs must first be staged by tools/datasets/fetch.py with SHA-256 verification")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PackError("Invalid source_checksums.json in %s" % base) from exc
        if manifest.get("schema_version") != 1 or manifest.get("source_id") != source_id or not isinstance(manifest.get("files"), list):
            raise PackError("source_checksums.json does not match dataset %s" % source_id)
        for item in manifest["files"]:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not isinstance(item.get("sha256"), str):
                raise PackError("Invalid source checksum entry")
            if item["name"] in expected:
                raise PackError("Duplicate staged source filename: %s" % item["name"])
            expected[item["name"]] = item["sha256"].lower()
    for path in files:
        digest = expected.get(path.name)
        if digest is None or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise PackError("No valid staged checksum for %s" % path.name)
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        actual = hasher.hexdigest()
        if actual != digest:
            raise PackError("Staged source hash changed for %s" % path.name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, choices=sorted(SPECS))
    parser.add_argument("--raw", nargs="+", required=True, help="verified files or directories of downloaded source files")
    parser.add_argument("--out", type=Path, help="defaults to ignored lead-core/backend/data/real-packs/<source>")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-hosts", type=int, default=400)
    parser.add_argument("--max-events", type=int, default=50_000)
    parser.add_argument("--allow-attributed-pack", action="store_true",
                        help="acknowledge citation obligations for sources whose reviewed terms allow redistribution")
    args = parser.parse_args(argv)
    if not 1 <= args.max_hosts <= MAX_HOSTS:
        parser.error("--max-hosts must be between 1 and %d" % MAX_HOSTS)
    if not 1 <= args.max_events <= MAX_EVENTS:
        parser.error("--max-events must be between 1 and %d" % MAX_EVENTS)
    spec = SPECS[args.source]
    raw_out = args.out or ROOT / "lead-core" / "backend" / "data" / "real-packs" / args.source
    if raw_out.is_symlink():
        parser.error("output path cannot be a symbolic link")
    out = raw_out.resolve()
    tracked_packs = (ROOT / "packs").resolve()
    if tracked_packs == out or tracked_packs in out.parents:
        if spec.redistribution.startswith("builder-only"):
            parser.error("this source is builder-only pending written terms; output must remain under ignored local data")
        if not args.allow_attributed_pack:
            parser.error("acknowledge the source attribution with --allow-attributed-pack before writing under packs/")
    data_dir = (ROOT / "lead-core" / "backend" / "data").resolve()
    if (out == ROOT or ROOT in out.parents) and not (data_dir in out.parents or tracked_packs in out.parents):
        parser.error("real-data packs under the repository must stay under ignored backend/data or the gated packs directory")
    try:
        files = _files(args.raw)
        _verify_source_checksums(args.raw, files, args.source)
        manifest = build_real_dataset_pack(args.source, files, out, seed=args.seed,
            max_hosts=args.max_hosts, max_events=args.max_events, contracts_dir=ROOT / "contracts")
        print(json.dumps({"pack_id": manifest["id"], "status": "local-only; registry activation remains gated",
            "redistribution": manifest["redistribution"], "counts": manifest["counts"],
            "content_hash": manifest["content_hash"], "output": str(out)}, indent=2))
        return 0
    except (PackError, OSError, ValueError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

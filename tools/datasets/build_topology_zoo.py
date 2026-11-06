"""Build a synthetic topology pack from one explicitly license-cleared GraphML."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "lead-core" / "backend"))
from addons.dataset_packs import PackError
from addons.topology_zoo_builder import build_topology_zoo_pack


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphml", required=True, type=Path)
    parser.add_argument("--license-record", required=True, type=Path,
        help="JSON record with source_url, license, citation, redistribution_allowed=true, and exact graph_sha256")
    parser.add_argument("--out", type=Path,
        default=ROOT / "lead-core" / "backend" / "data" / "real-packs" / "synth-topology-zoo")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--routes", type=int, default=30)
    args = parser.parse_args(argv)
    try:
        raw_output = args.out.absolute()
        if raw_output.is_symlink():
            raise PackError("output path cannot be a symbolic link")
        output = raw_output.resolve()
        local_data = (ROOT / "lead-core" / "backend" / "data").resolve()
        if local_data not in output.parents:
            raise PackError("Topology Zoo simulation output must remain under ignored lead-core/backend/data")
        manifest = build_topology_zoo_pack(args.graphml, args.license_record, args.out,
            seed=args.seed, route_count=args.routes, contracts_dir=ROOT / "contracts")
        print(json.dumps({"pack_id": manifest["id"], "counts": manifest["counts"],
            "content_hash": manifest["content_hash"], "output": str(args.out.resolve()),
            "status": "local-only; per-topology license terms still need human review"}, indent=2))
        return 0
    except (PackError, OSError, ValueError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

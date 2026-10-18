"""Makes graph_replay/training/sequences.json: the training routes Precog learns from.

Run from the repo root (backend environment on):   python graph/tools/generate_sequences.py
Options: --count 300  --seed 0  --out PATH
The same seed always gives the same file.
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "graph"))
sys.path.insert(0, str(REPO_ROOT / "lead-core" / "backend"))

from graph_net import TOPOLOGY_FILE, Topology, load_hosts  # noqa: E402
from graph_replay import TRAINING_FILE, generate_sequences  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=str(TRAINING_FILE))
    args = parser.parse_args(argv)
    topology = Topology.from_files(load_hosts(REPO_ROOT / "contracts" / "data" / "hosts.json"), TOPOLOGY_FILE)
    result = generate_sequences(topology, count=args.count, seed=args.seed)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    first_hops = {}
    for sequence in result["sequences"]:
        if len(sequence["path"]) >= 2 and sequence["path"][0] == "host-a":
            first_hops[sequence["path"][1]] = first_hops.get(sequence["path"][1], 0) + 1
    print("Wrote %d sequences (seed %d, engine %s) to %s" % (result["count"], result["seed"], topology.engine, args.out))
    print("From host-a the attacker's first move was: %s" % ", ".join("%s %d" % kv for kv in sorted(first_hops.items(), key=lambda kv: -kv[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

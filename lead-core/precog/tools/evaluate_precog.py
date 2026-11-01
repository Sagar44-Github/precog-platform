"""Trains and evaluates the Precog node-level model on GRAPH's training sequences, and saves the evaluated model.

Run from the repo root (backend environment on):   python lead-core/precog/tools/evaluate_precog.py
Options: --seed 0   --test-fraction 0.2   --out lead-core/precog/results
Writes: precog_engine/data/node_model.json (the model the product uses), results/precog_evaluation.json, results/precog_experiments.csv
The same seed always gives the same numbers.
"""
import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
for folder in ("lead-core/precog", "lead-core/backend", "graph"):
    sys.path.insert(0, str(REPO_ROOT / folder))

from graph_net import TOPOLOGY_FILE, Topology, load_hosts  # noqa: E402
from precog_engine import MODEL_FILE  # noqa: E402
from precog_engine.evaluation import evaluate  # noqa: E402
from precog_engine.model import file_sha256  # noqa: E402

NOTES = ("The training sequences are made by GRAPH's scripted generator (four attacker styles over a six-host demo network), not by real attackers. "
         "The numbers measure how well the model learned that generator's habits on sequences it never saw, and are NOT a claim about real intrusions. "
         "Containment success equals precision@1 (contain the top host) or precision@3 (contain the Top-3) by construction in this replay setting. "
         "The numbers come only from held-out sequences, never from the rehearsed golden path. "
         "On this six-host network at most three hosts can be reached from any host, so a Top-3 list nearly always contains every candidate: "
         "precision@3 is about 1.0 for EVERY method and says nothing. Judge the model by precision@1, by calibration, and by its gap to the baselines, "
         "and read that gap against the standard error given with precision@1.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--out", default=str(REPO_ROOT / "lead-core" / "precog" / "results"))
    args = parser.parse_args(argv)

    training = REPO_ROOT / "graph" / "graph_replay" / "training" / "sequences.json"
    data = json.loads(training.read_text(encoding="utf-8"))
    topology = Topology.from_files(load_hosts(REPO_ROOT / "contracts" / "data" / "hosts.json"), TOPOLOGY_FILE)
    model, result = evaluate(data["sequences"], lambda here, path: topology.candidates(here, exclude=path), topology.edge_probability,
                             seed=args.seed, test_fraction=args.test_fraction)
    model.meta.update({"training_file_sha256": file_sha256(training), "training_file_seed": data["seed"], "generator": data["generator"], "topology_engine": topology.engine})
    model.save(MODEL_FILE)
    result.update({"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "training_file_sha256": model.meta["training_file_sha256"], "notes": NOTES})
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "precog_evaluation.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    log_file = out / "precog_experiments.csv"
    new = not log_file.exists()
    with open(log_file, "a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        if new:
            writer.writerow(["timestamp_utc", "seed", "alpha", "train_sequences", "test_forecasts", "model_p1", "model_p3", "model_ece", "rule_p1", "rule_p3", "uniform_p1", "uniform_p3"])
        m, r, u = result["node_model"], result["baseline_rule_based"], result["baseline_uniform"]
        writer.writerow([result["generated_at"], args.seed, result["alpha"]["chosen"], result["split"]["training_sequences"], result["split"]["test_forecasts"],
                         m["precision_at_1"], m["precision_at_3"], m["expected_calibration_error"], r["precision_at_1"], r["precision_at_3"], u["precision_at_1"], u["precision_at_3"]])
    print("Held-out forecasts: %d (from %d test sequences; %d training sequences; alpha %s)" % (result["split"]["test_forecasts"], result["split"]["test_sequences"], result["split"]["training_sequences"], result["alpha"]["chosen"]))
    print("%-22s %12s %12s %8s" % ("", "precision@1", "precision@3", "ECE"))
    for key, label in (("node_model", "Markov node model"), ("baseline_rule_based", "rule-based baseline"), ("baseline_uniform", "uniform baseline")):
        row = result[key]
        print("%-22s %12.4f %12.4f %8s" % (label, row["precision_at_1"], row["precision_at_3"], row["expected_calibration_error"]))
    print("Largest candidate list in the test forecasts: %d hosts; precision@1 standard error: %.4f" % (result["node_model"]["max_candidates"], result["node_model"]["precision_at_1_std_error"]))
    print("Saved the model to %s and the results to %s" % (MODEL_FILE, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

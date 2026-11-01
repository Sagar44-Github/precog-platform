"""Exports the technique-level Markov table from the forecasting repository, ONCE, in its own environment (TRD DD-9).

Repository: https://github.com/mayank02raj/MITRE-ATTACK-based-Attack-Chain-Prediction   (permission by email; cite the repository and its paper)
What this does, honestly: that repository is one big script (AP_Prob_Rs_3_Scenarios_Latest.py) with paths of its author's computer that
imports PyTorch at the top and starts training when it is run, so it cannot be imported. This tool therefore reads the script's SOURCE TEXT,
cuts out only the repository's own functions it needs (af_sequences_from_file and train_markov_from_sequences, unchanged) and runs them
on the repository's own Attack Flow data files. PyTorch is never imported and nothing is trained.

Run (any Python 3.9 or newer, standard library only):
    python lead-core/precog/tools/export_technique_markov.py --repo PATH_TO_THE_CLONED_REPOSITORY
Options: --commit TEXT (recorded in the file; read from git when not given)   --out PATH
"""
import argparse
import ast
import glob
import json
import logging
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

SCRIPT = "AP_Prob_Rs_3_Scenarios_Latest.py"
WANTED_FUNCTIONS = ("af_sequences_from_file", "train_markov_from_sequences")
WANTED_CONSTANTS = ("MIN_CHAIN_LEN",)
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "precog_engine" / "data" / "technique_markov.json"
ID_PATTERN = re.compile(r"^T\d{4}(\.\d{3})?$")


class AnyTechniqueId(dict):
    """Stands in for the repository's id-to-name table: every ATT&CK id maps to itself, so its functions return technique IDS."""

    def __contains__(self, key):
        return isinstance(key, str) and bool(ID_PATTERN.match(key))

    def __getitem__(self, key):
        return key


def load_repo_functions(script_path):
    """Compiles only the wanted functions and constants out of the repository script, without running anything else in it."""
    source = Path(script_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in WANTED_FUNCTIONS:
            keep.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in WANTED_CONSTANTS for t in node.targets):
            keep.append(node)
    found = {n.name for n in keep if isinstance(n, ast.FunctionDef)}
    if found != set(WANTED_FUNCTIONS):
        raise SystemExit("The repository script no longer contains: %s" % ", ".join(sorted(set(WANTED_FUNCTIONS) - found)))
    namespace = {"json": json, "os": os, "re": re, "Counter": Counter, "defaultdict": defaultdict, "List": List, "Dict": Dict, "log": logging.getLogger("repo-functions")}
    exec(compile(ast.Module(body=keep, type_ignores=[]), script_path, "exec"), namespace)
    return namespace


def names_from_flows(files):
    """technique id -> a readable name, taken from the 'name' of the attack actions in the flow files."""
    names = {}
    for path in files:
        try:
            objects = json.loads(Path(path).read_text(encoding="utf-8")).get("objects", [])
        except (OSError, ValueError):
            continue
        for obj in objects:
            if isinstance(obj, dict) and obj.get("type") == "attack-action" and ID_PATTERN.match(str(obj.get("technique_id", ""))) and obj.get("name"):
                names.setdefault(obj["technique_id"], obj["name"])
    return names


def split_at_non_ids(sequences):
    """Some flow steps have no ATT&CK id (the repository falls back to their free-text name). Our forecasts speak in ATT&CK ids only,
    so each sequence is cut at such a step: two ids that were never next to each other are never joined. Returns (segments of ids, cut count)."""
    segments, cut = [], 0
    for sequence in sequences:
        current = []
        for step in sequence:
            if ID_PATTERN.match(str(step)):
                current.append(step)
            else:
                cut += 1
                if len(current) >= 2:
                    segments.append(current)
                current = []
        if len(current) >= 2:
            segments.append(current)
    return segments, cut


def export(repo_dir, commit=None):
    repo_dir = Path(repo_dir)
    functions = load_repo_functions(repo_dir / SCRIPT)
    files = sorted(glob.glob(str(repo_dir / "Attack flows" / "*.json")))
    if not files:
        raise SystemExit("No Attack Flow files found in %s" % (repo_dir / "Attack flows"))
    sequences = []
    for path in files:
        _name, found = functions["af_sequences_from_file"](path, AnyTechniqueId())
        sequences.extend(found)
    sequences, free_text_steps = split_at_non_ids(sequences)
    start_prob, next_prob, n_starts, n_transitions = functions["train_markov_from_sequences"](sequences)
    if commit is None:
        try:
            commit = subprocess.run(["git", "-C", str(repo_dir), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            commit = "unknown"
    return {
        "meta": {"source": "https://github.com/mayank02raj/MITRE-ATTACK-based-Attack-Chain-Prediction", "commit": commit, "data": "the repository's own 'Attack flows' folder (Attack Flow STIX files)",
                 "flow_files": len(files), "sequences": len(sequences), "free_text_steps_cut_out": free_text_steps, "start_states": n_starts, "unique_transitions": n_transitions,
                 "repository_functions_used": list(WANTED_FUNCTIONS), "markov": "first-order, unsmoothed, exactly as in train_markov_from_sequences, trained on ATT&CK-id steps only (sequences are cut at steps that have no id)",
                 "notice": "Used with the author's permission (by email). Cite the repository and its paper. Do not redistribute the repository's code outside the project without the author's agreement."},
        "names": names_from_flows(files),
        "start_prob": {k: round(v, 6) for k, v in sorted(start_prob.items())},
        "next_prob": {a: {b: round(p, 6) for b, p in sorted(row.items())} for a, row in sorted(next_prob.items())},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True, help="the cloned repository folder")
    parser.add_argument("--commit")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    table = export(args.repo, args.commit)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8")
    m = table["meta"]
    print("Wrote %s: %d flow files, %d sequences, %d techniques with a next step, %d transitions (PyTorch was not needed)" % (args.out, m["flow_files"], m["sequences"], len(table["next_prob"]), m["unique_transitions"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

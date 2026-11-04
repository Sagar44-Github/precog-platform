import ast
import json
import sys
import types

import pytest
from flask import Flask

from addons.loader import ROLE_PACKAGES, register_addons
from precog_engine import MODEL_FILE, NodeModel
from precog_engine.evaluation import evaluate
from precog_engine.model import file_sha256
from precog_helpers import REPO_ROOT


@pytest.fixture()
def live(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_MODE", "live")
    monkeypatch.setenv("WEB_DIST", str(tmp_path / "no-web"))
    monkeypatch.delenv("FORECAST_SOURCE", raising=False)
    return Flask(__name__)


def test_the_loader_knows_the_precog_package():
    assert "precog_engine" in ROLE_PACKAGES


def test_registering_through_the_real_loader_gives_the_precog_hook(live):
    ctx = register_addons(live, REPO_ROOT, types.SimpleNamespace(), packages=("precog_engine",))
    assert live.extensions["precog"]["load_report"]["precog_engine"] == "registered"
    precog = ctx.hooks.get("precog")
    assert precog.describe() == {"node_model": "markov", "alpha": precog.model.alpha, "technique_source": "repo"}
    assert all(hasattr(precog, name) for name in ("reset", "on_compromise", "on_attempt"))


def test_forecast_source_lookup_and_a_bad_value(live, monkeypatch):
    monkeypatch.setenv("FORECAST_SOURCE", "lookup")
    assert register_addons(live, REPO_ROOT, types.SimpleNamespace(), packages=("precog_engine",)).hooks.get("precog").describe()["technique_source"] == "lookup"
    monkeypatch.setenv("FORECAST_SOURCE", "magic")
    register_addons(Flask(__name__), REPO_ROOT, types.SimpleNamespace(), packages=("precog_engine",))


def test_a_bad_forecast_source_is_reported_not_fatal(monkeypatch, tmp_path):
    monkeypatch.setenv("WEB_DIST", str(tmp_path / "no-web"))
    monkeypatch.setenv("FORECAST_SOURCE", "magic")
    app = Flask(__name__)
    register_addons(app, REPO_ROOT, types.SimpleNamespace(), packages=("precog_engine",))
    assert "FORECAST_SOURCE" in app.extensions["precog"]["load_report"]["precog_engine"]


# ---------- the shipped model and results ----------
def graph_available():
    try:
        import graph_net

        return hasattr(graph_net, "Topology")
    except ImportError:
        return False


needs_graph = pytest.mark.skipif(not graph_available(), reason="GRAPH's real package is not merged yet")


@needs_graph
def test_the_shipped_model_was_trained_on_the_current_training_file():
    model = NodeModel.load(MODEL_FILE)
    training = REPO_ROOT / "graph" / "graph_replay" / "training" / "sequences.json"
    assert model.meta["training_file_sha256"] == file_sha256(training)
    assert model.meta["training_sequences"] == 240 and model.alpha > 0


def test_file_sha256_normalizes_windows_line_endings(tmp_path):
    lf = tmp_path / "training-lf.json"
    crlf = tmp_path / "training-crlf.json"
    lf.write_bytes(b'{"sequences": []}\n')
    crlf.write_bytes(b'{"sequences": []}\r\n')
    assert file_sha256(lf) == file_sha256(crlf)


@needs_graph
def test_the_shipped_results_match_a_fresh_evaluation_and_are_honest():
    from graph_net import TOPOLOGY_FILE, Topology, load_hosts

    topology = Topology.from_files(load_hosts(REPO_ROOT / "contracts" / "data" / "hosts.json"), TOPOLOGY_FILE)
    sequences = json.loads((REPO_ROOT / "graph" / "graph_replay" / "training" / "sequences.json").read_text(encoding="utf-8"))["sequences"]
    candidates = lambda here, path: topology.candidates(here, exclude=path)
    model, fresh = evaluate(sequences, candidates, topology.edge_probability)
    shipped = json.loads((REPO_ROOT / "lead-core" / "precog" / "results" / "precog_evaluation.json").read_text(encoding="utf-8"))
    for key in ("node_model", "baseline_rule_based", "baseline_uniform", "split", "alpha", "containment_success"):
        assert fresh[key] == shipped[key]
    assert model.counts == NodeModel.load(MODEL_FILE).counts
    assert fresh["node_model"]["precision_at_1"] > fresh["baseline_uniform"]["precision_at_1"]
    assert fresh["node_model"]["max_candidates"] == 3 and "says nothing" in shipped["notes"] and "NOT a claim about real intrusions" in shipped["notes"]
    assert shipped["split"]["test_forecasts"] == fresh["node_model"]["forecasts"]


@needs_graph
def test_the_evaluation_is_repeatable_and_never_trains_on_the_test_sequences():
    from graph_net import TOPOLOGY_FILE, Topology, load_hosts
    from precog_engine.model import split_sequences

    topology = Topology.from_files(load_hosts(REPO_ROOT / "contracts" / "data" / "hosts.json"), TOPOLOGY_FILE)
    sequences = json.loads((REPO_ROOT / "graph" / "graph_replay" / "training" / "sequences.json").read_text(encoding="utf-8"))["sequences"]
    candidates = lambda here, path: topology.candidates(here, exclude=path)
    first = evaluate(sequences, candidates, topology.edge_probability, seed=3)[1]
    assert first == evaluate(sequences, candidates, topology.edge_probability, seed=3)[1]
    train, test = split_sequences(sequences, seed=3)
    assert len(train) + len(test) == len(sequences) and first["split"]["training_sequences"] == len(train)


def test_the_evaluation_core_works_on_a_tiny_hand_made_network():
    links = {"a": ["m", "n", "o"], "m": ["o"], "n": ["o"], "o": []}
    candidates = lambda here, path: [t for t in links[here] if t not in path]
    sequences = [{"profile": "p", "path": ["a", "o"]}] * 30 + [{"profile": "p", "path": ["a", "m", "o"]}] * 10   # "o" is the common move but sorts last
    model, result = evaluate(sequences, candidates, lambda s, t: 0.5)
    assert result["node_model"]["precision_at_1"] > result["baseline_uniform"]["precision_at_1"]
    assert result["node_model"]["max_candidates"] == 3 and result["node_model"]["share_with_more_than_3_candidates"] == 0.0
    assert result["node_model"]["precision_at_3"] == 1.0
    assert set(result) >= {"node_model", "baseline_rule_based", "baseline_uniform", "by_profile", "containment_success", "alpha", "split"}


# ---------- the export tool ----------
SCRIPT = '''import torch   # a heavy library the real script imports first: it must never be imported by the export tool
from collections import Counter, defaultdict
MIN_CHAIN_LEN = 2
def af_sequences_from_file(fp, ATTACK_ID_TO_NAME):
    data = json.load(open(fp, encoding="utf-8"))
    names = [o.get("technique_id") if o.get("technique_id") in ATTACK_ID_TO_NAME else o.get("name") for o in data["objects"]]
    return "flow", [names]
def train_markov_from_sequences(json_sequences):
    start_counts = Counter(); trans = defaultdict(Counter)
    for seq in json_sequences:
        start_counts[seq[0]] += 1
        for a, b in zip(seq[:-1], seq[1:]): trans[a][b] += 1
    total = sum(start_counts.values())
    return ({k: v / total for k, v in start_counts.items()}, {a: {b: c / sum(r.values()) for b, c in r.items()} for a, r in trans.items()}, len(start_counts), sum(len(r) for r in trans.values()))
raise SystemExit("the script must not be run")
'''


def fake_repo(tmp_path):
    (tmp_path / "Attack flows").mkdir()
    (tmp_path / "AP_Prob_Rs_3_Scenarios_Latest.py").write_text(SCRIPT, encoding="utf-8")
    steps = [("T1046", "Scan"), ("T1110", "Brute Force"), ("free text step", "free text step"), ("T1078", "Valid Accounts"), ("T1021", "Remote Services")]
    flow = {"objects": [{"type": "attack-action", "technique_id": t if t.startswith("T") else "", "name": n} for t, n in steps]}
    (tmp_path / "Attack flows" / "one.json").write_text(json.dumps(flow), encoding="utf-8")
    return tmp_path


def test_the_export_tool_uses_the_repositorys_functions_without_running_the_script_or_importing_torch(tmp_path):
    sys.path.insert(0, str(REPO_ROOT / "lead-core" / "precog" / "tools"))
    try:
        import export_technique_markov as tool
    finally:
        sys.path.pop(0)
    table = tool.export(fake_repo(tmp_path), commit="abc")
    assert "torch" not in sys.modules
    assert table["next_prob"] == {"T1046": {"T1110": 1.0}, "T1078": {"T1021": 1.0}}       # cut at the free-text step: T1110 is never joined to T1078
    assert table["meta"]["free_text_steps_cut_out"] == 1 and table["meta"]["commit"] == "abc" and table["names"]["T1110"] == "Brute Force"
    assert table["meta"]["repository_functions_used"] == ["af_sequences_from_file", "train_markov_from_sequences"]


def test_the_export_tool_refuses_a_repository_whose_functions_have_gone(tmp_path):
    sys.path.insert(0, str(REPO_ROOT / "lead-core" / "precog" / "tools"))
    import export_technique_markov as tool
    (tmp_path / "Attack flows").mkdir()
    (tmp_path / "AP_Prob_Rs_3_Scenarios_Latest.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="no longer contains"):
        tool.export(tmp_path)


def test_the_export_tool_on_the_real_repository_when_it_is_available(tmp_path):
    import os

    repo = os.environ.get("PRECOG_REPO_DIR")
    if not repo:
        pytest.skip("set PRECOG_REPO_DIR to the cloned forecasting repository to run this")
    sys.path.insert(0, str(REPO_ROOT / "lead-core" / "precog" / "tools"))
    import export_technique_markov as tool
    fresh = tool.export(repo)
    shipped = json.loads((REPO_ROOT / "lead-core" / "precog" / "precog_engine" / "data" / "technique_markov.json").read_text(encoding="utf-8"))
    assert fresh["next_prob"] == shipped["next_prob"]

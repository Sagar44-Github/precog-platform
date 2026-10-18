import json
import subprocess
import sys

from graph_helpers import REPO_ROOT


def run(script, *args):
    return subprocess.run([sys.executable, str(REPO_ROOT / "graph" / "tools" / script), *args], capture_output=True, text=True, timeout=120)


def test_validate_scenarios_says_all_ok():
    result = run("validate_scenarios.py")
    assert result.returncode == 0, result.stderr + result.stdout
    assert "all scenarios OK" in result.stdout and result.stdout.count("ok ") >= 4


def test_demo_with_containment_blocks_the_move():
    result = run("demo_replay.py")
    assert result.returncode == 0, result.stderr + result.stdout
    assert "contained the predicted host" in result.stdout and "was blocked" in result.stdout
    assert "server-b" in result.stdout and "Replay finished: finished" in result.stdout


def test_demo_without_containment_lets_the_attacker_in():
    result = run("demo_replay.py", "--no-contain")
    assert result.returncode == 0, result.stderr + result.stdout
    assert "succeeded" in result.stdout and "host-a -> server-b" in result.stdout


def test_generate_sequences_writes_the_same_file_as_the_one_shipped(tmp_path):
    out = tmp_path / "sequences.json"
    result = run("generate_sequences.py", "--out", str(out))
    assert result.returncode == 0, result.stderr
    shipped = (REPO_ROOT / "graph" / "graph_replay" / "training" / "sequences.json").read_text(encoding="utf-8")
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(shipped)

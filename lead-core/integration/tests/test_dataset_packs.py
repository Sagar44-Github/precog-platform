"""Safety, determinism, and legacy equivalence coverage for offline packs."""
import json
import sqlite3
from pathlib import Path

import pytest

from addons.dataset_packs import PackError, PackStore, build_demo6_pack, validate_existing_demo_equivalence, validate_pack

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "packs" / "demo-6"


def build_to(tmp_path):
    target = tmp_path / "demo-6"
    build_demo6_pack(ROOT, target, ROOT / "contracts")
    return target


def test_checked_in_demo_pack_matches_legacy_sources():
    manifest = validate_pack(PACK, ROOT / "contracts")
    summary = validate_existing_demo_equivalence(PACK, ROOT)
    assert manifest["id"] == "demo-6"
    assert manifest["counts"]["hosts"] == 6
    assert manifest["counts"]["edges"] == 11
    assert manifest["counts"]["routes"] == 300
    assert summary["model_equal"] and summary["scenarios_equal"] and summary["event_inputs_equal"]
    assert summary["evaluation_equal"] and summary["golden_path_unchanged"]


def test_pack_build_is_repeatable_except_creation_metadata(tmp_path):
    first = build_to(tmp_path / "first")
    second = build_to(tmp_path / "second")
    manifest_a = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    manifest_b = json.loads((second / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_a["content_hash"] == manifest_b["content_hash"]
    assert manifest_a["counts"] == manifest_b["counts"]
    assert (first / "routes.jsonl").read_bytes() == (second / "routes.jsonl").read_bytes()
    assert (first / "pack.sqlite").read_bytes() == (second / "pack.sqlite").read_bytes()


def test_validator_rejects_payload_tampering(tmp_path):
    target = build_to(tmp_path)
    (target / "card.md").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(PackError, match="content hash"):
        validate_pack(target, ROOT / "contracts")


def test_validator_rejects_unknown_scenario_host(tmp_path):
    target = build_to(tmp_path)
    path = target / "scenarios" / "quiet-scan.json"
    scenario = json.loads(path.read_text(encoding="utf-8"))
    scenario["events"][0]["host"] = "outside-host"
    path.write_text(json.dumps(scenario), encoding="utf-8")
    with pytest.raises(PackError, match="unknown host"):
        validate_pack(target, ROOT / "contracts")


def test_validator_rejects_model_transitions_to_unknown_hosts(tmp_path):
    target = build_to(tmp_path)
    model_path = target / "model.json"
    model = json.loads(model_path.read_text(encoding="utf-8"))
    model["counts"]["host-a"]["outside-host"] = 1
    model_path.write_text(json.dumps(model), encoding="utf-8")
    from addons.dataset_packs import _canonical_json, _payload_hash
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    manifest["content_hash"], manifest["size_bytes"] = _payload_hash(target)
    (target / "manifest.json").write_bytes(_canonical_json(manifest))
    with pytest.raises(PackError, match="invalid transition counts"):
        validate_pack(target, ROOT / "contracts")


def test_pack_store_rejects_traversal_and_lists_valid_packs(tmp_path):
    build_to(tmp_path)
    store = PackStore(tmp_path, ROOT / "contracts")
    assert store.open("demo-6").manifest["id"] == "demo-6"
    assert [item["id"] for item in store.list_packs()] == ["demo-6"]
    for unsafe in ("..", "../demo-6", "demo-6/../../x", "Demo-6"):
        with pytest.raises(PackError):
            store.open(unsafe)


def test_pack_event_stream_is_time_ordered_and_bounded():
    pack = PackStore(PACK.parent, ROOT / "contracts").open("demo-6")
    batches = list(pack.iter_events(batch_size=3))
    assert batches and all(len(batch) <= 3 for batch in batches)
    events = [event for batch in batches for event in batch]
    assert [event["t"] for event in events] == sorted(event["t"] for event in events)
    selected = [event for batch in pack.iter_events(start_t=1500, end_t=4500, batch_size=2) for event in batch]
    assert all(1500 <= event["t"] <= 4500 for event in selected)
    with pytest.raises(ValueError, match="batch_size"):
        list(pack.iter_events(batch_size=10001))


def test_pack_validator_rejects_symlinked_contents(tmp_path):
    target = build_to(tmp_path)
    try:
        (target / "outside.json").symlink_to(target / "manifest.json")
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable on this Windows account")
    with pytest.raises(PackError, match="symbolic links"):
        validate_pack(target, ROOT / "contracts")


def test_pack_preserves_four_scenarios_and_label_records():
    pack = PackStore(PACK.parent, ROOT / "contracts").open("demo-6")
    files = sorted(path.stem for path in (PACK / "scenarios").glob("*.json"))
    expected = sorted(path.stem for path in (ROOT / "graph/graph_replay/scenarios").glob("*.json"))
    assert files == expected and len(files) == 4
    conn = sqlite3.connect(PACK / "pack.sqlite")
    try:
        assert conn.execute("SELECT COUNT(*) FROM windows").fetchone()[0] == 4
        assert conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0] == pack.manifest["counts"]["labelled_events"]
    finally:
        conn.close()

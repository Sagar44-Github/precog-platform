"""Fixture-only tests for the Phase D5 offline real-dataset adapters."""
import csv
import gzip
import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "lead-core" / "backend"))
from addons.dataset_packs import PackError, validate_pack
from addons.real_dataset_builders import SPECS, build_real_dataset_pack, parse_dataset
from tools.datasets.build_real_pack import _files, _verify_source_checksums
from tools.datasets.fetch import main as fetch_main


FLOW_HEADERS = {
    "cse-cic-ids2018": ["Timestamp", "Src IP", "Dst IP", "Protocol", "Src Port", "Dst Port", "Label"],
    "cic-ids2017": ["Timestamp", "Src IP", "Dst IP", "Protocol", "Src Port", "Dst Port", "Label"],
    "ctu-13": ["StartTime", "SrcAddr", "DstAddr", "Proto", "Sport", "Dport", "Label"],
    "cic-iot-2023": ["Timestamp", "IPV4_SRC_ADDR", "IPV4_DST_ADDR", "PROTOCOL", "L4_SRC_PORT", "L4_DST_PORT", "Attack_type"],
    "ton-iot": ["ts", "src_ip", "dst_ip", "proto", "src_port", "dst_port", "type"],
    "unsw-nb15": ["srcip", "dstip", "proto", "sport", "dsport", "attack_cat"],
    "cidds-001": ["Date first seen", "Src IP Addr", "Dst IP Addr", "Proto", "Src Pt", "Dst Pt", "Class", "AttackType"],
}


def _flow_values(dataset_id, row):
    start, src, dst, proto, sport, dport, label = row
    if dataset_id == "ctu-13":
        return [str(start), src, dst, proto, str(sport), str(dport), label]
    if dataset_id == "cic-iot-2023":
        return [str(start), src, dst, "6", str(sport), str(dport), label]
    if dataset_id == "ton-iot":
        return [str(start), src, dst, proto, str(sport), str(dport), label]
    if dataset_id == "unsw-nb15":
        return [src, dst, proto, str(sport), str(dport), label]
    if dataset_id == "cidds-001":
        return [str(start), src, dst, proto, str(sport), str(dport), "Attacker", label]
    return [str(start), src, dst, proto, str(sport), str(dport), label]


def _write_flow_fixture(path, dataset_id):
    headers = FLOW_HEADERS[dataset_id]
    rows = [
        (1, "8.8.8.8", "10.0.0.1", "TCP", 50000, 22, "Brute Force"),
        (2, "10.0.0.1", "10.0.0.2", "TCP", 445, 445, "Infiltration"),
        (3, "10.0.0.2", "10.0.0.3", "TCP", 445, 445, "Infiltration"),
        (4, "10.0.0.3", "10.0.0.4", "UDP", 3000, 53, "Normal"),
        (5, "10.0.0.4", "10.0.0.1", "TCP", 443, 443, "Benign"),
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(_flow_values(dataset_id, row) for row in rows)


@pytest.mark.parametrize("dataset_id", sorted(FLOW_HEADERS))
def test_source_specific_flow_headers_normalize_without_raw_files_in_repo(tmp_path, dataset_id):
    fixture = tmp_path / (dataset_id + ".csv")
    _write_flow_fixture(fixture, dataset_id)
    rows = parse_dataset(dataset_id, [fixture])
    assert len(rows) == 5
    assert rows[0]["raw_src"] == "8.8.8.8"
    assert rows[0]["semantic"] == "access-attempt"
    assert rows[1]["semantic"] == "lateral-movement"
    if dataset_id == "cidds-001":
        assert rows[0]["label"] == "Brute Force"  # AttackType wins over Class=Attacker.
    output = tmp_path / dataset_id
    manifest = build_real_dataset_pack(dataset_id, [fixture], output, max_hosts=10, max_events=20, contracts_dir=ROOT / "contracts")
    validate_pack(output, ROOT / "contracts")
    assert manifest["counts"]["events"] == 5
    assert manifest["capabilities"]["detection_labels"] == "native"


def test_lanl_gzip_auth_and_redteam_fixture_yields_native_routes(tmp_path):
    auth, redteam = tmp_path / "auth.txt.gz", tmp_path / "redteam.txt.gz"
    with gzip.open(auth, "wt", encoding="utf-8", newline="") as stream:
        stream.write("100,U1@D,U2@D,C1,C2,Kerberos,Network,LogOn,Success\n")
        stream.write("200,U2@D,U3@D,C2,C3,Kerberos,Network,LogOn,Success\n")
    with gzip.open(redteam, "wt", encoding="utf-8", newline="") as stream:
        stream.write("100,U1@D,C1,C2\n")
        stream.write("200,U1@D,C2,C3\n")
    rows = parse_dataset("lanl-cyber1", [auth, redteam])
    assert sum(bool(row.get("is_redteam")) for row in rows) == 2
    output = tmp_path / "lanl-cyber1"
    manifest = build_real_dataset_pack("lanl-cyber1", [auth, redteam], output, max_hosts=10, max_events=20, contracts_dir=ROOT / "contracts")
    validate_pack(output, ROOT / "contracts")
    assert manifest["capabilities"]["lateral_movement_routes"] == "derived"
    assert manifest["counts"]["routes"] == 1
    serialized = b"".join(path.read_bytes() for path in output.rglob("*") if path.is_file())
    assert b"U1@D" not in serialized and b"u1-d" not in serialized and b"C1" not in serialized


def test_lanl_host_cap_prioritizes_redteam_endpoints(tmp_path):
    auth, redteam = tmp_path / "auth.txt", tmp_path / "redteam.txt"
    auth.write_text("".join("%d,U9@D,U8@D,NOISY-A,NOISY-B,Kerberos,Network,LogOn,Success\n" % i for i in range(20)) +
        "999,U1@D,U2@D,C1,C2,Kerberos,Network,LogOn,Success\n", encoding="utf-8")
    redteam.write_text("999,U1@D,C1,C2\n", encoding="utf-8")
    manifest = build_real_dataset_pack("lanl-cyber1", [auth, redteam], tmp_path / "lanl-cyber1",
        max_hosts=2, max_events=50, contracts_dir=ROOT / "contracts")
    assert manifest["counts"]["hosts"] == 2
    assert manifest["counts"]["routes"] == 1


def test_cic_flow_pack_is_deterministic_bounded_and_pseudonymized(tmp_path):
    source = tmp_path / "input.csv"
    _write_flow_fixture(source, "cic-ids2017")
    first = build_real_dataset_pack("cic-ids2017", [source], tmp_path / "cic-ids2017", seed=7,
        max_hosts=10, max_events=20, contracts_dir=ROOT / "contracts")
    second = build_real_dataset_pack("cic-ids2017", [source], tmp_path / "copy" / "cic-ids2017", seed=7,
        max_hosts=10, max_events=20, contracts_dir=ROOT / "contracts")
    assert first["content_hash"] == second["content_hash"]
    assert first["counts"]["hosts"] <= 10 and first["counts"]["events"] <= 20
    assert first["capabilities"]["lateral_movement_routes"] == "derived"
    assert first["source_file_checksums"][0]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    evaluation = json.loads((tmp_path / "cic-ids2017" / "evaluation.json").read_text(encoding="utf-8"))
    assert evaluation["detector_evaluation"]["status"] == "computed-trivial-label-playback"
    assert evaluation["precog_evaluation"]["status"] == "requires-at-least-five-routes"
    payload = b"".join(path.read_bytes() for path in (tmp_path / "cic-ids2017").rglob("*") if path.is_file())
    assert b"8.8.8.8" not in payload and b"8-8-8-8" not in payload and b"10.0.0.1" not in payload


def test_impact_only_labels_do_not_claim_host_compromise(tmp_path):
    source = tmp_path / "impact.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(FLOW_HEADERS["cic-ids2017"])
        writer.writerow(_flow_values("cic-ids2017", (1, "8.8.8.8", "10.0.0.1", "TCP", 50000, 80, "DDoS")))
    manifest = build_real_dataset_pack("cic-ids2017", [source], tmp_path / "cic-ids2017",
        max_hosts=10, max_events=20, contracts_dir=ROOT / "contracts")
    assert manifest["capabilities"]["detection_labels"] == "native"
    assert manifest["capabilities"]["host_compromise"] == "none"
    assert manifest["capabilities"]["lateral_movement_routes"] == "none"


def test_unsw_nb15_does_not_infer_ordered_routes(tmp_path):
    source = tmp_path / "unsw.csv"
    _write_flow_fixture(source, "unsw-nb15")
    manifest = build_real_dataset_pack("unsw-nb15", [source], tmp_path / "unsw-nb15",
        max_hosts=10, max_events=20, contracts_dir=ROOT / "contracts")
    assert manifest["counts"]["routes"] == 0
    assert manifest["capabilities"]["lateral_movement_routes"] == "none"


def test_builder_rejects_unknown_sources_unsafe_inputs_and_bad_bounds(tmp_path):
    with pytest.raises(PackError, match="Unknown real dataset"):
        parse_dataset("nope", [tmp_path / "missing.csv"])
    source = tmp_path / "input.csv"
    _write_flow_fixture(source, "cic-ids2017")
    with pytest.raises(PackError, match="outside"):
        build_real_dataset_pack("cic-ids2017", [source], tmp_path / "cic-ids2017", max_hosts=501)


def test_source_catalog_has_all_eight_d5_adapters():
    assert set(SPECS) == {"lanl-cyber1", "cse-cic-ids2018", "cic-ids2017", "ctu-13",
        "cic-iot-2023", "ton-iot", "unsw-nb15", "cidds-001"}


def test_fetch_hash_manifest_is_required_and_verified_before_pack_build(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    fixture = raw / "flows.csv"
    _write_flow_fixture(fixture, "cic-ids2017")
    digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
    staged = tmp_path / "staged"
    assert fetch_main(["--source", "cic-ids2017", "--raw-dir", str(raw), "--out", str(staged),
                       "--sha256", "flows.csv=" + digest]) == 0
    files = _files([str(staged)])
    _verify_source_checksums([str(staged)], files, "cic-ids2017")
    manifest = build_real_dataset_pack("cic-ids2017", files, tmp_path / "pack" / "cic-ids2017",
        max_hosts=10, max_events=20, contracts_dir=ROOT / "contracts")
    assert manifest["source_file_checksums"][0]["sha256"] == digest
    (staged / "flows.csv").write_text("changed", encoding="utf-8")
    with pytest.raises(PackError, match="hash changed"):
        _verify_source_checksums([str(staged)], _files([str(staged)]), "cic-ids2017")

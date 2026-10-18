import datetime

import pytest

from addons.contracts import ContractError
from detect_helpers import packet
from detect_events import EventProcessor, packet_to_dict
from detect_events.events import to_iso_utc


# ---------- packets ----------
def test_only_alerts_become_events(processor):
    rows = [packet(id=1, severity="NORMAL", alert=False), packet(id=2, severity="HIGH"),
            packet(id=3, severity="MEDIUM"), packet(id=4, severity="LOW"), packet(id=5, severity=None)]
    events = processor.process_packets(rows)
    assert [e["packet_id"] for e in events] == [2, 3, 4]
    assert processor.skipped_unlabelled == 1


def test_event_fields_for_a_high_packet(processor, contracts):
    event = processor.process_packets([packet()])[0]
    contracts.validate("security_event", event)
    assert event["event_id"] == "evt-000001" and event["host"] == "host-a"
    assert event["ts"] == "2026-10-03T10:00:01Z" and event["packet_id"] == 1
    assert event["severity"] == "HIGH" and event["risk_score"] == 49.93
    assert event["technique_id"] == "T1021.004" and event["technique_name"] == "SSH"
    assert event["source"] == "nids_detector" and event["anomaly"] is False  # NIDS anomaly value 1 = not an outlier


def test_anomaly_flag_follows_nids_minus_one(processor):
    assert processor.process_packets([packet(anomaly=-1)])[0]["anomaly"] is True


def test_port_without_a_hint_gives_no_technique(processor):
    event = processor.process_packets([packet(dst_port=9999, severity="LOW")])[0]
    assert event["technique_id"] is None and event["technique_name"] is None


def test_unknown_source_address_is_kept_as_the_host(processor):
    assert processor.process_packets([packet(src_ip="10.9.9.9")])[0]["host"] == "10.9.9.9"


def test_bad_scores_are_handled(processor):
    events = processor.process_packets([
        packet(id=1, risk_score=250), packet(id=2, risk_score=-5), packet(id=3, risk_score=None),
        packet(id=4, risk_score=float("nan")), packet(id=5, risk_score="oops")])
    assert [e["risk_score"] for e in events] == [100.0, 0.0, 90.0, 90.0, 90.0]


def test_event_numbers_count_up_and_reset(processor):
    first = processor.process_packets([packet()])[0]
    second = processor.process_packets([packet(id=2)])[0]
    assert (first["event_id"], second["event_id"]) == ("evt-000001", "evt-000002")
    processor.reset()
    assert processor.process_packets([packet(id=3)])[0]["event_id"] == "evt-000001"


def test_events_reach_the_world_state_and_the_audit_log(processor, world, audit):
    event = processor.process_packets([packet()])[0]
    assert world.alerts()[0]["event_id"] == event["event_id"]
    entry = audit.read_all()[0]
    assert entry["type"] == "detection" and entry["ref_id"] == event["event_id"] and "HIGH alert on host-a" in entry["summary"]


def test_reset_clears_the_audit_log_unless_told_not_to(processor, audit):
    processor.process_packets([packet()])
    processor.reset(clear_audit=False)
    assert len(audit.read_all()) == 1
    processor.reset()
    assert audit.read_all() == []


def test_missing_fields_do_not_crash(processor):
    event = processor.process_packets([{"severity": "HIGH"}])[0]
    assert event["host"] == "unknown"
    assert event["explanation"].startswith("Unknown host sent a unknown-byte network packet")


def test_threat_actor_values_from_nids_are_never_copied(processor):
    row = packet(threat_actor="APT29", asn="AS1 (Evil)", location="Russia")
    text = str(processor.process_packets([row])[0])
    assert "APT29" not in text and "Russia" not in text and "Evil" not in text


def test_packet_to_dict_copies_the_fields_we_need():
    class FakePacket:
        id, timestamp, src_ip, dst_ip, protocol = 7, datetime.datetime(2026, 10, 3, 10, 0, 1), "a", "b", "TCP"
        src_port, dst_port, packet_size, flags = 1, 2, 3, "S"
        anomaly, risk_score, suspicious_port, alert, severity = -1, 60.0, True, True, "HIGH"
        threat_actor = "SIMULATED"

    row = packet_to_dict(FakePacket())
    assert row["id"] == 7 and row["severity"] == "HIGH" and "threat_actor" not in row


def test_a_real_datetime_from_nids_works(processor):
    event = processor.process_packets([packet(timestamp=datetime.datetime(2026, 10, 3, 10, 0, 1))])[0]
    assert event["ts"] == "2026-10-03T10:00:01Z"


# ---------- times ----------
@pytest.mark.parametrize("given,expected", [
    ("2026-10-03 10:00:01", "2026-10-03T10:00:01Z"),
    ("2026-10-03T10:00:01Z", "2026-10-03T10:00:01Z"),
    ("2026-10-03T15:30:01+05:30", "2026-10-03T10:00:01Z"),
    ("2026-10-03 10:00:01.123456", "2026-10-03T10:00:01Z"),
])
def test_times_are_converted_to_utc_text(given, expected):
    assert to_iso_utc(given) == expected


@pytest.mark.parametrize("bad", [None, "", "not a time", 12345])
def test_unreadable_times_become_now_not_an_error(bad):
    assert to_iso_utc(bad).endswith("Z") and len(to_iso_utc(bad)) == 20


# ---------- technique events ----------
def test_technique_event(processor, contracts):
    event = processor.process_technique("host-a", "T1110", note="Repeated failed logins", compromise=True)
    contracts.validate("security_event", event)
    assert event["source"] == "scripted" and event["packet_id"] is None and event["anomaly"] is True
    assert event["severity"] == "HIGH" and event["risk_score"] == 90.0
    assert event["technique_name"] == "Brute Force" and "now treated as compromised" in event["explanation"]


def test_technique_event_severity_and_score_options(processor):
    event = processor.process_technique("host-b", "T1046", severity="LOW")
    assert event["severity"] == "LOW" and event["risk_score"] == 35.0
    assert processor.process_technique("host-b", "T1046", risk_score=77)["risk_score"] == 77.0


def test_typos_in_scenarios_fail_loudly(processor):
    with pytest.raises(ValueError):
        processor.process_technique("host-z", "T1110")
    with pytest.raises(ValueError):
        processor.process_technique("host-a", "T0000")
    with pytest.raises(ValueError):
        processor.process_technique("host-a", "T1110", severity="CRITICAL")


def test_a_failed_technique_event_does_not_use_up_an_event_number(processor):
    with pytest.raises(ValueError):
        processor.process_technique("host-a", "T0000")
    assert processor.process_technique("host-a", "T1110")["event_id"] == "evt-000001"


# ---------- shared services ----------
def test_other_roles_can_write_audit_lines_through_the_processor(processor, audit):
    entry = processor.audit_record("containment", "act-000001", "Containment of server-b proposed")
    assert entry["type"] == "containment" and audit.read_all()[-1]["ref_id"] == "act-000001"


def test_processor_works_without_a_world_or_audit(hosts, techniques):
    bare = EventProcessor(hosts, techniques)
    assert bare.process_packets([packet()])[0]["event_id"] == "evt-000001"
    assert bare.audit_record("detection", "x", "y") is None
    bare.reset()


def test_contract_checking_catches_a_bad_event(hosts, techniques, contracts):
    class BrokenHosts(type(hosts)):
        def host_or_address(self, address):
            return ""  # an empty host breaks the security_event contract

    checked = EventProcessor(BrokenHosts([{"host_id": "a", "name": "A", "address": "1.1.1.1"}]), techniques, contracts=contracts)
    with pytest.raises(ContractError):
        checked.process_packets([packet()])

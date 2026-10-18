import json

import pytest

from detect_events import HostMap, TechniqueTable
from detect_events.explain import explain_packet, explain_technique, service_name


# ---------- hosts ----------
def test_demo_network_has_six_hosts_with_unique_addresses(hosts):
    assert len(hosts.host_ids()) == 6
    assert hosts.host_for_address("192.168.1.11") == "host-a"
    assert hosts.host_for_address("192.168.1.20") == "server-b"


def test_names_for_ids_and_addresses(hosts):
    assert hosts.name_of("host-a") == "Workstation A"
    assert hosts.name_of("192.168.1.50") == "Domain Controller"
    assert hosts.name_of("8.8.8.8") == "8.8.8.8"  # unknown values come back unchanged
    assert hosts.name_of(None) == "Unknown host" and hosts.name_of("") == "Unknown host"


def test_unknown_address_is_still_shown(hosts):
    assert hosts.host_for_address("10.9.9.9") is None
    assert hosts.host_or_address("10.9.9.9") == "10.9.9.9"
    assert hosts.host_or_address(None) == "unknown"


def test_bad_host_lists_are_refused():
    good = {"host_id": "a", "name": "A", "address": "1.1.1.1"}
    with pytest.raises(ValueError):
        HostMap([good, dict(good, name="B", address="2.2.2.2")])         # duplicate id
    with pytest.raises(ValueError):
        HostMap([good, dict(good, host_id="b", name="B")])               # duplicate address
    with pytest.raises(ValueError):
        HostMap([dict(good, name="")])                                   # empty name
    with pytest.raises(ValueError):
        HostMap([])                                                      # no hosts at all


# ---------- techniques ----------
def test_table_has_the_techniques_with_official_names(techniques):
    assert len(techniques.ids()) == 26
    assert techniques.get("T1110")["name"] == "Brute Force"
    assert techniques.get("T1021.004")["name"] == "SSH"
    assert techniques.get("T1021.004")["tactics"] == ["lateral-movement"]
    assert techniques.get("T9999") is None


def test_require_gives_a_helpful_error(techniques):
    with pytest.raises(ValueError) as info:
        techniques.require("T9999")
    assert "T9999" in str(info.value) and "T1110" in str(info.value)


def test_port_hints_cover_the_ports_nids_treats_as_suspicious(techniques):
    nids_suspicious_ports = {22, 23, 3389, 445, 135, 137, 138, 139, 4444, 6666, 31337}
    assert set(techniques.hinted_ports()) == nids_suspicious_ports


def test_port_hints_are_service_based_and_honest(techniques):
    assert techniques.technique_for_port(3389)["id"] == "T1021.001"
    assert techniques.technique_for_port(31337)["id"] == "T1571"
    assert techniques.technique_for_port(137) is None       # no defensible mapping
    assert techniques.technique_for_port(443) is None       # not suspicious at all


def test_every_technique_has_a_tactic_and_an_official_link(techniques):
    for technique_id in techniques.ids():
        technique = techniques.get(technique_id)
        assert technique["tactics"], technique_id
        assert technique["url"].startswith("https://attack.mitre.org/techniques/T")


def test_the_mitre_notice_is_kept_with_the_data(techniques):
    assert "MITRE Corporation" in techniques.meta["notice"]


def test_a_port_hint_to_an_unknown_technique_is_refused():
    data = {"techniques": [{"id": "T1", "name": "x", "tactics": ["a"]}], "port_hints": {"22": "T2"}}
    with pytest.raises(ValueError):
        TechniqueTable(data)


def test_duplicate_technique_ids_are_refused():
    item = {"id": "T1", "name": "x", "tactics": ["a"]}
    with pytest.raises(ValueError):
        TechniqueTable({"techniques": [item, item]})


# ---------- explanations ----------
def test_packet_explanation_is_plain_english_and_mentions_the_technique(techniques):
    text = explain_packet("Workstation A", "Workstation B", "TCP", 22, 2500, "HIGH", techniques.technique_for_port(22))
    assert text.startswith("Workstation A sent a 2500-byte TCP packet to port 22 (SSH, remote login) on Workstation B.")
    assert "NIDS rated it high risk." in text and "SSH (T1021.004)" in text and "lateral movement" in text


def test_packet_explanation_without_a_technique_makes_no_claim():
    text = explain_packet("Workstation A", "Workstation B", "UDP", 9999, 100, "LOW")
    assert "Traffic like this" not in text and "T1" not in text


def test_threat_actor_names_never_appear_in_explanations(techniques):
    for port in (22, 4444, 31337):
        text = explain_packet("A", "B", "TCP", port, 1, "HIGH", techniques.technique_for_port(port))
        assert "APT29" not in text and "Lazarus" not in text and "FIN7" not in text


def test_technique_explanation_and_compromise_sentence(techniques):
    text = explain_technique("Workstation A", techniques.get("T1110"), "Repeated failed logins.", compromise=True)
    assert "Brute Force (T1110)" in text and "credential access" in text
    assert "Repeated failed logins." in text and "Workstation A is now treated as compromised." in text
    assert ".." not in text


def test_service_names():
    assert service_name(3389) == "Remote Desktop"
    assert service_name(12345) is None

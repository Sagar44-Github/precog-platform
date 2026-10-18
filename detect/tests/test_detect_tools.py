"""The helper scripts in detect/tools."""
import json
import subprocess
import sys

import pytest

from detect_helpers import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "detect" / "tools"))
import build_attack_table  # noqa: E402


def fake_bundle(revoked=False):
    objects = [{"type": "x-mitre-collection", "x_mitre_version": "99.9"}]
    for technique_id, name, phase in (("T1110", "Brute Force", "credential-access"), ("T1046", "Network Service Discovery", "discovery")):
        item = {"type": "attack-pattern", "name": name, "kill_chain_phases": [{"phase_name": phase}],
                "external_references": [{"source_name": "mitre-attack", "external_id": technique_id}]}
        if revoked and technique_id == "T1046":
            item["revoked"] = True
        objects.append(item)
    return {"objects": objects}


def test_table_is_built_from_a_bundle():
    table = build_attack_table.build_table(fake_bundle(), ["T1110", "T1046"], {"22": "T1110", "137": None})
    assert table["meta"]["source"] == "MITRE ATT&CK Enterprise, version 99.9"
    assert [t["id"] for t in table["techniques"]] == ["T1110", "T1046"]
    assert table["techniques"][0]["tactics"] == ["credential-access"]
    assert table["techniques"][0]["url"] == "https://attack.mitre.org/techniques/T1110/"
    assert "MITRE Corporation" in table["meta"]["notice"]


def test_sub_technique_links_use_a_slash():
    bundle = fake_bundle()
    bundle["objects"].append({"type": "attack-pattern", "name": "SSH", "kill_chain_phases": [{"phase_name": "lateral-movement"}],
                              "external_references": [{"source_name": "mitre-attack", "external_id": "T1021.004"}]})
    table = build_attack_table.build_table(bundle, ["T1021.004"], {})
    assert table["techniques"][0]["url"] == "https://attack.mitre.org/techniques/T1021/004/"


def test_unknown_or_revoked_techniques_stop_the_build():
    with pytest.raises(SystemExit):
        build_attack_table.build_table(fake_bundle(), ["T0000"], {})
    with pytest.raises(SystemExit):
        build_attack_table.build_table(fake_bundle(revoked=True), ["T1046"], {})


def test_the_shipped_table_matches_the_builders_lists(techniques):
    assert techniques.ids() == build_attack_table.TECHNIQUE_IDS
    assert {str(p) for p in techniques.hinted_ports()} == set(build_attack_table.PORT_HINTS)


def test_demo_script_runs_and_prints_alerts():
    result = subprocess.run([sys.executable, str(REPO_ROOT / "detect" / "tools" / "demo_events.py")],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "evt-000001" in result.stdout and "evt-000003" in result.stdout and "audit log" in result.stdout
    assert "Brute Force (T1110)" in result.stdout

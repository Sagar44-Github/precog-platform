import json
import re

import pytest

from precog_engine import TechniqueLayer
from precog_helpers import DATA

ID = re.compile(r"^T\d{4}(\.\d{3})?$")
MARKOV = {"names": {"T1016": "System Network Configuration Discovery", "T1190": "Exploit"}, "next_prob": {"T1046": {"T1016": 0.5, "T1049": 0.5}, "T1059": {"T1105": 1.0}}}
LOOKUP = {"names": {"T1078": "Valid Accounts", "T1021": "Remote Services"}, "next": {"T1110": [{"id": "T1078", "probability": 0.5}], "T1021": [{"id": "T1021", "probability": 0.4}]}}


def test_the_shipped_rule_table_is_valid():
    table = json.loads((DATA / "technique_lookup.json").read_text(encoding="utf-8"))
    assert len(table["next"]) == 26
    for technique, options in table["next"].items():
        assert ID.match(technique) and technique in table["names"]
        assert all(o["id"] in table["names"] for o in options)
        assert not options or abs(sum(o["probability"] for o in options) - 1) < 1e-9
    assert table["names"]["T1110"] == "Brute Force" and "NOT learned" in table["meta"]["what"]


def test_the_shipped_exported_table_is_valid_and_says_where_it_came_from():
    table = json.loads((DATA / "technique_markov.json").read_text(encoding="utf-8"))
    meta = table["meta"]
    assert "mayank02raj/MITRE-ATTACK-based-Attack-Chain-Prediction" in meta["source"] and len(meta["commit"]) == 40
    assert meta["flow_files"] == 39 and meta["sequences"] > 1000 and meta["repository_functions_used"] == ["af_sequences_from_file", "train_markov_from_sequences"]
    assert "permission" in meta["notice"]
    for technique, row in table["next_prob"].items():
        assert ID.match(technique) and abs(sum(row.values()) - 1) < 1e-3 and all(ID.match(n) for n in row)


def test_a_hint_has_id_name_and_probability_and_records_its_source():
    layer = TechniqueLayer(MARKOV, LOOKUP)
    hint, source = layer.hint("T1046")
    assert source == "repo" and hint["technique_id"] in ("T1016", "T1049") and hint["probability"] == 0.5 and hint["technique_name"]


def test_a_sub_technique_falls_back_to_its_parent():
    hint, source = TechniqueLayer(MARKOV, LOOKUP).hint("T1059.001")
    assert (hint["technique_id"], source) == ("T1105", "repo")


def test_when_the_exported_table_does_not_know_a_technique_the_rule_table_answers_and_says_so():
    hint, source = TechniqueLayer(MARKOV, LOOKUP).hint("T1110")
    assert (hint["technique_id"], hint["technique_name"], source) == ("T1078", "Valid Accounts", "lookup")


def test_lookup_can_be_forced_or_be_the_only_table():
    assert TechniqueLayer(MARKOV, LOOKUP, prefer="lookup").hint("T1110")[1] == "lookup"
    assert TechniqueLayer(None, LOOKUP).hint("T1110")[1] == "lookup"
    assert TechniqueLayer(MARKOV, LOOKUP, prefer="lookup").default_source == "lookup"
    assert TechniqueLayer(MARKOV, LOOKUP).default_source == "repo"


def test_no_hint_when_nothing_is_known():
    assert TechniqueLayer(MARKOV, LOOKUP).hint("T9999") == (None, "repo")
    assert TechniqueLayer(None, None).hint("T1110") == (None, "lookup")
    assert TechniqueLayer(MARKOV, LOOKUP).hint(None)[0] is None


def test_missing_files_are_not_an_error(tmp_path):
    layer = TechniqueLayer.load(tmp_path / "no.json", tmp_path / "no2.json")
    assert layer.markov is None and layer.lookup is None


def test_the_real_files_give_a_hint_for_the_golden_path_techniques():
    layer = TechniqueLayer.load(DATA / "technique_markov.json", DATA / "technique_lookup.json")
    for technique in ("T1046", "T1110", "T1021.004", "T1190"):
        hint, source = layer.hint(technique)
        assert hint is not None and source in ("repo", "lookup")

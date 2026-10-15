"""Every contract has a schema and a sample, and the samples follow the schemas."""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from addons.contracts import ContractError, Contracts

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"
EXPECTED = {
    "packet_record", "security_event", "graph_snapshot", "forecast", "containment_action", "reeval_result",
    "audit_entry", "world_state", "session_record", "session_metrics", "replay_status", "detection_report",
}


@pytest.fixture(scope="module")
def contracts():
    return Contracts(CONTRACTS_DIR)


def sample(name):
    return json.loads((CONTRACTS_DIR / "samples" / (name + ".sample.json")).read_text(encoding="utf-8"))


def test_the_minimum_contract_set_exists(contracts):
    assert EXPECTED <= set(contracts.names())


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_schema_is_valid_json_schema(contracts, name):
    Draft202012Validator.check_schema(json.loads((CONTRACTS_DIR / "schemas" / (name + ".schema.json")).read_text(encoding="utf-8")))


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_sample_follows_its_schema(contracts, name):
    contracts.validate(name, sample(name))


def test_unknown_extra_field_is_rejected(contracts):
    bad = sample("security_event")
    bad["surprise"] = 1
    with pytest.raises(ContractError):
        contracts.validate("security_event", bad)


def test_wrong_severity_is_rejected(contracts):
    bad = sample("security_event")
    bad["severity"] = "SEVERE"
    with pytest.raises(ContractError):
        contracts.validate("security_event", bad)


def test_forecast_allows_at_most_three_targets(contracts):
    bad = sample("forecast")
    bad["targets"] = bad["targets"] + [{"rank": 3, "host_id": "db-server", "confidence": 0.01}]
    with pytest.raises(ContractError):
        contracts.validate("forecast", bad)


def test_confidence_must_be_between_zero_and_one(contracts):
    bad = sample("forecast")
    bad["targets"][0]["confidence"] = 74
    with pytest.raises(ContractError):
        contracts.validate("forecast", bad)


def test_changed_world_state_needs_every_part(contracts):
    bad = sample("world_state")
    del bad["graph"]
    with pytest.raises(ContractError):
        contracts.validate("world_state", bad)


def test_unchanged_poll_reply_is_tiny_and_valid(contracts):
    contracts.validate("world_state", {"version": 7, "changed": False})


def test_world_state_checks_the_parts_inside_it(contracts):
    bad = copy.deepcopy(sample("world_state"))
    bad["alerts"][0]["severity"] = "SEVERE"
    with pytest.raises(ContractError):
        contracts.validate("world_state", bad)


def test_every_schema_has_a_sample():
    schema_names = {p.name[: -len(".schema.json")] for p in (CONTRACTS_DIR / "schemas").glob("*.schema.json")}
    sample_names = {p.name[: -len(".sample.json")] for p in (CONTRACTS_DIR / "samples").glob("*.sample.json")}
    assert schema_names == sample_names

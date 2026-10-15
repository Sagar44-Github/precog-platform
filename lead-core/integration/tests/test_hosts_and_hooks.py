"""The shared host list and the plug-in socket's list of hooks."""
import ipaddress
import json
from pathlib import Path

import pytest

from addons.errors import ApiError
from addons.hooks import KNOWN_HOOKS, Hooks

HOSTS_FILE = Path(__file__).resolve().parents[3] / "contracts" / "data" / "hosts.json"
SAMPLES = Path(__file__).resolve().parents[3] / "contracts" / "samples"


@pytest.fixture(scope="module")
def hosts():
    return json.loads(HOSTS_FILE.read_text(encoding="utf-8"))


def test_six_hosts_with_every_field(hosts):
    assert len(hosts["hosts"]) == 6
    for host in hosts["hosts"]:
        assert set(host) == {"host_id", "name", "zone", "address", "role"}
        assert host["zone"] in ("user", "dmz", "internal")


def test_ids_and_addresses_are_unique_and_addresses_are_inside_the_subnet(hosts):
    ids = [h["host_id"] for h in hosts["hosts"]]
    addresses = [h["address"] for h in hosts["hosts"]]
    assert len(set(ids)) == 6 and len(set(addresses)) == 6
    network = ipaddress.ip_network(hosts["subnet"])
    assert all(ipaddress.ip_address(a) in network for a in addresses)


def test_the_samples_use_the_same_hosts_and_zones(hosts):
    graph = json.loads((SAMPLES / "graph_snapshot.sample.json").read_text(encoding="utf-8"))
    listed = {h["host_id"]: (h["name"], h["zone"]) for h in hosts["hosts"]}
    sampled = {h["host_id"]: (h["name"], h["zone"]) for h in graph["hosts"]}
    assert listed == sampled


def test_all_six_hooks_are_known():
    assert KNOWN_HOOKS == ("replay", "events", "graph", "precog", "containment", "push")


@pytest.mark.parametrize("name", KNOWN_HOOKS)
def test_every_known_hook_can_be_registered_and_found(name):
    hooks = Hooks()
    assert not hooks.has(name)
    with pytest.raises(ApiError) as info:
        hooks.require(name)
    assert info.value.status == 501
    hooks.register(name, object())
    assert hooks.has(name) and hooks.registered() == [name]


def test_unknown_hook_names_are_refused():
    with pytest.raises(ValueError):
        Hooks().register("telepathy", object())

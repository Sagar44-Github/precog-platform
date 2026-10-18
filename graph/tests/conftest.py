"""Test set-up for GRAPH's backend-side tests (run from the repo root with plain 'pytest')."""
import pytest

from graph_helpers import REPO_ROOT, Rig  # noqa: F401  (importing it also sets up the paths)
from addons.contracts import Contracts
from addons.world_state import WorldState
from graph_net import TOPOLOGY_FILE, LiveGraph, Topology, load_hosts
from graph_replay import ScenarioLibrary


@pytest.fixture(scope="session")
def contracts():
    return Contracts(REPO_ROOT / "contracts")


@pytest.fixture(scope="session")
def hosts():
    return load_hosts(REPO_ROOT / "contracts" / "data" / "hosts.json")


@pytest.fixture(scope="session")
def topology(hosts):
    return Topology.from_files(hosts, TOPOLOGY_FILE)


@pytest.fixture()
def world(contracts):
    return WorldState(contracts)


@pytest.fixture()
def graph(topology, world):
    return LiveGraph(topology, world=world)


@pytest.fixture(scope="session")
def library(hosts):
    return ScenarioLibrary(known_hosts={h["host_id"] for h in hosts})


@pytest.fixture()
def rig(world, graph, library, hosts):
    made = Rig(world, graph, library, hosts)
    yield made
    made.controller.stop()

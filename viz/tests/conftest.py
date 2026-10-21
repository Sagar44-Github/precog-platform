"""Test set-up for VIZ's backend-side tests (run from the repo root with plain 'pytest')."""
import pytest

from viz_helpers import REPO_ROOT, Rig  # noqa: F401  (importing it also sets up the paths)
from addons.contracts import Contracts
from addons.world_state import WorldState


@pytest.fixture(scope="session")
def contracts():
    return Contracts(REPO_ROOT / "contracts")


@pytest.fixture()
def world(contracts):
    return WorldState(contracts)


@pytest.fixture()
def rig(world, contracts):
    made = Rig(world, contracts)
    yield made
    made.service.shutdown()

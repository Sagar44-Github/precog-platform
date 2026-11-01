"""Test set-up for the Precog tests (run from the repo root with plain 'pytest')."""
import pytest

from precog_helpers import REPO_ROOT, Rig  # noqa: F401  (importing it also sets up the paths)
from addons.contracts import Contracts


@pytest.fixture(scope="session")
def contracts():
    return Contracts(REPO_ROOT / "contracts")


@pytest.fixture()
def rig(contracts, tmp_path):
    return Rig(contracts, sessions_dir=tmp_path / "sessions")

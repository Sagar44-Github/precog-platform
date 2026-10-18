"""Test set-up for DETECT's backend-side tests (run from the repo root with plain 'pytest')."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]  # the repo root
sys.path.insert(0, str(REPO_ROOT / "lead-core" / "backend"))
sys.path.insert(0, str(REPO_ROOT / "detect"))

from addons.contracts import Contracts  # noqa: E402
from addons.world_state import WorldState  # noqa: E402
from detect_events import AuditLog, EventProcessor, HostMap, TechniqueTable  # noqa: E402
from detect_events import TECHNIQUES_FILE  # noqa: E402


@pytest.fixture(scope="session")
def contracts():
    return Contracts(REPO_ROOT / "contracts")


@pytest.fixture()
def hosts():
    return HostMap.from_file(REPO_ROOT / "contracts" / "data" / "hosts.json")


@pytest.fixture()
def techniques():
    return TechniqueTable.from_file(TECHNIQUES_FILE)


@pytest.fixture()
def world(contracts):
    return WorldState(contracts)


@pytest.fixture()
def audit(tmp_path, contracts):
    return AuditLog(tmp_path / "audit" / "audit.jsonl", contracts)


@pytest.fixture()
def processor(hosts, techniques, audit, world, contracts):
    return EventProcessor(hosts, techniques, audit=audit, world=world, contracts=contracts)

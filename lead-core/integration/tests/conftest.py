"""Test set-up. Runs before every test file.

Environment variables are set BEFORE the backend is imported, because NIDS reads its
database address at import time. Each test run uses a fresh temporary database.
"""
import os

import sys

import tempfile
from pathlib import Path

import pytest


BACKEND = Path(__file__).resolve().parents[2] / "backend"
REPO_ROOT = BACKEND.parent.parent

\
_tmp = tempfile.mkdtemp(prefix="precog-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(_tmp) / "test.db").as_posix()

os.environ["SECRET_KEY"] = "test-secret-key-not-for-real-use"

os.environ["ADMIN_PASSWORD"] = "test-admin-password"

os.environ["DATA_MODE"] = "sample"

os.environ["VALIDATE_CONTRACTS"] = "1"

os.environ["AUTO_TRAIN_MODEL"] = "1"

os.environ["WEB_DIST"] = str(Path(_tmp) / "no-dist-here")

sys.path.insert(0, str(BACKEND))

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture(scope="session")

def flask_app():
    from run_app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def ctx(flask_app):
    return flask_app.extensions["precog"]


@pytest.fixture()
def world(ctx):
    """The world state, reset to the sample data before every test."""
    from addons.sample_loader import load_samples

    ctx["world"].reset()
    load_samples(ctx["world"], ctx["config"].contracts_dir)
    return ctx["world"]


@pytest.fixture()
def hooks(ctx):
    """The hooks object, emptied before and after the test so stand-ins never leak."""
    ctx["hooks"]._items.clear()
    yield ctx["hooks"]
    ctx["hooks"]._items.clear()


@pytest.fixture()
def client(flask_app, world):
    return flask_app.test_client()


@pytest.fixture()
def logged_in(client):
    reply = client.post("/api/x/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert reply.status_code == 200, reply.get_data(as_text=True)
    return client

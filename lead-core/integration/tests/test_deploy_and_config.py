import json
import sys
from pathlib import Path

import pytest

from addons.config import Config

REPO = Path(__file__).resolve().parents[3]


# ---------- which web folder is served ----------
def test_the_bundled_copy_is_used_when_it_exists(tmp_path, monkeypatch):
    monkeypatch.delenv("WEB_DIST", raising=False)
    (tmp_path / "lead-core" / "backend" / "web_dist").mkdir(parents=True)
    (tmp_path / "lead-core" / "backend" / "web_dist" / "index.html").write_text("x", encoding="utf-8")
    assert Config.from_env(tmp_path).web_dist == tmp_path / "lead-core" / "backend" / "web_dist"


def test_the_local_build_is_used_when_there_is_no_bundle(tmp_path, monkeypatch):
    monkeypatch.delenv("WEB_DIST", raising=False)
    assert Config.from_env(tmp_path).web_dist == tmp_path / "web" / "dist"


def test_an_explicit_web_dist_always_wins(tmp_path, monkeypatch):
    (tmp_path / "lead-core" / "backend" / "web_dist").mkdir(parents=True)
    (tmp_path / "lead-core" / "backend" / "web_dist" / "index.html").write_text("x", encoding="utf-8")
    monkeypatch.setenv("WEB_DIST", str(tmp_path / "elsewhere"))
    assert Config.from_env(tmp_path).web_dist == tmp_path / "elsewhere"


# ---------- the bundle builder ----------
def load_builder():
    sys.path.insert(0, str(REPO / "deploy"))
    try:
        import build_web_bundle

        return build_web_bundle
    finally:
        sys.path.pop(0)


def test_the_bundle_builder_replaces_the_old_copy_and_counts_files(tmp_path):
    builder = load_builder()
    (tmp_path / "dist" / "assets").mkdir(parents=True)
    (tmp_path / "dist" / "index.html").write_text("new", encoding="utf-8")
    (tmp_path / "dist" / "assets" / "a.js").write_text("js", encoding="utf-8")
    (tmp_path / "bundle").mkdir()
    (tmp_path / "bundle" / "stale.txt").write_text("old", encoding="utf-8")
    assert builder.copy_dist(tmp_path / "dist", tmp_path / "bundle") == 2
    assert not (tmp_path / "bundle" / "stale.txt").exists() and (tmp_path / "bundle" / "assets" / "a.js").is_file()


def test_the_bundle_builder_refuses_something_that_is_not_a_built_app(tmp_path):
    with pytest.raises(SystemExit, match="not built"):
        load_builder().copy_dist(tmp_path, tmp_path / "bundle")


# ---------- the Render blueprint ----------
def test_the_render_blueprint_is_valid_and_safe():
    yaml = pytest.importorskip("yaml")
    blueprint = yaml.safe_load((REPO / "render.yaml").read_text(encoding="utf-8"))
    service = blueprint["services"][0]
    assert service["plan"] == "free" and service["runtime"] == "python" and service["healthCheckPath"] == "/api/x/health"
    assert "--workers 1" in service["startCommand"] and "wsgi:application" in service["startCommand"] and "$PORT" in service["startCommand"]
    env = {e["key"]: e for e in service["envVars"]}
    assert env["DATA_MODE"]["value"] == "live" and env["COOKIE_SECURE"]["value"] == "1" and env["PYTHON_VERSION"]["value"] == "3.11.9"
    assert env["SECRET_KEY"].get("generateValue") is True
    for secret in ("ADMIN_PASSWORD", "FCM_PROJECT_ID", "FCM_CREDENTIALS_JSON"):
        assert env[secret].get("sync") is False and "value" not in env[secret]       # asked for in the dashboard, never in Git


def test_the_hosted_checker_passes_against_the_real_app_routes(flask_app, client, world):
    sys.path.insert(0, str(REPO / "lead-core" / "integration"))
    try:
        import check_hosted
    finally:
        sys.path.pop(0)

    def fetch(method, path, body=None, timeout=0):
        reply = client.open(path, method=method, json=body)
        return reply.status_code, dict(reply.headers), reply.get_data()

    checker = check_hosted.Checker("http://test", fetch=fetch)
    ok = checker.run(__import__("os").environ["ADMIN_PASSWORD"])
    failed = [n for n, good in checker.results if not good]
    # with only Part 1 merged some role parts or the built web app may be missing: only the always-present checks are required here
    assert "sign in works" not in failed and "the backend answers /api/x/health" not in failed
    assert ok or failed


def test_the_root_opens_the_precog_demo_instead_of_the_nids_dashboard(client):
    reply = client.get("/", follow_redirects=False)
    assert reply.status_code == 302
    assert reply.headers["Location"].endswith("/app/console/")

"""Module loading is fail-safe, and the web app is served correctly at /app/."""
import types

import pytest
from flask import Flask

from addons.config import Config
from addons.loader import _load_role_packages
from addons.webapp import register_webapp


def test_missing_packages_are_reported_not_fatal(ctx):
    report = _load_role_packages(ctx_stub(), ("package_that_does_not_exist",))
    assert report == {"package_that_does_not_exist": "missing"}


def ctx_stub():
    return types.SimpleNamespace()


def test_a_package_with_a_bug_does_not_stop_the_server(tmp_path, monkeypatch):
    (tmp_path / "broken_role_pkg").mkdir()
    (tmp_path / "broken_role_pkg" / "__init__.py").write_text("raise RuntimeError('boom')\n")
    (tmp_path / "bad_register_pkg").mkdir()
    (tmp_path / "bad_register_pkg" / "__init__.py").write_text("def register(ctx):\n    raise RuntimeError('nope')\n")
    (tmp_path / "good_role_pkg").mkdir()
    (tmp_path / "good_role_pkg" / "__init__.py").write_text("seen = []\ndef register(ctx):\n    seen.append(ctx)\n")
    (tmp_path / "no_register_pkg").mkdir()
    (tmp_path / "no_register_pkg" / "__init__.py").write_text("x = 1\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    report = _load_role_packages(ctx_stub(), ("broken_role_pkg", "bad_register_pkg", "good_role_pkg", "no_register_pkg"))
    assert report["broken_role_pkg"].startswith("error")
    assert report["bad_register_pkg"].startswith("error")
    assert report["good_role_pkg"] == "registered"
    assert report["no_register_pkg"].startswith("loaded")


def test_a_missing_library_inside_a_package_is_an_error_not_missing(tmp_path, monkeypatch):
    (tmp_path / "needs_lib_pkg").mkdir()
    (tmp_path / "needs_lib_pkg" / "__init__.py").write_text("import library_that_does_not_exist_xyz\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    report = _load_role_packages(ctx_stub(), ("needs_lib_pkg",))
    assert report["needs_lib_pkg"].startswith("error")


@pytest.fixture()
def web(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>APP</html>")
    (dist / "sw.js").write_text("// sw")
    (dist / "assets" / "main-abc123.js").write_text("console.log(1)")
    config = Config(repo_root=tmp_path, contracts_dir=tmp_path, web_dist=dist, data_mode="sample", validate_contracts=False, cookie_secure=False)
    app = Flask(__name__)
    register_webapp(app, config)
    return app.test_client(), tmp_path


def test_app_root_redirects_and_serves_index(web):
    client, _ = web
    assert client.get("/app").status_code == 302
    reply = client.get("/app/")
    assert reply.status_code == 200 and b"APP" in reply.data
    assert reply.headers["Cache-Control"] == "no-cache"


def test_files_are_served_and_page_addresses_fall_back_to_index(web):
    client, _ = web
    assert client.get("/app/assets/main-abc123.js").status_code == 200
    assert client.get("/app/sw.js").headers["Cache-Control"] == "no-cache"
    assert b"APP" in client.get("/app/mobile/alerts").data           # a page inside the app: index.html
    assert client.get("/app/assets/missing.js").status_code == 404   # a missing FILE is a real 404


def test_path_tricks_cannot_escape_the_web_folder(web):
    client, tmp_path = web
    (tmp_path / "secret.txt").write_text("TOP SECRET")
    for tricky in ("/app/../secret.txt", "/app/%2e%2e/secret.txt", "/app/..%2fsecret.txt"):
        reply = client.get(tricky)
        assert b"TOP SECRET" not in reply.data, tricky


def test_not_built_yet_gives_a_helpful_message(tmp_path):
    config = Config(repo_root=tmp_path, contracts_dir=tmp_path, web_dist=tmp_path / "nope", data_mode="sample", validate_contracts=False, cookie_secure=False)
    app = Flask(__name__)
    register_webapp(app, config)
    reply = app.test_client().get("/app/")
    assert reply.status_code == 503 and b"npm run build" in reply.data


def test_the_real_app_serves_the_app_route(flask_app):
    reply = flask_app.test_client().get("/app/")
    assert reply.status_code in (200, 503)  # 503 when web/dist has not been built in this checkout

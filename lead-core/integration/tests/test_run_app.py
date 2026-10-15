"""Start-up helpers in run_app.py."""
import os

import pytest

import run_app


def test_env_file_is_read_and_existing_values_win(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('# a comment\nPRECOG_T1=one\nPRECOG_T2="two words"\n\nPRECOG_T3=\'three\'\nnot a setting line\nPRECOG_T4=from-file\n')
    monkeypatch.setenv("PRECOG_T4", "already-set")
    for key in ("PRECOG_T1", "PRECOG_T2", "PRECOG_T3"):
        monkeypatch.delenv(key, raising=False)
    run_app.load_env_file(env_file)
    assert os.environ["PRECOG_T1"] == "one"
    assert os.environ["PRECOG_T2"] == "two words"
    assert os.environ["PRECOG_T3"] == "three"
    assert os.environ["PRECOG_T4"] == "already-set"
    for key in ("PRECOG_T1", "PRECOG_T2", "PRECOG_T3"):
        os.environ.pop(key, None)


def test_a_missing_env_file_is_fine(tmp_path):
    run_app.load_env_file(tmp_path / "does-not-exist.env")


def test_missing_required_setting_stops_start_up_with_a_clear_message(monkeypatch):
    monkeypatch.delenv("PRECOG_NOT_SET", raising=False)
    with pytest.raises(SystemExit) as info:
        run_app.require_env("PRECOG_NOT_SET", "Fill it in.")
    assert "PRECOG_NOT_SET is missing" in str(info.value)


def test_ensure_admin_replaces_an_old_password(flask_app):
    import app as nids_app
    from database.models import SessionLocal, User

    run_app.ensure_admin(nids_app, "another-good-password")
    session = SessionLocal()
    user = session.query(User).filter_by(username="admin").first()
    assert nids_app.bcrypt.check_password_hash(user.password_hash, "another-good-password")
    assert session.query(User).filter_by(username="admin").count() == 1
    session.close()
    run_app.ensure_admin(nids_app, os.environ["ADMIN_PASSWORD"])  # put the test password back for the other tests

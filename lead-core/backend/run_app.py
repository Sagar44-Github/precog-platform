"""Starts the whole backend: NIDS (unchanged) plus our add-ons.

Run it from the repo root:   python lead-core/backend/run_app.py
It never edits a NIDS file. It imports NIDS's Flask app and adjusts it from the outside.
"""
import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent.parent
NIDS_DIR = BACKEND_DIR / "nids"
NIDS_DASHBOARD = NIDS_DIR / "dashboard"
DEFAULT_DB = BACKEND_DIR / "data" / "nids.db"
ADMIN_USERNAME = "admin"

log = logging.getLogger("precog.run")


def load_env_file(path):
    """Read KEY=VALUE lines from a .env file. Values already set in the environment win."""
    path = Path(path)
    
    if not path.is_file():
        return
    
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def require_env(name, hint):
    value = os.environ.get(name, "").strip()
    
    if not value:
        raise SystemExit("%s is missing. %s" % (name, hint))
    return value


def ensure_admin(nids_app, password):
    """Make sure the demo account exists and uses OUR password (never NIDS's default one)."""
    
    from database.models import SessionLocal, User

    session = SessionLocal()
    try:
        password_hash = nids_app.bcrypt.generate_password_hash(password).decode("utf-8")
        admin = session.query(User).filter_by(username=ADMIN_USERNAME).first()
        if admin is None:
            session.add(User(username=ADMIN_USERNAME, password_hash=password_hash))
        else:
            admin.password_hash = password_hash
        session.commit()
    
    finally:
        session.close()


def ensure_model():
    """NIDS's detector needs a trained model file. Train one (about 10 seconds) if it is missing."""
    ml_dir = NIDS_DIR / "ml"
    if (ml_dir / "nids_model.pkl").is_file() and (ml_dir / "label_encoder.pkl").is_file():
        return
    if os.environ.get("AUTO_TRAIN_MODEL", "1").strip().lower() in ("0", "false", "no", "off"):
        raise SystemExit("The NIDS model files are missing. Run: python lead-core/backend/nids/ml/train_model.py")
    log.warning("No trained model found, training one now ...")
    from ml.train_model import train_and_evaluate

    train_and_evaluate()


def create_app():
    load_env_file(REPO_ROOT / ".env")
    if not NIDS_DASHBOARD.is_dir():
        raise SystemExit("The NIDS copy was not found at %s" % NIDS_DIR)

    secret_key = require_env("SECRET_KEY", "Copy .env.example to .env and fill it in (see the build guide).")
    admin_password = require_env("ADMIN_PASSWORD", "Copy .env.example to .env and fill it in (see the build guide).")
    if len(admin_password) < 8:
        raise SystemExit("ADMIN_PASSWORD must be at least 8 characters long.")

    # The database address must be set BEFORE NIDS is imported (NIDS reads it at import time).
    if not os.environ.get("DATABASE_URL", "").strip():
        DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)
        os.environ["DATABASE_URL"] = "sqlite:///" + DEFAULT_DB.as_posix()

    # NIDS uses relative paths such as ../data/uploads, so it must run from its dashboard folder.
    sys.path.insert(0, str(NIDS_DIR))
    sys.path.insert(0, str(NIDS_DASHBOARD))
    os.chdir(NIDS_DASHBOARD)

    import app as nids_app  # NIDS's dashboard/app.py (we import it, we do not edit it)
    from database.models import Packet, SessionLocal, User, init_db

    flask_app = nids_app.app
    flask_app.secret_key = secret_key  # replaces NIDS's hard-coded key
    flask_app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0").strip().lower() in ("1", "true", "yes", "on"),
    )

    init_db()
    ensure_admin(nids_app, admin_password)
    ensure_model()

    from addons import register_addons

    nids = SimpleNamespace(SessionLocal=SessionLocal, User=User, Packet=Packet, bcrypt=nids_app.bcrypt, app_module=nids_app)
    register_addons(flask_app, REPO_ROOT, nids)
    return flask_app


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    flask_app = create_app()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    from waitress import serve

    print("Backend ready:  http://%s:%d/app/   (API: /api/x/health)" % (host, port))
    serve(flask_app, host=host, port=port, threads=4)  # waitress works on Windows; never debug mode


if __name__ == "__main__":
    main()

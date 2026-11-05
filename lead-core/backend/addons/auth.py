"""Login and add-on managed demo roles for the JSON web app."""
import json
import os
from collections import defaultdict, deque
from functools import wraps
from pathlib import Path
import threading
import time

from flask_login import current_user, login_user, logout_user

from .errors import ApiError

ROLE_NAMES = {"viewer": "Viewer", "analyst": "Analyst", "admin": "Administrator"}
ROLE_PERMISSIONS = {
    "viewer": {"can_contain": False, "can_run_replay": False, "can_release": False, "can_restart_replay": False},
    "analyst": {"can_contain": True, "can_run_replay": True, "can_release": False, "can_restart_replay": False},
    "admin": {"can_contain": True, "can_run_replay": True, "can_release": True, "can_restart_replay": True},
}


def role_for_user(user):
    """Resolve privileges from the authenticated NIDS account, never from request data."""
    username = getattr(user, "username", "")
    return username if username in ROLE_PERMISSIONS else "viewer"


def operator_profile(user):
    role = role_for_user(user)
    return {
        "status": "ok",
        "username": user.username,
        "role": role,
        "role_name": ROLE_NAMES[role],
        "permissions": dict(ROLE_PERMISSIONS[role]),
    }


def demo_role_required(*allowed_roles):
    """Require a signed-in demo operator with one of the named server-side roles."""
    def decorate(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                raise ApiError("not_logged_in", "Please log in first.", 401)
            if role_for_user(current_user) not in allowed_roles:
                raise ApiError("forbidden", "Your demo role cannot perform this action.", 403)
            return view(*args, **kwargs)
        return wrapper
    return decorate


ROLE_MAP_PATH = Path(__file__).with_name("role_map.json")
ROLE_LEVEL = {"viewer": 0, "analyst": 1, "admin": 2}
_RATE_LOCK = threading.Lock()
_RATE_BUCKETS = defaultdict(deque)


def _role_map():
    return json.loads(ROLE_MAP_PATH.read_text(encoding="utf-8"))["roles"]


def role_for_username(username):
    if not isinstance(username, str):
        return "viewer"
    for role, definition in _role_map().items():
        if username in definition.get("users", []):
            return role
    return "viewer"


def ensure_demo_accounts(nids):
    """Create optional analyst/viewer NIDS login rows from environment-only passwords."""
    session = nids.SessionLocal()
    try:
        for role, definition in _role_map().items():
            if role == "admin":
                continue  # run_app.py sets admin's password from ADMIN_PASSWORD.
            password = os.environ.get(definition.get("password_env", ""), "")
            if not password:
                continue
            if len(password) < 8:
                raise ValueError("%s must be at least 8 characters long when configured." % definition["password_env"])
            for username in definition.get("users", []):
                user = session.query(nids.User).filter_by(username=username).first()
                encoded = nids.bcrypt.generate_password_hash(password).decode("utf-8")
                if user is None:
                    session.add(nids.User(username=username, password_hash=encoded))
                else:
                    user.password_hash = encoded
        session.commit()
    finally:
        session.close()


def json_login_required(view):
    """Like NIDS's login_required, but answers 401 JSON instead of redirecting to a page."""

    @wraps(view)
    
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            raise ApiError("not_logged_in", "Please log in first.", 401)
        return view(*args, **kwargs)

    return wrapper


def check_login(nids, username, password):
    
    """Return the NIDS user object when the username and password are right, otherwise None."""
    
    if not isinstance(username, str) or not isinstance(password, str) or not username or not password:
        return None
    session = nids.SessionLocal()
    
    try:
        user = session.query(nids.User).filter_by(username=username).first()
    finally:
        session.close()
    
    if user is not None and nids.bcrypt.check_password_hash(user.password_hash, password):
        return user
    return None


def do_login(user):
    login_user(user)


def do_logout():
    logout_user()


def current_role():
    if not current_user.is_authenticated:
        return None
    return role_for_username(getattr(current_user, "username", None))


def info_for(username):
    role = role_for_username(username)
    return {
        "status": "ok", "username": username, "role": role,
        "role_name": {"viewer": "Viewer", "analyst": "Analyst", "admin": "Administrator"}[role],
        "read_only": role == "viewer",
        "permissions": {
            "can_contain": role != "viewer", "can_run_replay": role != "viewer",
            "can_release": role == "admin", "can_restart_replay": role == "admin",
        },
    }


def rate_limit(max_requests=30, window_seconds=60):
    """Small in-memory per-user/per-route sliding window for costly reads and exports."""
    if max_requests < 1 or window_seconds < 1:
        raise ValueError("Rate limit values must be positive.")

    def decorate(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            from flask import request

            identity = current_user.get_id() if current_user.is_authenticated else request.remote_addr or "anonymous"
            key = (identity, request.endpoint)
            now = time.monotonic()
            with _RATE_LOCK:
                bucket = _RATE_BUCKETS[key]
                while bucket and now - bucket[0] >= window_seconds:
                    bucket.popleft()
                if len(bucket) >= max_requests:
                    raise ApiError("rate_limited", "Too many requests. Wait a moment and try again.", 429)
                bucket.append(now)
            return view(*args, **kwargs)

        return wrapper

    return decorate


def role_required(minimum_role):
    if minimum_role not in ROLE_LEVEL:
        raise ValueError("Unknown role %r" % minimum_role)

    def decorate(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                raise ApiError("not_logged_in", "Please log in first.", 401)
            role = current_role()
            if ROLE_LEVEL[role] < ROLE_LEVEL[minimum_role]:
                raise ApiError(
                    "forbidden",
                    "The %s role needs analyst or admin access for this action." % role,
                    403,
                )
            return view(*args, **kwargs)

        return wrapper

    return decorate

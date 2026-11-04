"""Login for the web app.

NIDS has its own login page, which answers with redirects. A web app cannot use that cleanly,
so this adds a JSON login that uses NIDS's own user table, password check and session cookie.
"""
from functools import wraps

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

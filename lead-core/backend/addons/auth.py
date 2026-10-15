"""Login for the web app.

NIDS has its own login page, which answers with redirects. A web app cannot use that cleanly,
so this adds a JSON login that uses NIDS's own user table, password check and session cookie.
"""
from functools import wraps

from flask_login import current_user, login_user, logout_user

from .errors import ApiError


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

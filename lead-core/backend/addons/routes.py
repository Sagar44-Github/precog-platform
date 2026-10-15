"""All new routes. They live under /api/x so they never clash with NIDS's own routes.

Every error answers JSON like {"error": {"code": "...", "message": "..."}}.
"""
from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user
from werkzeug.exceptions import HTTPException

from . import auth
from .contracts import ContractError
from .errors import ApiError

bp = Blueprint("precog_addons", __name__, url_prefix="/api/x")

FORECAST_STATUSES = ("pending", "hit", "miss", "superseded")
REQUESTERS = ("console", "mobile")
MAX_ALERT_LIMIT = 200


def _ctx():
    return current_app.extensions["precog"]


def _body():
    data = request.get_json(silent=True)
    
    if not isinstance(data, dict):
        raise ApiError("bad_request", "Send a JSON object in the request body.", 400)
    return data


def _text(data, key, required=True):
    value = data.get(key)
    
    if value is None and not required:
        return None
    
    if not isinstance(value, str) or not value.strip():
        raise ApiError("bad_request", "'%s' must be a non-empty text value." % key, 400)
    return value.strip()


def _out(contract_name, data):
    """Check data we are about to send against its contract (when checking is switched on)."""
    ctx = _ctx()
    
    if ctx["contracts"] is not None:
        try:
            ctx["contracts"].validate(contract_name, data)
        except ContractError as exc:
            current_app.logger.error("Contract violation: %s", exc)
            raise ApiError("contract_violation", str(exc), 500)
    return data


@bp.errorhandler(Exception)
def _handle_errors(exc):
    
    if isinstance(exc, ApiError):
        return jsonify(exc.to_dict()), exc.status
    
    if isinstance(exc, HTTPException):
        return jsonify({"error": {"code": exc.name.lower().replace(" ", "_"), "message": exc.description}}), exc.code
    
    current_app.logger.exception("Unexpected error in /api/x")
    
    return jsonify({"error": {"code": "internal_error", "message": "Something went wrong on the server."}}), 500


# ---------- health and login ----------
@bp.get("/health")
def health():
    ctx = _ctx()
    
    return jsonify({
        "status": "ok", "data_mode": ctx["config"].data_mode, "version": ctx["world"].version,
        "hooks": ctx["hooks"].registered(), "modules": ctx["load_report"],
    })


@bp.post("/login")
def login():
    data = _body()
    user = auth.check_login(_ctx()["nids"], data.get("username"), data.get("password"))
    
    if user is None:
        raise ApiError("invalid_credentials", "Wrong username or password.", 401)
    auth.do_login(user)
    return jsonify({"status": "ok", "username": user.username})


@bp.post("/logout")
def logout():
    auth.do_logout()
    return jsonify({"status": "ok"})


@bp.get("/me")
@auth.json_login_required
def me():
    return jsonify({"status": "ok", "username": current_user.username})


# ---------- reading the state ----------
@bp.get("/state")
@auth.json_login_required
def state():
    since = request.args.get("since")
    if since is not None:
        try:
            since = int(since)
        except ValueError:
            raise ApiError("bad_request", "'since' must be a whole number.", 400)
    return jsonify(_out("world_state", _ctx()["world"].snapshot(since)))


@bp.get("/alerts")
@auth.json_login_required
def alerts():
    
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        raise ApiError("bad_request", "'limit' must be a whole number.", 400)
    
    limit = max(1, min(limit, MAX_ALERT_LIMIT))
    return jsonify(_ctx()["world"].alerts(limit))


@bp.get("/alerts/<event_id>")
@auth.json_login_required

def alert(event_id):
    found = _ctx()["world"].get_alert(event_id)
    if found is None:
        raise ApiError("not_found", "No alert with id %s." % event_id, 404)
    return jsonify(found)


@bp.get("/graph")
@auth.json_login_required

def graph():
    return jsonify(_out("graph_snapshot", _ctx()["world"].graph()))



@bp.get("/forecasts")
@auth.json_login_required
def forecasts():
    status = request.args.get("status")
    
    if status is not None and status not in FORECAST_STATUSES:
        raise ApiError("bad_request", "'status' must be one of: %s." % ", ".join(FORECAST_STATUSES), 400)
    return jsonify(_ctx()["world"].forecasts(status))


@bp.get("/forecasts/current")
@auth.json_login_required
def forecast_current():
    
    
    found = _ctx()["world"].current_forecast()
    
    if found is None:
    
        raise ApiError("no_forecast", "No forecast is pending.", 404)
    return jsonify(found)


# ---------- containment (needs the VIZ module) ----------
@bp.post("/containment/propose")
@auth.json_login_required

def containment_propose():
    ctx = _ctx()
    data = _body()
    target = _text(data, "target_host")
    forecast_id = _text(data, "forecast_id", required=False)
    requested_by = data.get("requested_by", "console")
    
    if requested_by not in REQUESTERS:
        raise ApiError("bad_request", "'requested_by' must be 'console' or 'mobile'.", 400)
    action = ctx["hooks"].require("containment").propose(ctx["world"], target, forecast_id, requested_by)
    
    return jsonify(_out("containment_action", action))


@bp.post("/containment/confirm")
@auth.json_login_required
def containment_confirm():
    ctx = _ctx()
    action = ctx["hooks"].require("containment").confirm(ctx["world"], _text(_body(), "action_id"))
    
    return jsonify(_out("containment_action", action))


@bp.post("/containment/cancel")
@auth.json_login_required
def containment_cancel():
    ctx = _ctx()
    action = ctx["hooks"].require("containment").cancel(ctx["world"], _text(_body(), "action_id"))
    return jsonify(_out("containment_action", action))


@bp.get("/containment/actions")
@auth.json_login_required
def containment_actions():
    return jsonify(_ctx()["world"].actions())


# ---------- session and metrics ----------
@bp.get("/session")
@auth.json_login_required
def session():
    found = _ctx()["world"].session()
    if found is None:
        raise ApiError("no_session", "There is no session yet.", 404)
    return jsonify(found)


@bp.get("/sessions")
@auth.json_login_required
def sessions():
    return jsonify(_ctx()["world"].sessions())


@bp.get("/metrics/precog")
@auth.json_login_required
def metrics_precog():
    return jsonify(_out("session_metrics", _ctx()["world"].metrics()))


@bp.get("/metrics/detection")
@auth.json_login_required
def metrics_detection():
    found = _ctx()["world"].detection_report()
    if found is None:
        raise ApiError("no_report", "No detection report has been loaded.", 404)
    return jsonify(found)


# ---------- replay (needs the GRAPH module) ----------
@bp.get("/replay/scenarios")
@auth.json_login_required
def replay_scenarios():
    return jsonify(_ctx()["hooks"].require("replay").list_scenarios())


@bp.get("/replay/status")
@auth.json_login_required
def replay_status():
    ctx = _ctx()
    replay = ctx["hooks"].get("replay")
    return jsonify(_out("replay_status", replay.status() if replay else ctx["world"].replay()))


@bp.post("/replay/start")
@auth.json_login_required
def replay_start():
    data = _body()
    scenario_id = _text(data, "scenario_id")
    speed = data.get("speed", 1.0)
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or speed <= 0:
        raise ApiError("bad_request", "'speed' must be a number above 0.", 400)
    return jsonify(_out("replay_status", _ctx()["hooks"].require("replay").start(scenario_id, float(speed))))


def _replay_action(name):
    status = getattr(_ctx()["hooks"].require("replay"), name)()
    return jsonify(_out("replay_status", status))


@bp.post("/replay/pause")
@auth.json_login_required
def replay_pause():
    return _replay_action("pause")


@bp.post("/replay/resume")
@auth.json_login_required
def replay_resume():
    return _replay_action("resume")


@bp.post("/replay/restart")
@auth.json_login_required
def replay_restart():
    return _replay_action("restart")


# ---------- push ----------
@bp.post("/push/register")
@auth.json_login_required
def push_register():
    ctx = _ctx()
    token = _text(_body(), "token")
    if len(token) > 4096:
        raise ApiError("bad_request", "That push token is too long.", 400)
    count = ctx["world"].add_push_token(token)
    push = ctx["hooks"].get("push")
    if push is not None:
        push.register(token)
    return jsonify({"status": "ok", "count": count})


# ---------- anything else under /api/x ----------
@bp.route("/<path:rest>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def not_found(rest):
    raise ApiError("not_found", "There is no endpoint '/api/x/%s' for this method." % rest, 404)

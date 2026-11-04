"""All new routes. They live under /api/x so they never clash with NIDS's own routes.

Every error answers JSON like {"error": {"code": "...", "message": "..."}}.
"""
import json
import platform
import sqlite3
from datetime import datetime, time, timedelta, timezone
from importlib.metadata import version as package_version

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
ALERT_SEVERITIES = ("HIGH", "MEDIUM", "LOW", "NORMAL")
AUDIT_TYPES = ("detection", "forecast", "containment")
PAGE_SORTS = ("ts", "risk_score", "severity")


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


def _date_filter(value, name, end_of_day=False):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if len(value) == 10 and end_of_day:
            parsed += timedelta(days=1) - timedelta(microseconds=1)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        raise ApiError("bad_request", "'%s' must be an ISO date or timestamp." % name, 400)


def _entry_time(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)


def _page_window(items, limit, cursor):
    try:
        offset = int(cursor) if cursor else 0
    except ValueError:
        raise ApiError("bad_request", "'cursor' must be a non-negative integer.", 400)
    if offset < 0:
        raise ApiError("bad_request", "'cursor' must be a non-negative integer.", 400)
    page = items[offset:offset + limit]
    next_cursor = str(offset + len(page)) if offset + len(page) < len(items) else None
    return page, next_cursor


def _query_text(name, max_length=256):
    value = request.args.get(name, "").strip()
    if len(value) > max_length:
        raise ApiError("bad_request", "'%s' is too long." % name, 400)
    return value


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


@bp.get("/alerts/search")
@auth.json_login_required
def alerts_search():
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        raise ApiError("bad_request", "'limit' must be a whole number.", 400)
    limit = max(1, min(limit, MAX_ALERT_LIMIT))
    severity = request.args.get("severity", "").upper()
    if severity and severity not in ALERT_SEVERITIES:
        raise ApiError("bad_request", "'severity' must be one of: %s." % ", ".join(ALERT_SEVERITIES), 400)
    sort = request.args.get("sort", "ts")
    order = request.args.get("order", "desc").lower()
    if sort not in PAGE_SORTS or order not in ("asc", "desc"):
        raise ApiError("bad_request", "Use a supported sort field and 'asc' or 'desc' order.", 400)
    filters = {
        "q": _query_text("q"), "severity": severity, "host": _query_text("host"),
        "technique": _query_text("technique"), "from": _query_text("from", 80),
        "to": _query_text("to", 80), "sort": sort, "order": order,
    }
    start = _date_filter(filters["from"], "from")
    end = _date_filter(filters["to"], "to", end_of_day=True)
    if start and end and start > end:
        raise ApiError("bad_request", "'from' must not be later than 'to'.", 400)
    query = filters["q"].casefold()
    host = filters["host"].casefold()
    technique = filters["technique"].casefold()
    rows = []
    for alert_row in _ctx()["world"].alerts(MAX_ALERT_LIMIT):
        ts = _entry_time(alert_row.get("ts"))
        searchable = " ".join(str(alert_row.get(key) or "") for key in ("host", "technique_id", "technique_name", "explanation", "event_id")).casefold()
        if severity and alert_row.get("severity") != severity:
            continue
        if host and host not in str(alert_row.get("host", "")).casefold():
            continue
        if technique and technique not in " ".join((str(alert_row.get("technique_id") or ""), str(alert_row.get("technique_name") or ""))).casefold():
            continue
        if query and query not in searchable:
            continue
        if start and ts < start:
            continue
        if end and ts > end:
            continue
        rows.append(alert_row)
    severity_rank = {"NORMAL": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    if sort == "ts":
        rows.sort(key=lambda row: (_entry_time(row.get("ts")), row.get("event_id", "")), reverse=order == "desc")
    elif sort == "risk_score":
        rows.sort(key=lambda row: (float(row.get("risk_score", 0)), row.get("event_id", "")), reverse=order == "desc")
    else:
        rows.sort(key=lambda row: (severity_rank.get(row.get("severity"), -1), row.get("event_id", "")), reverse=order == "desc")
    total = len(rows)
    page, next_cursor = _page_window(rows, limit, request.args.get("cursor", ""))
    payload = {"items": page, "total": total, "next_cursor": next_cursor, "limit": limit, "filters": filters}
    return jsonify(_out("alert_page", payload))


@bp.get("/alerts/<event_id>")
@auth.json_login_required

def alert(event_id):
    found = _ctx()["world"].get_alert(event_id)
    if found is None:
        raise ApiError("not_found", "No alert with id %s." % event_id, 404)
    return jsonify(found)


@bp.get("/assets")
@auth.json_login_required
def assets():
    ctx = _ctx()
    graph_hook = ctx["hooks"].get("graph")
    if graph_hook is None:
        raise ApiError("not_built", "The 'graph' part has not been built yet.", 501)
    try:
        host_file = ctx["config"].contracts_dir / "data" / "hosts.json"
        hosts = json.loads(host_file.read_text(encoding="utf-8"))["hosts"]
    except (OSError, KeyError, ValueError):
        raise ApiError("assets_unavailable", "The demo host inventory could not be loaded.", 503)
    live_hosts = {host["host_id"]: host for host in ctx["world"].graph().get("hosts", [])}
    items = []
    for host in hosts:
        host_id = host["host_id"]
        profile = graph_hook.topology.asset_profile(host_id)
        live = live_hosts.get(host_id, {})
        items.append({
            "host_id": host_id, "name": host["name"], "zone": host["zone"], "address": host["address"],
            "role": host["role"], "state": live.get("state", "normal"),
            "risk_score": round(graph_hook.topology.risk(host_id) * 10, 1),
            "criticality": profile["criticality"], "services": profile["services"],
            "weaknesses": profile["weaknesses"],
            "reachable_hosts": graph_hook.topology.connections(host_id),
            "state_history": ctx["world"].host_state_history(host_id),
        })
    return jsonify(_out("host_inventory", {"items": items, "total": len(items)}))


@bp.get("/audit")
@auth.json_login_required
def audit_entries():
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        raise ApiError("bad_request", "'limit' must be a whole number.", 400)
    limit = max(1, min(limit, MAX_ALERT_LIMIT))
    entry_type = request.args.get("type", "")
    if entry_type and entry_type not in AUDIT_TYPES:
        raise ApiError("bad_request", "'type' must be one of: %s." % ", ".join(AUDIT_TYPES), 400)
    filters = {
        "type": entry_type, "ref_id": _query_text("ref_id"), "q": _query_text("q"),
        "from": _query_text("from", 80), "to": _query_text("to", 80),
    }
    start = _date_filter(filters["from"], "from")
    end = _date_filter(filters["to"], "to", end_of_day=True)
    if start and end and start > end:
        raise ApiError("bad_request", "'from' must not be later than 'to'.", 400)
    events_hook = _ctx()["hooks"].get("events")
    audit_log = getattr(events_hook, "audit", None) if events_hook is not None else None
    if audit_log is None:
        raise ApiError("not_built", "The audit log is not available.", 501)
    try:
        rows = audit_log.read_all()
    except OSError:
        raise ApiError("audit_unavailable", "The audit log could not be read.", 503)
    query = filters["q"].casefold()
    ref_id = filters["ref_id"].casefold()
    rows = [row for row in rows if
        (not entry_type or row.get("type") == entry_type)
        and (not ref_id or ref_id in str(row.get("ref_id", "")).casefold())
        and (not query or query in str(row.get("summary", "")).casefold())
        and (not start or _entry_time(row.get("ts")) >= start)
        and (not end or _entry_time(row.get("ts")) <= end)]
    rows.sort(key=lambda row: (_entry_time(row.get("ts")), str(row.get("ref_id", ""))), reverse=True)
    total = len(rows)
    page, next_cursor = _page_window(rows, limit, request.args.get("cursor", ""))
    return jsonify(_out("audit_page", {"items": page, "total": total, "next_cursor": next_cursor, "limit": limit, "filters": filters}))


@bp.get("/system")
@auth.json_login_required
def system_status():
    ctx = _ctx()
    events_hook = ctx["hooks"].get("events")
    audit_path = getattr(getattr(events_hook, "audit", None), "path", None)
    payload = {
        "status": "ok", "data_mode": ctx["config"].data_mode, "world_version": ctx["world"].version,
        "hooks": ctx["hooks"].registered(), "modules": ctx["load_report"],
        "versions": {"python": platform.python_version(), "flask": package_version("Flask"), "sqlite": sqlite3.sqlite_version},
        "checks": {"contract_validation": ctx["contracts"] is not None, "audit_log_available": bool(audit_path and (audit_path.is_file() or audit_path.parent.is_dir()))},
    }
    return jsonify(_out("system_status", payload))


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

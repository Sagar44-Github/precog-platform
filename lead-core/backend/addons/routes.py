"""All new routes. They live under /api/x so they never clash with NIDS's own routes.

Every error answers JSON like {"error": {"code": "...", "message": "..."}}.
"""
import json
import platform
import sqlite3
import uuid
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
AUDIT_TYPES = ("detection", "forecast", "containment", "incident")
PAGE_SORTS = ("ts", "risk_score", "severity")
INCIDENT_STATUSES = ("open", "contained", "closed")


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


def _validate_input(contract_name, data):
    contracts = _ctx()["contracts"]
    if contracts is not None:
        try:
            contracts.validate(contract_name, data)
        except ContractError as exc:
            raise ApiError("bad_request", str(exc), 400) from exc


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


def _severity_rollup(alerts):
    rank = {"NORMAL": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    return max((alert.get("severity", "NORMAL") for alert in alerts), key=lambda value: rank.get(value, 0), default="NORMAL")


def _timeline(alerts, forecasts, actions):
    rows = []
    for alert in alerts:
        rows.append({"kind": "detection", "ts": alert["ts"], "label": "%s alert on %s" % (alert["severity"], alert["host"]), "ref_id": alert["event_id"], "host": alert["host"]})
    for forecast in forecasts:
        target = forecast.get("targets", [{}])[0].get("host_id") if forecast.get("targets") else None
        label = "Predicted target: %s" % target if target else "Forecast recorded"
        rows.append({"kind": "forecast", "ts": forecast["ts"], "label": label, "ref_id": forecast["forecast_id"], "host": target})
    for action in actions:
        host = action["target_host"]
        rows.append({"kind": "containment", "ts": action["proposed_at"], "label": "Containment proposed for %s" % host, "ref_id": action["action_id"], "host": host})
        if action.get("confirmed_at"):
            rows.append({"kind": "containment", "ts": action["confirmed_at"], "label": "Simulated containment %s for %s" % (action["status"], host), "ref_id": action["action_id"], "host": host})
    rows.sort(key=lambda row: (_entry_time(row["ts"]), row["ref_id"], row["kind"]))
    return rows


def _incident_from_session(record):
    alerts = record.get("alerts", [])
    forecasts = record.get("forecasts", [])
    actions = record.get("actions", [])
    incident_id = "inc-" + record["session_id"]
    severity = _severity_rollup(alerts)
    hosts = []
    observed_targets = [forecast.get("outcome", {}).get("attempted_host") for forecast in forecasts if forecast.get("outcome")]
    for host in [alert.get("host") for alert in alerts] + [forecast.get("from_host") for forecast in forecasts] + observed_targets + [action.get("target_host") for action in actions]:
        if host and host not in hosts:
            hosts.append(host)
    techniques = []
    seen_techniques = set()
    for alert in alerts:
        technique_id, technique_name = alert.get("technique_id"), alert.get("technique_name")
        if technique_id and technique_id not in seen_techniques:
            techniques.append({"technique_id": technique_id, "technique_name": technique_name or technique_id})
            seen_techniques.add(technique_id)
    if record.get("status") in INCIDENT_STATUSES:
        status = record["status"]
    elif any(action.get("status") == "executed" for action in actions):
        status = "contained"
    else:
        status = "open"
    title = "%s replay" % (record.get("scenario_id") or "Replay session")
    return {
        "incident_id": incident_id, "session_id": record["session_id"], "scenario_id": record.get("scenario_id"),
        "title": title, "summary": "A simulated attack chain recorded %d alert%s across %d host%s." % (
            len(alerts), "" if len(alerts) == 1 else "s", len(hosts), "" if len(hosts) == 1 else "s"),
        "started_at": record["started_at"], "ended_at": record.get("ended_at"), "status": status,
        "severity": severity, "alert_count": len(alerts), "hosts": hosts, "techniques": techniques,
        "alerts": alerts, "forecasts": forecasts, "actions": actions,
        "timeline": _timeline(alerts, forecasts, actions), "notes": record.get("notes", []),
    }


def _session_report(record):
    alerts = record.get("alerts", [])
    forecasts = record.get("forecasts", [])
    actions = record.get("actions", [])
    resolved = [forecast for forecast in forecasts if forecast.get("status") in ("hit", "miss")]
    hits = [forecast for forecast in resolved if forecast.get("status") == "hit"]
    top_one = [forecast for forecast in resolved if forecast.get("outcome") and forecast["outcome"].get("rank_hit") == 1]
    top_three = [forecast for forecast in resolved if forecast.get("outcome") and forecast["outcome"].get("rank_hit") is not None]
    count = len(resolved)
    return {
        "session_id": record["session_id"], "scenario_id": record.get("scenario_id"),
        "started_at": record["started_at"], "ended_at": record.get("ended_at"),
        "alert_count": len(alerts), "severity": _severity_rollup(alerts), "alerts": alerts,
        "forecasts": forecasts, "actions": actions,
        "metrics": {
            "forecasts_resolved": count, "hits": len(hits), "hit_rate": len(hits) / count if count else None,
            "precision_at_1": len(top_one) / count if count else None,
            "precision_at_3": len(top_three) / count if count else None,
            "honesty_note": "Session counter, not the model's overall accuracy. Precision@3 can be trivial when at most three hosts are reachable.",
        },
        "timeline": _timeline(alerts, forecasts, actions),
    }


def _incident_records(ctx):
    records = []
    for session_record in ctx["world"].incident_sessions():
        if session_record.get("alerts") or session_record.get("forecasts") or session_record.get("actions"):
            records.append(_incident_from_session(session_record))
    records.sort(key=lambda item: (_entry_time(item["started_at"]), item["incident_id"]), reverse=True)
    return records


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
    return jsonify(_out("operator_profile", auth.operator_profile(user)))


@bp.post("/logout")
def logout():
    auth.do_logout()
    return jsonify({"status": "ok"})


@bp.get("/me")
@auth.json_login_required
def me():
    return jsonify(_out("operator_profile", auth.operator_profile(current_user)))


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


@bp.get("/incidents")
@auth.json_login_required
def incidents():
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        raise ApiError("bad_request", "'limit' must be a whole number.", 400)
    limit = max(1, min(limit, MAX_ALERT_LIMIT))
    status = request.args.get("status", "")
    severity = request.args.get("severity", "").upper()
    if status and status not in INCIDENT_STATUSES:
        raise ApiError("bad_request", "'status' must be one of: %s." % ", ".join(INCIDENT_STATUSES), 400)
    if severity and severity not in ALERT_SEVERITIES:
        raise ApiError("bad_request", "'severity' must be one of: %s." % ", ".join(ALERT_SEVERITIES), 400)
    filters = {"q": _query_text("q"), "status": status, "severity": severity}
    query = filters["q"].casefold()
    rows = []
    for incident in _incident_records(_ctx()):
        searchable = " ".join((incident["incident_id"], incident["title"], incident["summary"], " ".join(incident["hosts"]), " ".join(item["technique_id"] for item in incident["techniques"]))).casefold()
        if status and incident["status"] != status:
            continue
        if severity and incident["severity"] != severity:
            continue
        if query and query not in searchable:
            continue
        rows.append(incident)
    page, next_cursor = _page_window(rows, limit, request.args.get("cursor", ""))
    payload = {"items": page, "total": len(rows), "next_cursor": next_cursor, "limit": limit, "filters": filters}
    return jsonify(_out("incident_page", payload))


def _find_incident(incident_id):
    return next((item for item in _incident_records(_ctx()) if item["incident_id"] == incident_id), None)


def _audit_incident(incident_id, summary):
    events = _ctx()["hooks"].get("events")
    recorder = getattr(events, "audit_record", None) if events is not None else None
    if recorder is not None:
        recorder("incident", incident_id, summary)


@bp.get("/incidents/<incident_id>")
@auth.json_login_required
def incident_detail(incident_id):
    found = _find_incident(incident_id)
    if found is None:
        raise ApiError("not_found", "No incident with id %s." % incident_id, 404)
    return jsonify(_out("incident_detail", found))


@bp.post("/incidents/<incident_id>/notes")
@auth.json_login_required
def incident_add_note(incident_id):
    if _find_incident(incident_id) is None:
        raise ApiError("not_found", "No incident with id %s." % incident_id, 404)
    text = _text(_body(), "text")
    if len(text) > 2000:
        raise ApiError("bad_request", "Incident notes must be 2000 characters or fewer.", 400)
    note = {"note_id": "note-%s" % uuid.uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"), "author": current_user.username, "text": text}
    _out("incident_note", note)
    _ctx()["world"].add_incident_note(incident_id, note)
    _audit_incident(incident_id, "Analyst note added to simulated incident.")
    return jsonify(note), 201


@bp.patch("/incidents/<incident_id>/status")
@auth.json_login_required
def incident_set_status(incident_id):
    if _find_incident(incident_id) is None:
        raise ApiError("not_found", "No incident with id %s." % incident_id, 404)
    status = _text(_body(), "status")
    if status not in INCIDENT_STATUSES:
        raise ApiError("bad_request", "'status' must be one of: %s." % ", ".join(INCIDENT_STATUSES), 400)
    _ctx()["world"].set_incident_status(incident_id, status)
    _audit_incident(incident_id, "Incident status updated to %s." % status)
    found = _find_incident(incident_id)
    return jsonify(_out("incident_detail", found))


@bp.get("/reports")
@auth.json_login_required
def reports():
    records = _ctx()["world"].incident_sessions()
    items = []
    for record in records:
        report = _session_report(record)
        items.append({key: report[key] for key in ("session_id", "scenario_id", "started_at", "ended_at", "alert_count", "severity")}
                      | {"forecasts_resolved": report["metrics"]["forecasts_resolved"], "hit_rate": report["metrics"]["hit_rate"]})
    payload = {"items": items, "total": len(items)}
    return jsonify(_out("report_page", payload))


@bp.get("/reports/<session_id>")
@auth.json_login_required
def report_detail(session_id):
    record = next((item for item in _ctx()["world"].incident_sessions() if item["session_id"] == session_id), None)
    if record is None:
        raise ApiError("not_found", "No replay session with id %s." % session_id, 404)
    return jsonify(_out("session_report", _session_report(record)))


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
    source = request.args.get("source")
    if source is not None and source not in ("repo", "lookup"):
        raise ApiError("bad_request", "'source' must be 'repo' or 'lookup'.", 400)
    include_archived = request.args.get("include_archived", "0")
    if include_archived not in ("0", "1"):
        raise ApiError("bad_request", "'include_archived' must be 0 or 1.", 400)
    session_id = request.args.get("session_id")
    from_host = request.args.get("from_host")
    items = _ctx()["world"].forecasts(status, include_archived=include_archived == "1")
    if source is not None:
        items = [item for item in items if item.get("source") == source]
    if session_id:
        items = [item for item in items if item.get("session_id") == session_id]
    if from_host:
        items = [item for item in items if item.get("from_host") == from_host]
    return jsonify(items)


@bp.get("/forecasts/current")
@auth.json_login_required
def forecast_current():
    
    
    found = _ctx()["world"].current_forecast()
    
    if found is None:
    
        raise ApiError("no_forecast", "No forecast is pending.", 404)
    return jsonify(found)


@bp.get("/forecasts/what-if")
@auth.json_login_required
def forecast_what_if():
    ctx = _ctx()
    from_host = _query_text("from_host", 128)
    if not from_host:
        raise ApiError("bad_request", "'from_host' is required.", 400)
    graph = ctx["hooks"].get("graph")
    engine = ctx["hooks"].get("precog")
    if graph is None or engine is None:
        raise ApiError("not_built", "The graph and Precog modules are required for a what-if forecast.", 501)
    host = next((item for item in ctx["world"].graph().get("hosts", []) if item.get("host_id") == from_host), None)
    if host is None:
        raise ApiError("not_found", "No host with id %s." % from_host, 404)
    if host.get("state") != "compromised":
        raise ApiError("host_not_compromised", "Choose a host currently marked compromised in this simulation.", 409)
    candidates = graph.feasible_targets(from_host)
    if not candidates:
        raise ApiError("no_candidates", "No feasible predicted targets remain for this host.", 409)
    preview = engine.preview(from_host, candidates)
    payload = {
        "from_host": from_host,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **preview,
        "note": "Read-only simulation preview. This does not create a forecast, change host state, or affect the replay.",
    }
    return jsonify(_out("what_if_forecast", payload))


@bp.get("/forecasts/<forecast_id>")
@auth.json_login_required
def forecast_detail(forecast_id):
    found = next((item for item in _ctx()["world"].forecasts(include_archived=True) if item.get("forecast_id") == forecast_id), None)
    if found is None:
        raise ApiError("not_found", "No forecast with id %s." % forecast_id, 404)
    return jsonify(_out("forecast", found))


# ---------- containment (needs the VIZ module) ----------
@bp.post("/containment/propose")
@auth.demo_role_required("analyst", "admin")

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
@auth.demo_role_required("analyst", "admin")
def containment_confirm():
    ctx = _ctx()
    action = ctx["hooks"].require("containment").confirm(ctx["world"], _text(_body(), "action_id"))
    
    return jsonify(_out("containment_action", action))


@bp.post("/containment/cancel")
@auth.demo_role_required("analyst", "admin")
def containment_cancel():
    ctx = _ctx()
    action = ctx["hooks"].require("containment").cancel(ctx["world"], _text(_body(), "action_id"))
    return jsonify(_out("containment_action", action))


@bp.get("/containment/actions")
@auth.json_login_required
def containment_actions():
    include_archived = request.args.get("include_archived", "0")
    if include_archived not in ("0", "1"):
        raise ApiError("bad_request", "'include_archived' must be 0 or 1.", 400)
    return jsonify(_ctx()["world"].actions(include_archived=include_archived == "1"))


@bp.post("/containment/playbooks/propose")
@auth.demo_role_required("analyst", "admin")
def containment_playbook_propose():
    ctx = _ctx()
    data = _body()
    _validate_input("containment_playbook_request", data)
    playbook = data["playbook"]
    graph = ctx["hooks"].require("graph")
    snapshot = graph.snapshot()
    hosts = snapshot.get("hosts", [])
    host_by_id = {host["host_id"]: host for host in hosts}
    forecast_id = _text(data, "forecast_id", required=False)

    if playbook == "host":
        targets = [_text(data, "target_host")]
    elif playbook == "zone":
        zone = _text(data, "zone")
        if zone not in {host.get("zone") for host in hosts}:
            raise ApiError("unknown_zone", "Choose a zone that exists in the simulated topology.", 404)
        targets = [host["host_id"] for host in hosts if host.get("zone") == zone and host.get("state") != "contained"]
    else:
        forecast = next((item for item in ctx["world"].forecasts() if item.get("forecast_id") == forecast_id), None) if forecast_id else ctx["world"].current_forecast()
        if forecast is None or forecast.get("status") != "pending":
            raise ApiError("forecast_unavailable", "Choose a pending forecast from the current replay.", 409)
        forecast_id = forecast["forecast_id"]
        predicted = [item["host_id"] for item in forecast.get("targets", [])]
        if playbook == "top_three":
            targets = predicted[:3]
        else:
            path = snapshot.get("compromised_path", [])
            targets = list(dict.fromkeys(path + predicted))
        targets = [host_id for host_id in targets if host_by_id.get(host_id, {}).get("state") != "contained"]

    action = ctx["hooks"].require("containment").propose_many(ctx["world"], targets, forecast_id, "console", playbook)
    return jsonify(_out("containment_action", action))


@bp.post("/containment/release/propose")
@auth.demo_role_required("admin")
def containment_release_propose():
    data = _body()
    action = _ctx()["hooks"].require("containment").propose_release(
        _ctx()["world"], _text(data, "containment_action_id"), "console"
    )
    return jsonify(_out("containment_action", action))


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


def _metric_summary(record):
    return {key: record[key] for key in ("forecasts", "precision_at_1", "precision_at_1_std_error", "precision_at_3", "expected_calibration_error")}


@bp.get("/analytics")
@auth.json_login_required
def forecast_analytics():
    ctx = _ctx()
    evaluation_path = ctx["config"].repo_root / "lead-core" / "precog" / "results" / "precog_evaluation.json"
    try:
        evaluated = json.loads(evaluation_path.read_text(encoding="utf-8"))
        node = evaluated["node_model"]
        split = evaluated["split"]
        alpha = evaluated["alpha"]["chosen"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        current_app.logger.exception("Precog evaluation results could not be loaded")
        raise ApiError("analytics_unavailable", "The held-out Precog evaluation results are unavailable.", 503) from exc

    resolved = [item for item in ctx["world"].forecasts(include_archived=True) if item.get("status") in ("hit", "miss") and item.get("outcome")]
    tally_counts = {"model": 0, "rule_based": 0, "uniform": 0}
    tally_samples = {"model": 0, "rule_based": 0, "uniform": 0}
    for forecast in resolved:
        attempted = forecast["outcome"].get("attempted_host")
        model_hit = forecast["outcome"].get("rank_hit") == 1
        if forecast.get("explanation"):
            tally_samples["model"] += 1
            tally_counts["model"] += int(model_hit)
            row = next((candidate for candidate in forecast["explanation"].get("candidate_set", []) if candidate.get("host_id") == attempted), None)
            if row is not None:
                for name, rank_field in (("rule_based", "rule_based_rank"), ("uniform", "uniform_rank")):
                    tally_samples[name] += 1
                    tally_counts[name] += int(row.get(rank_field) == 1)

    def tally(name):
        sample_size = tally_samples[name]
        return {"rank1_hits": tally_counts[name], "precision_at_1": round(tally_counts[name] / sample_size, 4) if sample_size else None}

    payload = {
        "evaluation": {
            "source": "Held-out route evaluation from lead-core/precog/results/precog_evaluation.json; Golden Path runs are excluded.",
            "training_sequences": split["training_sequences"],
            "test_sequences": split["test_sequences"],
            "alpha": alpha,
            "node_model": _metric_summary(node),
            "calibration_bins": node["calibration_bins"],
            "baselines": [
                {"name": "Rule-based (simulated edge likelihood)", "metrics": _metric_summary(evaluated["baseline_rule_based"])},
                {"name": "Uniform (equal candidate probability)", "metrics": _metric_summary(evaluated["baseline_uniform"])},
            ],
        },
        "session": ctx["world"].metrics(),
        "live_tally": {
            "forecasts_resolved": len(resolved),
            "honesty_note": "Session counter, not the model's overall accuracy. Baselines use each forecast's captured candidate ranking.",
            "model": tally("model"),
            "rule_based": tally("rule_based"),
            "uniform": tally("uniform"),
        },
        "detection_report": ctx["world"].detection_report(),
        "honesty_notes": [
            "Forecast metrics come from held-out training sequences; Golden Path rehearsals are not part of the evaluation.",
            "Precision@3 is 1.0 for all methods because at most three hosts are reachable in the current topology; it does not separate the methods.",
            "The Markov model's precision@1 is only slightly above the rule-based baseline in this evaluation.",
            "The CICIDS2017 detection report describes an offline public sample and is not comparable with the live Isolation Forest detector.",
            "Any hit rate shown for the current replay is a session counter, not the model's overall accuracy.",
        ],
    }
    return jsonify(_out("forecast_analytics", payload))


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
@auth.demo_role_required("analyst", "admin")
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
@auth.demo_role_required("analyst", "admin")
def replay_pause():
    return _replay_action("pause")


@bp.post("/replay/resume")
@auth.demo_role_required("analyst", "admin")
def replay_resume():
    return _replay_action("resume")


@bp.post("/replay/restart")
@auth.demo_role_required("admin")
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

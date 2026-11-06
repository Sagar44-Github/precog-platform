"""All new routes. They live under /api/x so they never clash with NIDS's own routes.

Every error answers JSON like {"error": {"code": "...", "message": "..."}}.
"""
from flask import Blueprint, Response, current_app, jsonify, request
import platform
import sqlite3
import uuid
from datetime import time, timedelta
from importlib.metadata import version as package_version
from flask_login import current_user
from werkzeug.exceptions import HTTPException
from urllib.parse import urlsplit
from datetime import datetime, timezone
import html
import json
import re

from . import auth
from .contracts import ContractError
from .dataset_packs import PackError
from .errors import ApiError

bp = Blueprint("precog_addons", __name__, url_prefix="/api/x")

FORECAST_STATUSES = ("pending", "hit", "miss", "superseded")
REQUESTERS = ("console", "mobile")
MAX_ALERT_LIMIT = 200
ALERT_SEVERITIES = ("HIGH", "MEDIUM", "LOW", "NORMAL")
AUDIT_TYPES = ("detection", "forecast", "containment", "incident", "workspace")
PAGE_SORTS = ("ts", "risk_score", "severity")
INCIDENT_STATUSES = ("open", "contained", "closed", "reopened")
INCIDENT_SEVERITIES = ("HIGH", "MEDIUM", "LOW")
INCIDENT_SORTS = ("updated_desc", "created_asc", "severity_desc")
INCIDENT_ID = re.compile(r"^INC-[0-9]{4}$")
RUN_ID = re.compile(r"^RUN-[0-9]{6}$")
MAX_WRITE_BYTES = 32768


def _ctx():
    return current_app.extensions["precog"]


def _governance():
    service = current_app.extensions.get("precog_governance")
    if service is None:
        raise ApiError("not_built", "The response governance module is not available.", 501)
    return service


def _workspaces():
    service = current_app.extensions.get("precog_workspaces")
    if service is None:
        raise ApiError("not_built", "Dataset workspace management is unavailable.", 501)
    return service


def _audit_workspace(pack_id, summary):
    events = _ctx()["hooks"].get("events")
    recorder = getattr(events, "audit_record", None) if events is not None else None
    if recorder is not None:
        recorder("workspace", pack_id, "%s (%s): %s" % (current_user.username, auth.current_role(), summary))


def _governance_result(record):
    kind = "release_record" if record.get("playbook_id") == "release-host" else "approval_record"
    return {"record_type": "release" if kind == "release_record" else "approval", "record": _out(kind, record)}


def _body():
    data = request.get_json(silent=True)
    
    if not isinstance(data, dict):
        raise ApiError("bad_request", "Send a JSON object in the request body.", 400)
    return data


@bp.before_request
def _protect_cookie_writes():
    """Only same-origin JSON requests with the app's non-simple header may mutate state.

    The custom header forces a CORS preflight; this service does not enable cross-origin
    CORS. Fetch Metadata and Origin are checked as a second same-origin signal.
    """
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    if request.endpoint == "precog_addons.login":
        return None
    if not current_user.is_authenticated:
        return None  # protected views return the existing JSON 401 response
    if not request.is_json:
        raise ApiError("json_required", "Send writes as application/json.", 415)
    if request.content_length is not None and request.content_length > MAX_WRITE_BYTES:
        raise ApiError("request_too_large", "The JSON request is larger than 32 KB.", 413)
    if request.headers.get("X-Precog-Request") != "1":
        raise ApiError("csrf_rejected", "This write did not include the required same-origin request header.", 403)
    if request.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
        raise ApiError("csrf_rejected", "Cross-site writes are not allowed.", 403)
    origin = request.headers.get("Origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme != request.scheme or parsed.netloc.lower() != request.host.lower():
            raise ApiError("csrf_rejected", "Cross-origin writes are not allowed.", 403)
    return None


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
    return jsonify(_out("role_info", auth.info_for(user.username)))


@bp.post("/logout")
def logout():
    auth.do_logout()
    return jsonify({"status": "ok"})


@bp.get("/me")
def me():
    # Keep the public SPA's initial auth check quiet for signed-out visitors.
    # Protected data routes still require a session and return JSON 401 errors.
    if current_user.is_authenticated:
        return jsonify(_out("role_info", auth.info_for(current_user.username)))
    return jsonify({"status": "ok", "username": None})


@bp.get("/role")
@auth.json_login_required
def role_info():
    return jsonify(_out("role_info", auth.info_for(current_user.username)))


@bp.get("/feed")
@auth.json_login_required
def domain_feed():
    since_text = request.args.get("since")
    since = None
    if since_text is not None:
        try:
            since = int(since_text)
        except ValueError:
            raise ApiError("bad_request", "'since' must be a whole number.", 400)
        if since < 0:
            raise ApiError("bad_request", "'since' cannot be negative.", 400)
    incidents = _ctx()["hooks"].require("incidents")
    result = incidents.feed(since)
    studio = _ctx()["hooks"].get("studio")
    if studio is not None:
        incidents.set_run_version(studio.revision)
        result = incidents.feed(since)
        result["revision"] += studio.revision
    governance = current_app.extensions.get("precog_governance")
    if governance is not None:
        governance.records(1)  # Refresh expired proposals before publishing the action version.
        result["versions"]["actions"] += governance.revision
        result["revision"] += governance.revision
    result["versions"]["workspace"] = _workspaces().feed_version()
    result["revision"] += result["versions"]["workspace"]
    result["changed"] = since is None or since != result["revision"]
    return jsonify(_out("feed_versions", result))


@bp.get("/workspaces")
@auth.json_login_required
def workspaces_list():
    service = _workspaces()
    summaries = [_out("workspace", item) for item in service.list_workspaces()]
    payload = {"active_workspace": service.active.pack_id, "workspaces": summaries}
    return jsonify(_out("workspace_list", payload))


@bp.get("/workspaces/active")
@auth.json_login_required
def workspace_active():
    service = _workspaces()
    payload = service.summary(service.active, active=True)
    payload["workspace_version"] = service.version
    return jsonify(_out("workspace", payload))


@bp.get("/workspaces/<workspace_id>/card")
@auth.json_login_required
def workspace_card(workspace_id):
    try:
        payload = _workspaces().card(workspace_id)
    except PackError as exc:
        raise ApiError("workspace_not_found", str(exc), 404)
    return jsonify(_out("dataset_card", payload))


@bp.post("/workspaces/install")
@auth.demo_role_required("admin")
def workspace_install():
    data = _body()
    pack_id = _text(data, "pack_id")
    try:
        manifest = _workspaces().store.open(pack_id).manifest
    except PackError as exc:
        raise ApiError("invalid_pack", str(exc), 400)
    # D2 deliberately installs only a pack already placed beneath the configured
    # local packs root. Arbitrary paths and remote archives are not accepted.
    _audit_workspace(_workspaces().active.pack_id, "validated local pack %s for workspace installation" % pack_id)
    return jsonify(_out("pack_install_job", {"job_id": "install-%s" % pack_id, "pack_id": pack_id,
        "state": "completed", "progress": 1.0, "message": "Validated local pack %s (%.2f MiB)." % (pack_id, manifest["size_bytes"] / 1048576)}))


@bp.post("/workspaces/<workspace_id>/activate")
@auth.demo_role_required("admin", "analyst")
def workspace_activate(workspace_id):
    data = _body()
    if data.get("confirm") is not True:
        raise ApiError("confirmation_required", "Confirm that switching resets the current replay state.", 400)
    service = _workspaces()
    previous_id = service.active.pack_id
    try:
        service.store.open(workspace_id)
        _audit_workspace(previous_id, "switching to workspace %s" % workspace_id)
        result = service.activate(workspace_id)
    except PackError as exc:
        raise ApiError("workspace_unavailable", str(exc), 404)
    _audit_workspace(workspace_id, "activated from workspace %s" % previous_id)
    result["workspace_version"] = service.version
    return jsonify(_out("workspace", result))


@bp.delete("/workspaces/<workspace_id>")
@auth.demo_role_required("admin")
def workspace_delete(workspace_id):
    service = _workspaces()
    if workspace_id == "demo-6":
        raise ApiError("protected_workspace", "The default demo-6 workspace cannot be deleted.", 403)
    if workspace_id == service.active.pack_id:
        raise ApiError("workspace_active", "Switch away from a workspace before deleting it.", 409)
    try:
        pack = service.store.open(workspace_id)
    except PackError as exc:
        raise ApiError("workspace_not_found", str(exc), 404)
    # Delete only a validated direct-child pack; never use an identifier as a path.
    import shutil
    _audit_workspace(service.active.pack_id, "deleted installed workspace pack %s" % workspace_id)
    shutil.rmtree(pack.path)
    service._buckets.pop(workspace_id, None)
    data_path = service.data_root / workspace_id
    if data_path.resolve().parent == service.data_root.resolve() and data_path.exists():
        shutil.rmtree(data_path)
    service.version += 1
    return jsonify({"status": "deleted", "workspace_id": workspace_id, "workspace_version": service.version})


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
    source = request.args.get("source")
    include_archived = request.args.get("include_archived", "0").lower() in ("1", "true", "yes")
    if status is not None and status not in FORECAST_STATUSES:
        raise ApiError("bad_request", "'status' must be one of: %s." % ", ".join(FORECAST_STATUSES), 400)
    if source is not None and source not in ("repo", "lookup"):
        raise ApiError("bad_request", "'source' must be repo or lookup.", 400)
    rows = _ctx()["world"].forecasts(status, include_archived=include_archived)
    if source is not None:
        rows = [row for row in rows if row.get("source") == source]
    return jsonify(rows)


@bp.get("/forecasts/current")
@auth.json_login_required
def forecast_current():
    
    
    found = _ctx()["world"].current_forecast()
    
    if found is None:
    
        raise ApiError("no_forecast", "No forecast is pending.", 404)
    return jsonify(found)


@bp.get("/forecasts/<forecast_id>/explain")
@auth.json_login_required
def forecast_explain(forecast_id):
    try:
        result = current_app.extensions["precog_lab"].explain(forecast_id)
    except KeyError:
        raise ApiError("not_found", "There is no forecast with id %s." % forecast_id, 404)
    return jsonify(_out("forecast_explanation", result))


@bp.post("/whatif")
@auth.json_login_required
@auth.rate_limit(max_requests=20, window_seconds=60)
def whatif():
    data = _body()
    try:
        _ctx()["contracts"].validate("whatif_request", data) if _ctx()["contracts"] else None
        result = current_app.extensions["precog_lab"].whatif(data)
    except ContractError as exc:
        raise ApiError("bad_request", str(exc), 400)
    except ValueError as exc:
        raise ApiError("bad_request", str(exc), 400)
    return jsonify(_out("whatif_result", result))


@bp.get("/analytics/model")
@auth.json_login_required
def analytics_model():
    return jsonify(_out("model_card", current_app.extensions["precog_lab"].model_overview()))


@bp.post("/analytics/evaluate")
@auth.role_required("analyst")
@auth.rate_limit(max_requests=3, window_seconds=60)
def analytics_evaluate():
    data = _body()
    try:
        if _ctx()["contracts"]:
            _ctx()["contracts"].validate("evaluation_request", data)
    except ContractError as exc:
        raise ApiError("bad_request", str(exc), 400)
    if set(data) - {"seed", "test_fraction", "alpha_grid"}:
        raise ApiError("bad_request", "Only seed, test_fraction and alpha_grid are accepted.", 400)
    seed = data.get("seed", 0)
    fraction = data.get("test_fraction", 0.2)
    grid = data.get("alpha_grid", [0.01, 0.05, 0.1, 0.2, 0.5, 1.0])
    if isinstance(seed, bool) or not isinstance(seed, int) or abs(seed) > 1000000:
        raise ApiError("bad_request", "seed must be a whole number between -1000000 and 1000000.", 400)
    if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not 0.1 <= float(fraction) <= 0.5:
        raise ApiError("bad_request", "test_fraction must be between 0.1 and 0.5.", 400)
    if not isinstance(grid, list) or not 1 <= len(grid) <= 6 or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.001 <= float(value) <= 2 for value in grid) or len(set(grid)) != len(grid):
        raise ApiError("bad_request", "alpha_grid must contain 1–6 unique numbers from 0.001 to 2.", 400)
    try:
        result = current_app.extensions["precog_lab"].run_evaluation(seed, float(fraction), [float(value) for value in grid])
    except TimeoutError as exc:
        raise ApiError("evaluation_timeout", str(exc), 503)
    return jsonify(_out("evaluation_run", result))


@bp.get("/analytics/experiments")
@auth.json_login_required
def analytics_experiments():
    return jsonify([_out("evaluation_run", item) for item in current_app.extensions["precog_lab"].list_experiments()])


# ---------- containment (needs the VIZ module) ----------
@bp.post("/containment/propose")
@auth.role_required("analyst")

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
@auth.role_required("analyst")
def containment_confirm():
    ctx = _ctx()
    action = ctx["hooks"].require("containment").confirm(ctx["world"], _text(_body(), "action_id"))
    
    return jsonify(_out("containment_action", action))


@bp.post("/containment/cancel")
@auth.role_required("analyst")
def containment_cancel():
    ctx = _ctx()
    action = ctx["hooks"].require("containment").cancel(ctx["world"], _text(_body(), "action_id"))
    return jsonify(_out("containment_action", action))


@bp.get("/containment/actions")
@auth.json_login_required
def containment_actions():
    return jsonify(_ctx()["world"].actions())


# ---------- governed response playbooks (all actions remain simulated) ----------
@bp.get("/containment/playbooks")
@auth.json_login_required
def containment_playbooks():
    return jsonify([_out("playbook", item) for item in _governance().list_playbooks()])


@bp.post("/containment/preview")
@auth.json_login_required
@auth.rate_limit(max_requests=20, window_seconds=60)
def containment_preview():
    data = _body()
    allowed = {"playbook_id", "host_id", "zone", "forecast_id"}
    if set(data) - allowed or "playbook_id" not in data:
        raise ApiError("bad_request", "Send playbook_id and only its optional host_id, zone, and forecast_id fields.", 400)
    for key in ("playbook_id", "host_id", "zone", "forecast_id"):
        if key in data and data[key] is not None and (not isinstance(data[key], str) or len(data[key]) > 100):
            raise ApiError("bad_request", "'%s' must be text of at most 100 characters." % key, 400)
    preview = _governance().preview(data["playbook_id"], auth.current_role(), data.get("host_id"), data.get("zone"), data.get("forecast_id"))
    return jsonify(_out("playbook_preview", preview))


@bp.get("/containment/governance")
@auth.json_login_required
def containment_governance_records():
    try:
        limit = int(request.args.get("limit", "100"))
    except ValueError:
        raise ApiError("bad_request", "'limit' must be a whole number.", 400)
    records = _governance().records(limit)
    return jsonify({
        "approvals": [_out("approval_record", item) for item in records["approvals"]],
        "releases": [_out("release_record", item) for item in records["releases"]],
        "revision": records["revision"],
    })


@bp.get("/containment/governance/export")
@auth.json_login_required
@auth.rate_limit(max_requests=12, window_seconds=60)
def containment_governance_export():
    fmt = request.args.get("format", "json").lower()
    if fmt not in ("json", "markdown"):
        raise ApiError("bad_request", "Format must be json or markdown.", 400)
    records = _governance().records(200)
    if fmt == "json":
        return jsonify(records)
    lines = ["# Precog SOC response governance", "", "SIMULATION — these actions changed only in-memory demo state.", ""]
    for title, items in (("Playbook proposals", records["approvals"]), ("Host releases", records["releases"])):
        lines.extend(["## " + title, ""])
        if not items:
            lines.extend(["No records.", ""])
        for item in items:
            reason = html.escape(str(item.get("reason", ""))).replace("\n", " ")
            lines.extend([
                "### %s · %s · %s" % (item["action_id"], item["playbook_id"], item["status"]),
                "",
                "- Proposed by: %s (%s)" % (html.escape(item["proposed_by"]), item["proposed_role"]),
                "- Proposed at: %s" % item["proposed_at"],
                "- Reason: %s" % reason,
                "- Hosts: %s" % ", ".join(host["host_id"] for host in item["preview_snapshot"]["hosts_affected"]),
                "- Executed actions: %s" % ", ".join(item.get("host_action_ids", [])) if "host_action_ids" in item else "- Executed actions: release record",
                "",
            ])
    response = Response("\n".join(lines), content_type="text/markdown; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="precog-response-governance.md"'
    return response


@bp.post("/containment/governance/propose")
@auth.role_required("analyst")
@auth.rate_limit(max_requests=12, window_seconds=60)
def containment_governance_propose():
    data = _body()
    allowed = {"playbook_id", "host_id", "zone", "forecast_id", "incident_id", "reason"}
    if set(data) - allowed or not {"playbook_id", "reason"} <= set(data):
        raise ApiError("bad_request", "Send playbook_id and reason, with only optional host_id, zone, forecast_id, and incident_id.", 400)
    for key in allowed:
        value = data.get(key)
        if value is not None and (not isinstance(value, str) or len(value) > (500 if key == "reason" else 100)):
            raise ApiError("bad_request", "'%s' has an invalid value or is too long." % key, 400)
    if data.get("incident_id") is not None and not INCIDENT_ID.fullmatch(data["incident_id"]):
        raise ApiError("bad_request", "'incident_id' must use the INC-0001 format.", 400)
    record = _governance().propose(
        data["playbook_id"], current_user.username, auth.current_role(), data["reason"],
        host_id=data.get("host_id"), zone=data.get("zone"), forecast_id=data.get("forecast_id"), incident_id=data.get("incident_id"),
    )
    return jsonify(_governance_result(record))


@bp.post("/containment/governance/approve")
@auth.role_required("admin")
def containment_governance_approve():
    data = _body()
    if set(data) - {"action_id", "decision", "reason"} or not {"action_id", "decision"} <= set(data):
        raise ApiError("bad_request", "Send action_id, decision and an optional reason.", 400)
    action_id = _text(data, "action_id")
    if len(action_id) > 32:
        raise ApiError("bad_request", "Invalid action id.", 400)
    record = _governance().approve(action_id, current_user.username, auth.current_role(), data["decision"], data.get("reason", ""))
    return jsonify(_governance_result(record))


@bp.post("/containment/governance/confirm")
@auth.role_required("analyst")
def containment_governance_confirm():
    data = _body()
    if set(data) != {"action_id"}:
        raise ApiError("bad_request", "Send exactly one field: action_id.", 400)
    action_id = _text(data, "action_id")
    if len(action_id) > 32:
        raise ApiError("bad_request", "Invalid action id.", 400)
    return jsonify(_governance_result(_governance().confirm(action_id, current_user.username, auth.current_role())))


@bp.post("/containment/governance/cancel")
@auth.role_required("analyst")
def containment_governance_cancel():
    data = _body()
    if set(data) - {"action_id", "reason"} or "action_id" not in data:
        raise ApiError("bad_request", "Send action_id and an optional cancellation reason.", 400)
    action_id = _text(data, "action_id")
    if len(action_id) > 32:
        raise ApiError("bad_request", "Invalid action id.", 400)
    record = _governance().cancel(action_id, current_user.username, auth.current_role(), data.get("reason", "Cancelled by the operator."))
    return jsonify(_governance_result(record))


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
@auth.role_required("analyst")
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
@auth.role_required("analyst")
def replay_pause():
    return _replay_action("pause")


@bp.post("/replay/resume")
@auth.role_required("analyst")
def replay_resume():
    return _replay_action("resume")


@bp.post("/replay/restart")
@auth.role_required("analyst")
def replay_restart():
    return _replay_action("restart")


# ---------- push ----------
@bp.post("/push/register")
@auth.role_required("analyst")
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


# ---------- incident investigation workbench ----------
def _incident_id(value):
    if not INCIDENT_ID.fullmatch(value or ""):
        raise ApiError("bad_request", "Incident identifiers use the form INC-0001.", 400)
    return value


def _incident_time_arg(key, alternate=None):
    value = request.args.get(key)
    if value is None and alternate:
        value = request.args.get(alternate)
    if value is None or value == "":
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ApiError("bad_request", "'%s' must be an ISO 8601 timestamp." % key, 400)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@bp.get("/incidents")
@auth.json_login_required
@auth.rate_limit(max_requests=90, window_seconds=60)
def incidents_list():
    status = request.args.get("status")
    severity = request.args.get("severity")
    sort = request.args.get("sort", "updated_desc")
    host = request.args.get("host")
    technique = request.args.get("technique")
    cursor = request.args.get("cursor")
    if status and status not in INCIDENT_STATUSES:
        raise ApiError("bad_request", "'status' must be one of: %s." % ", ".join(INCIDENT_STATUSES), 400)
    if severity and severity not in INCIDENT_SEVERITIES:
        raise ApiError("bad_request", "'severity' must be one of: %s." % ", ".join(INCIDENT_SEVERITIES), 400)
    if sort not in INCIDENT_SORTS:
        raise ApiError("bad_request", "'sort' must be one of: %s." % ", ".join(INCIDENT_SORTS), 400)
    if host is not None and (not host.strip() or len(host) > 80):
        raise ApiError("bad_request", "'host' must be a host id of 1 to 80 characters.", 400)
    if technique is not None and (not technique.strip() or len(technique) > 100):
        raise ApiError("bad_request", "'technique' must be 1 to 100 characters.", 400)
    if cursor:
        _incident_id(cursor)
    try:
        limit = int(request.args.get("limit", 25))
    except ValueError:
        raise ApiError("bad_request", "'limit' must be a whole number.", 400)
    if not 1 <= limit <= 100:
        raise ApiError("bad_request", "'limit' must be between 1 and 100.", 400)
    start = _incident_time_arg("start", "from")
    end = _incident_time_arg("end", "to")
    if start and end and start > end:
        raise ApiError("bad_request", "'start' must be before 'end'.", 400)
    try:
        result = _ctx()["hooks"].require("incidents").list_page(
            status=status,
            severity=severity,
            host=host.strip() if host else None,
            technique=technique.strip() if technique else None,
            start=start,
            end=end,
            sort=sort,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as exc:
        raise ApiError("bad_request", str(exc), 400)
    result["items"] = [_out("incident", item) for item in result["items"]]
    return jsonify(result)


@bp.get("/incidents/<incident_id>/timeline")
@auth.json_login_required
@auth.rate_limit(max_requests=90, window_seconds=60)
def incident_timeline(incident_id):
    incident_id = _incident_id(incident_id)
    engine = _ctx()["hooks"].require("incidents")
    if engine.get(incident_id) is None:
        raise ApiError("not_found", "No incident with id %s." % incident_id, 404)
    return jsonify([_out("timeline_event", event) for event in engine.timeline(incident_id)])


@bp.get("/incidents/<incident_id>/export")
@auth.json_login_required
@auth.rate_limit(max_requests=12, window_seconds=60)
def incident_export(incident_id):
    incident_id = _incident_id(incident_id)
    engine = _ctx()["hooks"].require("incidents")
    incident = engine.get(incident_id)
    if incident is None:
        raise ApiError("not_found", "No incident with id %s." % incident_id, 404)
    incident = _out("incident", incident)
    timeline = [_out("timeline_event", event) for event in engine.timeline(incident_id)]
    export_format = request.args.get("format", "json").lower()
    if export_format == "json":
        response = jsonify({
            "incident": incident,
            "timeline": timeline,
            "simulation_note": "Scripted replay data only. Containment changes simulated in-memory state; it does not affect a real network.",
        })
        response.headers["Content-Disposition"] = 'attachment; filename="%s.json"' % incident_id
        return response
    if export_format != "markdown":
        raise ApiError("bad_request", "'format' must be json or markdown.", 400)
    import html

    lines = [
        "# %s — %s" % (incident_id, html.escape(incident["title"])),
        "",
        "**SIMULATION:** Scripted replay data only. Containment changes simulated in-memory state; no real network is affected.",
        "",
        "- Status: %s" % incident["status"],
        "- Severity: %s" % incident["severity"],
        "- Scenario: %s" % (incident["scenario_id"] or "unknown"),
        "- Affected hosts: %s" % (", ".join(incident["affected_hosts"]) or "none"),
        "- Compromised hosts: %s" % (", ".join(incident["compromised_hosts"]) or "none"),
        "",
        "## Timeline",
    ]
    lines.extend("- %s — %s" % (item["timestamp"], html.escape(item["summary"])) for item in timeline)
    if incident["notes"]:
        lines.extend(["", "## Analyst notes"])
        lines.extend("- %s (%s, %s): %s" % (note["created_at"], note["author"], note["role"], html.escape(note["body"])) for note in incident["notes"])
    response = Response("\n".join(lines) + "\n", mimetype="text/markdown")
    response.headers["Content-Disposition"] = 'attachment; filename="%s.md"' % incident_id
    return response


@bp.get("/incidents/<incident_id>")
@auth.json_login_required
@auth.rate_limit(max_requests=90, window_seconds=60)
def incident_detail(incident_id):
    incident_id = _incident_id(incident_id)
    incident = _ctx()["hooks"].require("incidents").get(incident_id)
    if incident is None:
        raise ApiError("not_found", "No incident with id %s." % incident_id, 404)
    return jsonify(_out("incident", incident))


@bp.post("/incidents/<incident_id>/notes")
@auth.role_required("analyst")
def incident_note_add(incident_id):
    incident_id = _incident_id(incident_id)
    data = _body()
    if set(data) != {"body"}:
        raise ApiError("bad_request", "Send exactly one field: body.", 400)
    engine = _ctx()["hooks"].require("incidents")
    try:
        note = engine.add_note(incident_id, data.get("body"), current_user.username, auth.current_role())
    except KeyError:
        raise ApiError("not_found", "No incident with id %s." % incident_id, 404)
    except ValueError as exc:
        raise ApiError("bad_request", str(exc), 400)
    return jsonify(_out("incident_note", note)), 201


@bp.post("/incidents/<incident_id>/status")
@auth.role_required("analyst")
def incident_status_change(incident_id):
    incident_id = _incident_id(incident_id)
    data = _body()
    if set(data) != {"status", "reason", "confirm"}:
        raise ApiError("bad_request", "Send status, reason and confirm.", 400)
    engine = _ctx()["hooks"].require("incidents")
    try:
        incident = engine.change_status(
            incident_id,
            data.get("status"),
            data.get("reason"),
            data.get("confirm"),
            current_user.username,
            auth.current_role(),
        )
    except KeyError:
        raise ApiError("not_found", "No incident with id %s." % incident_id, 404)
    except ValueError as exc:
        raise ApiError("bad_request", str(exc), 400)
    return jsonify(_out("incident", incident))


# ---------- replay studio, scenarios and run history ----------
def _studio():
    return _ctx()["hooks"].require("studio")


@bp.get("/scenarios")
@auth.json_login_required
def scenario_library():
    items = [_out("scenario_summary", item) for item in _studio().scenarios()]
    return jsonify(_out("scenario_library", {"items": items}))


@bp.get("/scenarios/options")
@auth.json_login_required
def scenario_builder_options():
    studio = _studio()
    graph = _ctx()["hooks"].require("graph")
    events = _ctx()["hooks"].require("events")
    table = getattr(events, "techniques", None) or getattr(getattr(events, "_delegate", None), "techniques", None)
    hosts = [{"host_id": host_id, "name": info.get("name", host_id), "zone": info.get("zone", "unknown")}
             for host_id, info in sorted(studio.topology.hosts.items())]
    techniques = [{"id": item_id, "name": table.require(item_id).get("name", item_id),
                   "tactics": list(table.require(item_id).get("tactics", []))}
                  for item_id in sorted(studio.technique_ids)] if table is not None else []
    return jsonify(_out("scenario_builder_options", {"hosts": hosts, "techniques": techniques}))


@bp.get("/scenarios/<scenario_id>")
@auth.json_login_required
def scenario_get(scenario_id):
    found = _studio().get_scenario(scenario_id)
    if found is None:
        raise ApiError("not_found", "There is no scenario called '%s'." % scenario_id, 404)
    return jsonify(found)


@bp.get("/scenarios/<scenario_id>/export")
@auth.json_login_required
def scenario_export(scenario_id):
    found = _studio().get_scenario(scenario_id)
    if found is None:
        raise ApiError("not_found", "There is no scenario called '%s'." % scenario_id, 404)
    response = jsonify(found["scenario"])
    response.headers["Content-Disposition"] = 'attachment; filename="%s.json"' % scenario_id
    return response


@bp.post("/scenarios/validate")
@auth.role_required("analyst")
@auth.rate_limit(max_requests=20, window_seconds=60)
def scenario_validate():
    data = _body()
    if set(data) != {"scenario"}:
        raise ApiError("bad_request", "Send exactly one field: scenario.", 400)
    return jsonify(_studio().validate(data["scenario"]))


@bp.post("/scenarios/dry-run")
@auth.role_required("analyst")
@auth.rate_limit(max_requests=5, window_seconds=60)
def scenario_dry_run():
    data = _body()
    if set(data) != {"scenario"}:
        raise ApiError("bad_request", "Send exactly one field: scenario.", 400)
    try:
        return jsonify(_studio().dry_run(data["scenario"]))
    except ValueError as exc:
        raise ApiError("bad_request", str(exc), 400)


@bp.post("/scenarios")
@auth.role_required("analyst")
@auth.rate_limit(max_requests=20, window_seconds=60)
def scenario_save():
    data = _body()
    if set(data) != {"scenario"}:
        raise ApiError("bad_request", "Send exactly one field: scenario.", 400)
    try:
        return jsonify(_studio().save_scenario(data["scenario"])), 201
    except ValueError as exc:
        raise ApiError("bad_request", str(exc), 400)


@bp.delete("/scenarios/<scenario_id>")
@auth.role_required("analyst")
@auth.rate_limit(max_requests=20, window_seconds=60)
def scenario_delete(scenario_id):
    try:
        _studio().delete_scenario(scenario_id)
    except KeyError:
        raise ApiError("not_found", "There is no saved user scenario called '%s'." % scenario_id, 404)
    except ValueError as exc:
        raise ApiError("bad_request", str(exc), 400)
    return jsonify({"scenario_id": scenario_id, "deleted": True})


@bp.get("/replay/studio/status")
@auth.json_login_required
def replay_studio_status():
    replay = _ctx()["hooks"].require("replay")
    studio = _studio()
    return jsonify(_out("studio_status", {"status": replay.status(), "active_run": studio.active()}))


@bp.post("/replay/studio/start")
@auth.role_required("analyst")
@auth.rate_limit(max_requests=10, window_seconds=60)
def replay_studio_start():
    data = _body()
    if set(data) - {"scenario_id", "speed"} or "scenario_id" not in data:
        raise ApiError("bad_request", "Send scenario_id and optional speed.", 400)
    speed = data.get("speed", 1.0)
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0.25 <= float(speed) <= 8:
        raise ApiError("bad_request", "Studio speed must be between 0.25x and 8x.", 400)
    replay = _ctx()["hooks"].require("replay")
    status = replay.start(_text(data, "scenario_id"), float(speed), paused=True)
    return jsonify(_out("studio_status", {"status": status, "active_run": _studio().active()}))


@bp.post("/replay/step")
@auth.role_required("analyst")
def replay_step():
    _body()
    replay = _ctx()["hooks"].require("replay")
    status = replay.step()
    if _ctx()["hooks"].get("studio") is None:
        return jsonify(status)
    return jsonify(_out("studio_status", {"status": status, "active_run": _studio().active()}))


@bp.post("/replay/step-back")
@auth.role_required("analyst")
def replay_step_back():
    _body()
    replay = _ctx()["hooks"].require("replay")
    status = replay.step_back()
    return jsonify(_out("studio_status", {"status": status, "active_run": _studio().active()}))


@bp.post("/replay/seek")
@auth.role_required("analyst")
def replay_seek():
    data = _body()
    if set(data) != {"position"}:
        raise ApiError("bad_request", "Send exactly one field: position.", 400)
    status = _ctx()["hooks"].require("replay").seek(data["position"])
    return jsonify(_out("studio_status", {"status": status, "active_run": _studio().active()}))


@bp.post("/replay/speed")
@auth.role_required("analyst")
def replay_speed():
    data = _body()
    if set(data) != {"speed"}:
        raise ApiError("bad_request", "Send exactly one field: speed.", 400)
    status = _ctx()["hooks"].require("replay").set_speed(data["speed"])
    return jsonify(_out("studio_status", {"status": status, "active_run": _studio().active()}))


@bp.post("/replay/breakpoints")
@auth.role_required("analyst")
def replay_breakpoints():
    data = _body()
    if set(data) != {"sequences"}:
        raise ApiError("bad_request", "Send exactly one field: sequences.", 400)
    values = _ctx()["hooks"].require("replay").set_breakpoints(data["sequences"])
    return jsonify(_out("breakpoint_set", {"sequences": values}))


@bp.get("/runs")
@auth.json_login_required
def runs_list():
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        raise ApiError("bad_request", "'limit' must be a whole number.", 400)
    if not 1 <= limit <= 50:
        raise ApiError("bad_request", "'limit' must be between 1 and 50.", 400)
    return jsonify([_out("run_summary", item) for item in _studio().list_runs(limit)])


@bp.get("/runs/compare")
@auth.json_login_required
def runs_compare():
    first_id, second_id = request.args.get("a", ""), request.args.get("b", "")
    if not RUN_ID.fullmatch(first_id) or not RUN_ID.fullmatch(second_id):
        raise ApiError("bad_request", "Supply run ids with the RUN-000001 format as a and b.", 400)
    try:
        return jsonify(_studio().compare(first_id, second_id))
    except KeyError as exc:
        raise ApiError("not_found", "No run with id %s." % exc.args[0], 404)


@bp.get("/runs/<run_id>/snapshots")
@auth.json_login_required
def run_snapshots(run_id):
    if not RUN_ID.fullmatch(run_id):
        raise ApiError("bad_request", "Run id must use the RUN-000001 format.", 400)
    result = _studio().snapshot_index(run_id)
    if result is None:
        raise ApiError("not_found", "No run with id %s." % run_id, 404)
    return jsonify(result)


@bp.get("/runs/<run_id>")
@auth.json_login_required
def run_get(run_id):
    if not RUN_ID.fullmatch(run_id):
        raise ApiError("bad_request", "Run id must use the RUN-000001 format.", 400)
    result = _studio().get_run(run_id)
    if result is None:
        raise ApiError("not_found", "No run with id %s." % run_id, 404)
    return jsonify(_out("run_detail", {"summary": _out("run_summary", result["summary"]), "final_state": result.get("final_state")}))


@bp.get("/snapshots")
@auth.json_login_required
def snapshot_get():
    run_id = request.args.get("run", "")
    if not RUN_ID.fullmatch(run_id):
        raise ApiError("bad_request", "Supply a run id with the RUN-000001 format.", 400)
    version_text = request.args.get("version")
    version = None
    if version_text is not None:
        try:
            version = int(version_text)
        except ValueError:
            raise ApiError("bad_request", "'version' must be a whole number.", 400)
        if version < 0:
            raise ApiError("bad_request", "'version' cannot be negative.", 400)
    result = _studio().get_snapshot(run_id, version)
    if result is None:
        raise ApiError("not_found", "No run snapshot matches that run and version.", 404)
    return jsonify(result)


# ---------- read-only network digital twin ----------
def _twin():
    return _ctx()["hooks"].require("twin")


@bp.get("/topology")
@auth.json_login_required
def topology_get():
    return jsonify(_out("topology", _twin().topology_view()))


@bp.get("/topology/paths")
@auth.json_login_required
@auth.rate_limit(max_requests=30, window_seconds=60)
def topology_paths_get():
    source, target = request.args.get("from", ""), request.args.get("to", "")
    if not source or not target:
        raise ApiError("bad_request", "Supply from and to host ids.", 400)
    try:
        limit = int(request.args.get("limit", "10"))
        result = _twin().paths(source, target, limit)
    except ValueError as exc:
        raise ApiError("bad_request", str(exc), 400)
    except KeyError as exc:
        raise ApiError("not_found", "Unknown demo host %s." % exc.args[0], 404)
    return jsonify(_out("topology_paths", result))


@bp.get("/topology/segmentation-preview")
@auth.json_login_required
@auth.rate_limit(max_requests=20, window_seconds=60)
def topology_segmentation_preview():
    source = request.args.get("from", "")
    remove_from = request.args.get("remove_from", "")
    remove_to = request.args.get("remove_to", "")
    if not source or not remove_from or not remove_to:
        raise ApiError("bad_request", "Supply from, remove_from and remove_to host ids.", 400)
    try:
        result = _twin().segmentation_preview(source, remove_from, remove_to)
    except ValueError as exc:
        raise ApiError("bad_request", str(exc), 400)
    except KeyError as exc:
        raise ApiError("not_found", "Unknown demo host %s." % exc.args[0], 404)
    return jsonify(_out("segmentation_preview", result))


@bp.get("/hosts/<host_id>")
@auth.json_login_required
def host_detail_get(host_id):
    try:
        result = _twin().host_detail(host_id)
    except KeyError:
        raise ApiError("not_found", "There is no host with id %s." % host_id, 404)
    return jsonify(_out("host_detail", result))


@bp.get("/hosts/<host_id>/history")
@auth.json_login_required
@auth.rate_limit(max_requests=20, window_seconds=60)
def host_history_get(host_id):
    try:
        limit = int(request.args.get("limit", "200"))
        result = _twin().host_history(host_id, limit)
    except ValueError as exc:
        raise ApiError("bad_request", str(exc), 400)
    except KeyError:
        raise ApiError("not_found", "There is no host with id %s." % host_id, 404)
    return jsonify(_out("host_history", result))


# ---------- anything else under /api/x ----------


# Compatibility endpoints retained from the Phase B operator workspace.
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

def _find_incident(incident_id):
    return next((item for item in _incident_records(_ctx()) if item["incident_id"] == incident_id), None)

def _audit_incident(incident_id, summary):
    events = _ctx()["hooks"].get("events")
    recorder = getattr(events, "audit_record", None) if events is not None else None
    if recorder is not None:
        recorder("incident", incident_id, summary)

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
    model = engine.model
    probabilities = model.probabilities(from_host, candidates) if model is not None else {}
    if not probabilities:
        weights = {host_id: max(float(graph.topology.edge_probability(from_host, host_id)), 0.01) for host_id in candidates}
        total = sum(weights.values()) or 1.0
        probabilities = {host_id: weight / total for host_id, weight in weights.items()}
    ranked = sorted(probabilities.items(), key=lambda item: (-item[1], item[0]))
    targets = [{"rank": index + 1, "host_id": host_id, "confidence": round(probability, 4)}
               for index, (host_id, probability) in enumerate(ranked[:3])]
    weights = {host_id: max(float(graph.topology.edge_probability(from_host, host_id)), 0.01) for host_id in candidates}
    weight_total = sum(weights.values()) or 1.0
    rule = {host_id: weight / weight_total for host_id, weight in weights.items()}
    rule_order = {host_id: index + 1 for index, (host_id, _) in enumerate(sorted(rule.items(), key=lambda item: (-item[1], item[0])))}
    model_order = {host_id: index + 1 for index, (host_id, _) in enumerate(ranked)}
    uniform_order = {host_id: index + 1 for index, host_id in enumerate(sorted(candidates))}
    alpha = model.alpha if model is not None else 0.0
    counts = model.counts.get(from_host, {}) if model is not None else {}
    candidate_set = [{"host_id": host_id, "transition_count": int(counts.get(host_id, 0)),
        "model_probability": round(probabilities[host_id], 6), "model_rank": model_order[host_id],
        "rule_based_probability": round(rule[host_id], 6), "rule_based_rank": rule_order[host_id],
        "uniform_probability": round(1 / len(candidates), 6), "uniform_rank": uniform_order[host_id]}
        for host_id in candidates]
    hint, hint_source = engine.layer.hint(engine._last_technique(from_host)) if engine.layer else (None, "lookup")
    payload = {"from_host": from_host,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "targets": targets, "technique_hint": hint, "source": getattr(engine.layer, "default_source", "lookup"),
        "explanation": {"model": {"name": "markov" if model is not None else "rule-based", "alpha": alpha},
            "technique_hint_source": hint_source, "candidate_count": len(candidates), "candidate_set": candidate_set},
        "note": "Read-only simulation preview. This does not create a forecast, change host state, or affect the replay."}
    return jsonify(_out("what_if_forecast", payload))

@bp.get("/forecasts/<forecast_id>")
@auth.json_login_required
def forecast_detail(forecast_id):
    found = next((item for item in _ctx()["world"].forecasts(include_archived=True) if item.get("forecast_id") == forecast_id), None)
    if found is None:
        raise ApiError("not_found", "No forecast with id %s." % forecast_id, 404)
    return jsonify(_out("forecast", found))

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

def _session_comparison_item(record):
    alerts = record.get("alerts", [])
    forecasts = record.get("forecasts", [])
    outcomes = [item.get("outcome") for item in forecasts if item.get("status") in ("hit", "miss") and item.get("outcome")]
    rank_hits = [item.get("rank_hit") for item in outcomes]
    resolved = len(rank_hits)
    hits = sum(rank is not None for rank in rank_hits)
    actions = record.get("actions", [])
    return {
        "session_id": record["session_id"], "scenario_id": record.get("scenario_id"),
        "started_at": record["started_at"], "ended_at": record.get("ended_at"),
        "alert_count": len(alerts),
        "severity_counts": {severity: sum(item.get("severity") == severity for item in alerts) for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW")},
        "forecast_count": len(forecasts), "resolved_forecasts": resolved, "hits": hits, "misses": resolved - hits,
        "precision_at_1": (sum(rank == 1 for rank in rank_hits) / resolved) if resolved else None,
        "precision_at_3": (hits / resolved) if resolved else None,
        "containment_actions": sum(item.get("operation", "contain") == "contain" for item in actions),
        "successful_containments": sum(item.get("operation", "contain") == "contain" and item.get("status") == "executed" for item in actions),
    }

@bp.get("/sessions/compare")
@auth.json_login_required
def compare_sessions():
    left_id = _query_text("left", 128)
    right_id = _query_text("right", 128)
    if not left_id or not right_id:
        raise ApiError("bad_request", "Choose both left and right session ids.", 400)
    if left_id == right_id:
        raise ApiError("bad_request", "Choose two different replay sessions.", 400)
    records = {item["session_id"]: item for item in _ctx()["world"].sessions()}
    left, right = records.get(left_id), records.get(right_id)
    if left is None or right is None:
        raise ApiError("not_found", "One or both replay sessions were not found.", 404)
    if not left.get("ended_at") or not right.get("ended_at"):
        raise ApiError("session_not_finished", "Session comparison is available for finished replays.", 409)
    payload = {
        "left": _session_comparison_item(left), "right": _session_comparison_item(right),
        "simulation_only": True,
        "note": "These are session counters, not the model's overall accuracy.",
    }
    return jsonify(_out("session_comparison", payload))

@bp.get("/time-travel")
@auth.json_login_required
def time_travel():
    try:
        limit = int(request.args.get("limit", 120))
    except ValueError:
        raise ApiError("bad_request", "'limit' must be a whole number.", 400)
    if limit < 1:
        raise ApiError("bad_request", "'limit' must be at least 1.", 400)
    session_id = _query_text("session_id", 128)
    snapshots = _ctx()["world"].time_travel(session_id=session_id, limit=limit)
    return jsonify([_out("time_travel_snapshot", item) for item in snapshots])

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

@bp.get("/replay/scenarios/<scenario_id>")
@auth.json_login_required
def replay_scenario_detail(scenario_id):
    scenario = _ctx()["hooks"].require("replay").library.get(scenario_id)
    if scenario is None:
        raise ApiError("not_found", "No scenario with id %s." % scenario_id, 404)
    return jsonify(scenario)

@bp.post("/replay/scenarios")
@auth.demo_role_required("analyst", "admin")
def replay_scenario_save():
    if request.content_length and request.content_length > 262144:
        raise ApiError("payload_too_large", "A scenario must be 256 KiB or smaller.", 413)
    replay = _ctx()["hooks"].require("replay")
    try:
        scenario = replay.library.save_custom(_body())
    except ValueError as exc:
        raise ApiError("invalid_scenario", str(exc), 400)
    return jsonify(scenario), 201

@bp.route("/<path:rest>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def not_found(rest):
    raise ApiError("not_found", "There is no endpoint '/api/x/%s' for this method." % rest, 404)

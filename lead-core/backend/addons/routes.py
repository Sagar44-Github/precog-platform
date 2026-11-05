"""All new routes. They live under /api/x so they never clash with NIDS's own routes.

Every error answers JSON like {"error": {"code": "...", "message": "..."}}.
"""
from flask import Blueprint, Response, current_app, jsonify, request
from flask_login import current_user
from werkzeug.exceptions import HTTPException
from urllib.parse import urlsplit
from datetime import datetime, timezone
import re

from . import auth
from .contracts import ContractError
from .errors import ApiError

bp = Blueprint("precog_addons", __name__, url_prefix="/api/x")

FORECAST_STATUSES = ("pending", "hit", "miss", "superseded")
REQUESTERS = ("console", "mobile")
MAX_ALERT_LIMIT = 200
INCIDENT_STATUSES = ("open", "contained", "closed", "reopened")
INCIDENT_SEVERITIES = ("HIGH", "MEDIUM", "LOW")
INCIDENT_SORTS = ("updated_desc", "created_asc", "severity_desc")
INCIDENT_ID = re.compile(r"^INC-[0-9]{4}$")
RUN_ID = re.compile(r"^RUN-[0-9]{6}$")
MAX_WRITE_BYTES = 32768


def _ctx():
    return current_app.extensions["precog"]


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
        result["changed"] = since is None or since != result["revision"]
    return jsonify(_out("feed_versions", result))


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


# ---------- anything else under /api/x ----------
@bp.route("/<path:rest>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def not_found(rest):
    raise ApiError("not_found", "There is no endpoint '/api/x/%s' for this method." % rest, 404)

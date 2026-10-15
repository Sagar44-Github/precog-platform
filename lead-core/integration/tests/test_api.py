"""The /api/x routes, tested through Flask's test client (no real server needed)."""
import copy
import os

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]  # set by conftest.py

SAMPLE_ACTION = {
    "action_id": "act-000009", "target_host": "server-b", "forecast_id": "fc-000001", "requested_by": "mobile",
    "status": "pending_confirmation", "proposed_at": "2026-10-03T10:00:05Z", "confirmed_at": None, "result": None,
}
SAMPLE_REPLAY = {"state": "running", "scenario_id": "golden-path", "speed": 1.0, "position": 2}


def err(reply):
    return reply.get_json()["error"]


# ---------- health, login ----------
def test_health_needs_no_login(client):
    reply = client.get("/api/x/health")
    assert reply.status_code == 200
    body = reply.get_json()
    assert body["status"] == "ok" and body["data_mode"] == "sample"
    assert set(body["modules"]) == {"detect_events", "graph_replay", "graph_net", "viz_containment"}


def test_protected_routes_answer_401_json_not_a_redirect(client):
    for path in ("/api/x/state", "/api/x/alerts", "/api/x/graph", "/api/x/me", "/api/x/forecasts/current"):
        reply = client.get(path)
        assert reply.status_code == 401, path
        assert err(reply)["code"] == "not_logged_in"


def test_wrong_password_is_refused(client):
    reply = client.post("/api/x/login", json={"username": "admin", "password": "wrong-password"})
    assert reply.status_code == 401 and err(reply)["code"] == "invalid_credentials"


def test_nids_default_password_no_longer_works(client):
    reply = client.post("/api/x/login", json={"username": "admin", "password": "password123"})
    assert reply.status_code == 401


def test_login_without_a_json_body_is_a_clean_400(client):
    reply = client.post("/api/x/login", data="not json", content_type="text/plain")
    assert reply.status_code == 400 and err(reply)["code"] == "bad_request"


def test_login_me_logout_cycle(client):
    assert client.post("/api/x/login", json={"username": "admin", "password": ADMIN_PASSWORD}).status_code == 200
    assert client.get("/api/x/me").get_json()["username"] == "admin"
    assert client.post("/api/x/logout").status_code == 200
    assert client.get("/api/x/me").status_code == 401


# ---------- polling ----------
def test_state_full_then_unchanged_then_changed(logged_in, world):
    first = logged_in.get("/api/x/state").get_json()
    assert first["changed"] is True and first["forecast"]["forecast_id"] == "fc-000001"
    again = logged_in.get("/api/x/state?since=%d" % first["version"]).get_json()
    assert again == {"version": first["version"], "changed": False}
    world.set_replay(SAMPLE_REPLAY)
    changed = logged_in.get("/api/x/state?since=%d" % first["version"]).get_json()
    assert changed["changed"] is True and changed["replay"]["state"] == "running"


def test_state_rejects_a_bad_since(logged_in):
    reply = logged_in.get("/api/x/state?since=abc")
    assert reply.status_code == 400 and err(reply)["code"] == "bad_request"


# ---------- reading ----------
def test_alerts_limit_and_single_alert(logged_in):
    assert len(logged_in.get("/api/x/alerts?limit=1").get_json()) == 1
    assert logged_in.get("/api/x/alerts?limit=abc").status_code == 400
    assert logged_in.get("/api/x/alerts/evt-000001").get_json()["host"] == "host-a"
    assert err(logged_in.get("/api/x/alerts/evt-404"))["code"] == "not_found"


def test_graph_forecasts_and_filters(logged_in):
    assert len(logged_in.get("/api/x/graph").get_json()["hosts"]) == 6
    assert len(logged_in.get("/api/x/forecasts").get_json()) == 1
    assert logged_in.get("/api/x/forecasts?status=pending").get_json()[0]["status"] == "pending"
    assert logged_in.get("/api/x/forecasts?status=bogus").status_code == 400
    assert logged_in.get("/api/x/forecasts/current").get_json()["targets"][0]["host_id"] == "server-b"


def test_no_pending_forecast_is_a_clean_404(logged_in, world):
    world.resolve_forecast("fc-000001", "miss", {"attempted_host": "host-b", "rank_hit": 2, "blocked": False})
    reply = logged_in.get("/api/x/forecasts/current")
    assert reply.status_code == 404 and err(reply)["code"] == "no_forecast"


def test_session_metrics_and_detection_report(logged_in):
    assert logged_in.get("/api/x/session").get_json()["session_id"] == "ses-000001"
    assert logged_in.get("/api/x/sessions").get_json() == []
    assert logged_in.get("/api/x/metrics/precog").get_json()["forecasts_resolved"] == 0
    assert logged_in.get("/api/x/metrics/detection").get_json()["dataset"] == "CICIDS2017"
    assert logged_in.get("/api/x/containment/actions").get_json()[0]["action_id"] == "act-000001"


# ---------- containment hook ----------
class StandInContainment:
    """A tiny fake of VIZ's module, only for these tests."""

    def propose(self, world, target_host, forecast_id, requested_by):
        action = dict(copy.deepcopy(SAMPLE_ACTION), target_host=target_host, forecast_id=forecast_id, requested_by=requested_by)
        world.upsert_action(action)
        return action

    def confirm(self, world, action_id):
        action = dict(world.get_action(action_id), status="executed", confirmed_at="2026-10-03T10:00:09Z", result="Contained")
        world.upsert_action(action)
        return action

    def cancel(self, world, action_id):
        action = dict(world.get_action(action_id), status="cancelled")
        world.upsert_action(action)
        return action


def test_containment_without_the_viz_module_is_501_not_built(logged_in, hooks):
    reply = logged_in.post("/api/x/containment/propose", json={"target_host": "server-b"})
    assert reply.status_code == 501 and err(reply)["code"] == "not_built"


def test_containment_two_step_flow_with_a_stand_in(logged_in, hooks, world):
    hooks.register("containment", StandInContainment())
    proposed = logged_in.post("/api/x/containment/propose", json={"target_host": "db-server", "forecast_id": "fc-000001", "requested_by": "mobile"})
    assert proposed.status_code == 200 and proposed.get_json()["status"] == "pending_confirmation"
    confirmed = logged_in.post("/api/x/containment/confirm", json={"action_id": "act-000009"}).get_json()
    assert confirmed["status"] == "executed"
    assert world.get_action("act-000009")["status"] == "executed"


def test_containment_cancel_with_a_stand_in(logged_in, hooks):
    hooks.register("containment", StandInContainment())
    logged_in.post("/api/x/containment/propose", json={"target_host": "db-server"})
    assert logged_in.post("/api/x/containment/cancel", json={"action_id": "act-000009"}).get_json()["status"] == "cancelled"


def test_containment_input_checks(logged_in, hooks):
    hooks.register("containment", StandInContainment())
    assert logged_in.post("/api/x/containment/propose", json={}).status_code == 400
    assert logged_in.post("/api/x/containment/propose", json={"target_host": "x", "requested_by": "robot"}).status_code == 400
    assert logged_in.post("/api/x/containment/confirm", json={"action_id": ""}).status_code == 400


def test_a_module_returning_bad_data_is_caught_as_contract_violation(logged_in, hooks):
    class Broken(StandInContainment):
        def propose(self, world, target_host, forecast_id, requested_by):
            return {"action_id": "act-1", "status": "pending_confirmation"}  # most fields missing

    hooks.register("containment", Broken())
    reply = logged_in.post("/api/x/containment/propose", json={"target_host": "server-b"})
    assert reply.status_code == 500 and err(reply)["code"] == "contract_violation"


def test_a_module_can_raise_a_clean_error(logged_in, hooks):
    from addons.errors import HookError

    class Refuses(StandInContainment):
        def confirm(self, world, action_id):
            raise HookError("expired", "That action has expired.", 409)

    hooks.register("containment", Refuses())
    reply = logged_in.post("/api/x/containment/confirm", json={"action_id": "act-000001"})
    assert reply.status_code == 409 and err(reply)["code"] == "expired"


# ---------- replay hook ----------
class StandInReplay:
    def list_scenarios(self):
        return [{"scenario_id": "golden-path", "description": "stand-in"}]

    def status(self):
        return dict(SAMPLE_REPLAY)

    def start(self, scenario_id, speed):
        return dict(SAMPLE_REPLAY, scenario_id=scenario_id, speed=speed)

    def pause(self):
        return dict(SAMPLE_REPLAY, state="paused")

    def resume(self):
        return dict(SAMPLE_REPLAY, state="running")

    def restart(self):
        return dict(SAMPLE_REPLAY, position=0)


def test_replay_status_falls_back_to_the_world_when_no_module(logged_in, hooks):
    assert logged_in.get("/api/x/replay/status").get_json()["state"] == "waiting_for_decision"
    assert logged_in.get("/api/x/replay/scenarios").status_code == 501
    assert logged_in.post("/api/x/replay/start", json={"scenario_id": "golden-path"}).status_code == 501


def test_replay_controls_with_a_stand_in(logged_in, hooks):
    hooks.register("replay", StandInReplay())
    assert logged_in.get("/api/x/replay/scenarios").get_json()[0]["scenario_id"] == "golden-path"
    assert logged_in.post("/api/x/replay/start", json={"scenario_id": "golden-path", "speed": 2}).get_json()["speed"] == 2.0
    assert logged_in.post("/api/x/replay/pause").get_json()["state"] == "paused"
    assert logged_in.post("/api/x/replay/resume").get_json()["state"] == "running"
    assert logged_in.post("/api/x/replay/restart").get_json()["position"] == 0


def test_replay_start_input_checks(logged_in, hooks):
    hooks.register("replay", StandInReplay())
    assert logged_in.post("/api/x/replay/start", json={}).status_code == 400
    assert logged_in.post("/api/x/replay/start", json={"scenario_id": "a", "speed": 0}).status_code == 400
    assert logged_in.post("/api/x/replay/start", json={"scenario_id": "a", "speed": "fast"}).status_code == 400
    assert logged_in.post("/api/x/replay/start", json={"scenario_id": "a", "speed": True}).status_code == 400


# ---------- push, unknown paths ----------
def test_push_register_stores_each_token_once(logged_in, world):
    assert logged_in.post("/api/x/push/register", json={"token": "tok-1"}).get_json()["count"] == 1
    assert logged_in.post("/api/x/push/register", json={"token": "tok-1"}).get_json()["count"] == 1
    assert logged_in.post("/api/x/push/register", json={"token": "x" * 5000}).status_code == 400
    assert logged_in.post("/api/x/push/register", json={}).status_code == 400


def test_unknown_api_path_and_wrong_method_are_json_404(logged_in):
    assert err(logged_in.get("/api/x/nothing-here"))["code"] == "not_found"
    assert err(logged_in.post("/api/x/state"))["code"] == "not_found"

def scenario(scenario_id="custom-probe", host="host-a"):
    return {
        "scenario_id": scenario_id,
        "description": "A short simulated reconnaissance sequence.",
        "events": [{"seq": 1, "offset_ms": 0, "kind": "technique", "host": host, "technique_id": "T1046"}],
    }


def test_time_travel_returns_contract_checked_read_only_snapshots(logged_in, world):
    before = world.version
    reply = logged_in.get("/api/x/time-travel?limit=1")
    assert reply.status_code == 200
    snapshots = reply.get_json()
    assert len(snapshots) == 1 and snapshots[0]["version"] >= before
    assert snapshots[0]["graph"]["hosts"] and snapshots[0]["replay"]["state"]
    assert logged_in.get("/api/x/time-travel?limit=not-a-number").status_code == 400
    assert logged_in.get("/api/x/time-travel?limit=0").status_code == 400


def test_scenario_builder_validates_saves_and_loads_custom_scenarios(logged_in, ctx, tmp_path):
    from graph_replay import ScenarioLibrary

    known_hosts = {"host-a", "host-b", "server-b", "file-server", "db-server", "domain-controller"}
    library = ScenarioLibrary(known_hosts=known_hosts, custom_folder=tmp_path)
    original_replay = ctx["hooks"].get("replay")

    class ReplayLibrary:
        def __init__(self, scenario_library):
            self.library = scenario_library

        def list_scenarios(self):
            return self.library.summaries()

    ctx["hooks"].register("replay", ReplayLibrary(library))
    try:
        reply = logged_in.post("/api/x/replay/scenarios", json=scenario())
        assert reply.status_code == 201, reply.get_json()
        assert reply.get_json()["scenario_id"] == "custom-probe"
        assert logged_in.get("/api/x/replay/scenarios/custom-probe").get_json()["events"][0]["host"] == "host-a"
        summary = next(item for item in logged_in.get("/api/x/replay/scenarios").get_json() if item["scenario_id"] == "custom-probe")
        assert summary["custom"] is True and summary["events"] == 1
        assert (tmp_path / "custom-probe.json").is_file()
        assert logged_in.post("/api/x/replay/scenarios", json=scenario()).status_code == 400
        assert logged_in.post("/api/x/replay/scenarios", json=scenario("custom-ghost", "ghost")).status_code == 400
    finally:
        if original_replay is None:
            ctx["hooks"]._items.pop("replay", None)
        else:
            ctx["hooks"].register("replay", original_replay)


def _finished_session(session_id, scenario_id, severity, rank=None, action_count=0, include_forecast=False):
    forecasts = []
    if include_forecast:
        forecasts.append({"status": "hit" if rank is not None else "miss", "outcome": {"rank_hit": rank}})
    alerts = [{"severity": severity}] if severity else []
    actions = [{"operation": "contain", "status": "executed"}] * action_count
    return {
        "session_id": session_id,
        "scenario_id": scenario_id,
        "started_at": "2026-11-04T12:00:00Z",
        "ended_at": "2026-11-04T12:00:05Z",
        "forecasts": forecasts,
        "alerts": alerts,
        "actions": actions,
    }


def test_session_comparison_uses_only_finished_sessions_and_returns_honest_counters(logged_in, world):
    with world._lock:
        original = world._sessions
        world._sessions = [
            _finished_session("ses-left", "golden-path", "HIGH", 1, action_count=1, include_forecast=True),
            _finished_session("ses-right", "quiet-scan", None, include_forecast=True),
        ]
    try:
        reply = logged_in.get("/api/x/sessions/compare?left=ses-left&right=ses-right")
        assert reply.status_code == 200, reply.get_json()
        result = reply.get_json()
        assert result["left"]["alert_count"] == 1 and result["left"]["precision_at_1"] == 1
        assert result["left"]["successful_containments"] == 1
        assert result["right"]["misses"] == 1 and result["right"]["precision_at_3"] == 0
        assert result["simulation_only"] is True and "not the model's overall accuracy" in result["note"]
        assert logged_in.get("/api/x/sessions/compare?left=ses-left&right=ses-left").status_code == 400
        assert logged_in.get("/api/x/sessions/compare?left=missing&right=ses-right").status_code == 404
    finally:
        with world._lock:
            world._sessions = original


def test_session_compare_refuses_active_sessions(logged_in, world):
    record = _finished_session("ses-active", "golden-path", None)
    record["ended_at"] = None
    with world._lock:
        original = world._sessions
        world._sessions = [record, _finished_session("ses-finished", "quiet-scan", None)]
    try:
        reply = logged_in.get("/api/x/sessions/compare?left=ses-active&right=ses-finished")
        assert reply.status_code == 409 and reply.get_json()["error"]["code"] == "session_not_finished"
    finally:
        with world._lock:
            world._sessions = original

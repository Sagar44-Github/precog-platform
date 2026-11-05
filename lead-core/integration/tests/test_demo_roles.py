"""Demo roles are tied to authenticated NIDS usernames and enforced by the server."""

def _seed_user(ctx, username, password):
    nids = ctx["nids"]
    session = nids.SessionLocal()
    try:
        user = session.query(nids.User).filter_by(username=username).first()
        password_hash = nids.bcrypt.generate_password_hash(password).decode("utf-8")
        if user is None:
            session.add(nids.User(username=username, password_hash=password_hash))
        else:
            user.password_hash = password_hash
        session.commit()
    finally:
        session.close()


def test_login_and_me_return_the_server_resolved_operator_profile(client, ctx):
    _seed_user(ctx, "analyst", "analyst-test-password")
    reply = client.post("/api/x/login", json={"username": "analyst", "password": "analyst-test-password"})
    assert reply.status_code == 200
    assert reply.get_json()["role"] == "analyst"
    profile = client.get("/api/x/me").get_json()
    assert profile["role_name"] == "Analyst"
    assert profile["permissions"] == {
        "can_contain": True, "can_run_replay": True, "can_release": False, "can_restart_replay": False,
    }


def test_viewer_cannot_escalate_or_start_mutations(client, ctx):
    _seed_user(ctx, "viewer", "viewer-test-password")
    reply = client.post("/api/x/login", json={"username": "viewer", "password": "viewer-test-password"})
    assert reply.status_code == 200 and reply.get_json()["role"] == "viewer"
    assert reply.get_json()["permissions"]["can_contain"] is False

    replay = client.post("/api/x/replay/start", json={"scenario_id": "golden-path", "role": "admin"})
    contain = client.post("/api/x/containment/propose", json={"target_host": "server-b", "requested_by": "console", "role": "admin"})
    release = client.post("/api/x/containment/release/propose", json={"containment_action_id": "act-000001"})
    for response in (replay, contain, release):
        assert response.status_code == 403
        assert response.get_json()["error"]["code"] == "forbidden"


def test_admin_profile_has_release_and_restart_capabilities(logged_in):
    profile = logged_in.get("/api/x/me").get_json()
    assert profile["role"] == "admin"
    assert profile["permissions"]["can_release"] is True
    assert profile["permissions"]["can_restart_replay"] is True

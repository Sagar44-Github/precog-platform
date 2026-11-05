import json

import pytest

from viz_containment.push import AlertWatcher, FcmSender, LogSender, alert_notification, build_sender_from_env, first_sentence


def alert(event_id="evt-000001", severity="HIGH", host="host-a", ts="2026-10-03T10:00:01Z", explanation="Workstation A sent a 2500-byte TCP packet to port 22 (SSH, remote login) on Workstation B. NIDS rated it high risk."):
    return {"event_id": event_id, "ts": ts, "host": host, "packet_id": None, "anomaly": True, "risk_score": 80.0, "severity": severity,
            "explanation": explanation, "technique_id": None, "technique_name": None, "source": "scripted"}


class Recorder:
    def __init__(self):
        self.sent = []

    def send(self, tokens, notification):
        self.sent.append((list(tokens), notification))
        return len(tokens)


GRAPH = {"hosts": [{"host_id": "host-a", "name": "Workstation A", "zone": "user", "state": "normal"}], "edges": [], "compromised_path": []}


# ---------- the wording (UI/UX brief 11.2) ----------
def test_first_sentence_only():
    assert first_sentence("One. Two. Three.") == "One."
    assert first_sentence("Only one sentence.") == "Only one sentence."
    assert first_sentence("") == ""


def test_notification_title_and_body_follow_the_brief():
    n = alert_notification(alert(), "Workstation A")
    assert n["title"] == "High alert: Workstation A"
    assert n["body"] == "Workstation A sent a 2500-byte TCP packet to port 22 (SSH, remote login) on Workstation B."
    assert n["url"] == "/app/alerts/evt-000001" and n["event_id"] == "evt-000001"


# ---------- the watcher ----------
def test_a_new_high_alert_is_sent_once_to_every_phone(world):
    world.set_graph(GRAPH)
    world.add_push_token("token-1")
    world.add_push_token("token-2")
    sender = Recorder()
    watcher = AlertWatcher(world, sender)
    world.add_alert(alert())
    assert len(watcher.poll_once()) == 1
    assert watcher.poll_once() == [] and len(sender.sent) == 1
    assert sender.sent[0][0] == ["token-1", "token-2"] and sender.sent[0][1]["title"] == "High alert: Workstation A"


def test_only_high_alerts_are_sent(world):
    world.add_push_token("t")
    sender = Recorder()
    watcher = AlertWatcher(world, sender)
    world.add_alert(alert("evt-000001", "MEDIUM"))
    world.add_alert(alert("evt-000002", "LOW"))
    world.add_alert(alert("evt-000003", "HIGH"))
    watcher.poll_once()
    assert [n["event_id"] for _, n in sender.sent] == ["evt-000003"]


def test_alerts_that_exist_when_the_watcher_starts_are_not_announced(world):
    world.add_push_token("t")
    world.add_alert(alert())
    sender = Recorder()
    watcher = AlertWatcher(world, sender)
    watcher.poll_once()
    assert sender.sent == []


def test_nothing_is_sent_when_no_phone_is_registered(world):
    sender = Recorder()
    watcher = AlertWatcher(world, sender)
    world.add_alert(alert())
    watcher.poll_once()
    assert sender.sent == []


def test_a_restarted_replay_with_the_same_event_numbers_is_announced_again(world):
    world.add_push_token("t")
    sender = Recorder()
    watcher = AlertWatcher(world, sender)
    world.add_alert(alert(ts="2026-10-03T10:00:01Z"))
    watcher.poll_once()
    world.reset()
    world.add_alert(alert(ts="2026-10-03T10:05:09Z"))                   # evt-000001 again, a new time
    watcher.poll_once()
    assert len(sender.sent) == 2


def test_an_unknown_host_is_shown_as_it_is(world):
    world.add_push_token("t")
    sender = Recorder()
    watcher = AlertWatcher(world, sender)
    world.add_alert(alert(host="10.9.9.9"))
    watcher.poll_once()
    assert sender.sent[0][1]["title"] == "High alert: 10.9.9.9"


def test_the_background_thread_sends_too(world):
    import time

    world.add_push_token("t")
    sender = Recorder()
    watcher = AlertWatcher(world, sender, interval=0.02)
    watcher.start()
    world.add_alert(alert())
    end = time.monotonic() + 3
    while not sender.sent and time.monotonic() < end:
        time.sleep(0.01)
    watcher.stop()
    assert len(sender.sent) == 1


# ---------- Firebase sending ----------
class Reply:
    def __init__(self, status):
        self.status_code, self.text = status, "x"


def test_fcm_sender_posts_a_data_only_message_per_phone():
    calls = []

    def post(url, headers, json, timeout):
        calls.append((url, headers, json))
        return Reply(200)

    sender = FcmSender("demo-project", lambda: "access-123", post=post)
    n = alert_notification(alert(), "Workstation A")
    assert sender.send(["tok-a", "tok-b"], n) == 2
    url, headers, body = calls[0]
    assert url == "https://fcm.googleapis.com/v1/projects/demo-project/messages:send"
    assert headers == {"Authorization": "Bearer access-123"}
    message = body["message"]
    assert message["token"] == "tok-a" and "notification" not in message                  # data only: our service worker shows it
    assert message["data"] == {"title": "High alert: Workstation A", "body": n["body"], "event_id": "evt-000001", "url": "/app/alerts/evt-000001"}
    assert message["webpush"]["headers"]["Urgency"] == "high" and calls[1][2]["message"]["token"] == "tok-b"


def test_fcm_sender_counts_only_accepted_phones_and_survives_errors():
    replies = iter([Reply(200), Reply(404), ConnectionError("offline")])

    def post(url, headers, json, timeout):
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return reply

    sender = FcmSender("p", lambda: "a", post=post)
    assert sender.send(["a", "b", "c"], alert_notification(alert(), "W")) == 1


def test_sender_choice_follows_the_environment(tmp_path):
    assert isinstance(build_sender_from_env({}), LogSender)
    assert isinstance(build_sender_from_env({"FCM_PROJECT_ID": "p"}), LogSender)                 # a key is missing
    assert isinstance(build_sender_from_env({"FCM_PROJECT_ID": "p", "FCM_CREDENTIALS_FILE": str(tmp_path / "nope.json")}), LogSender)
    assert isinstance(build_sender_from_env({"FCM_PROJECT_ID": "p", "FCM_CREDENTIALS_JSON": "{ not json"}), LogSender)


def test_a_real_looking_key_builds_an_fcm_sender():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    info = {"type": "service_account", "project_id": "demo", "private_key_id": "x", "private_key": pem, "client_email": "x@demo.iam.gserviceaccount.com",
            "client_id": "1", "token_uri": "https://oauth2.googleapis.com/token"}
    sender = build_sender_from_env({"FCM_PROJECT_ID": "demo", "FCM_CREDENTIALS_JSON": json.dumps(info)})
    assert isinstance(sender, FcmSender) and sender.project_id == "demo"                           # (no network is used here)

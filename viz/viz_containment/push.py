"""Push notifications for high-severity alerts through Firebase Cloud Messaging (web push).

A small watcher thread looks at the shared alerts; each NEW alert with severity HIGH is sent once to every registered phone.
Messages are 'data only' (title, body, event id, link); the service worker in web/public/push/push-sw.js shows them.
If Firebase is not set up, a log-only sender is used and the in-app alert feed still shows every alert (PRD FR-PSH-3).
Secrets (the Firebase service-account key) come from environment variables or a file outside the repo, never from code.
"""
import json
import logging
import threading

log = logging.getLogger("precog.push")

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_URL = "https://fcm.googleapis.com/v1/projects/%s/messages:send"
SEVERITY_WORDS = {"HIGH": "High", "MEDIUM": "Medium", "LOW": "Low"}
PUSH_SEVERITIES = ("HIGH",)  # the documented threshold (TRD 13.7, PRD FR-PSH-2)


def first_sentence(text):
    text = (text or "").strip()
    cut = text.find(". ")
    return text if cut < 0 else text[: cut + 1]


def alert_notification(alert, host_name):
    """The notification for one alert (UI/UX brief 11.2): '{Severity} alert: {host name}' and the first sentence."""
    word = SEVERITY_WORDS.get(alert["severity"], "Alert")
    return {"title": "%s alert: %s" % (word, host_name), "body": first_sentence(alert["explanation"]),
            "event_id": alert["event_id"], "url": "/app/alerts/" + alert["event_id"]}


class LogSender:
    """Used when Firebase is not set up: it only writes a log line."""

    def send(self, tokens, notification):
        log.info("Push (log only, %d phone(s)): %s - %s", len(tokens), notification["title"], notification["body"])
        return 0


class FcmSender:
    """Sends through Firebase's HTTP v1 API. token_provider returns an access token; post is requests.post (both injectable for tests)."""

    def __init__(self, project_id, token_provider, post=None):
        self.project_id = project_id
        self._token_provider = token_provider
        if post is None:
            import requests

            post = requests.post
        self._post = post

    def send(self, tokens, notification):
        """Returns how many phones accepted the message."""
        accepted = 0
        access = self._token_provider()
        data = {k: str(notification[k]) for k in ("title", "body", "event_id", "url")}
        for token in tokens:
            body = {"message": {"token": token, "data": data, "webpush": {"headers": {"Urgency": "high"}}}}
            try:
                reply = self._post(FCM_URL % self.project_id, headers={"Authorization": "Bearer " + access}, json=body, timeout=10)
                if 200 <= reply.status_code < 300:
                    accepted += 1
                else:
                    log.warning("Firebase refused a push (%s): %s", reply.status_code, getattr(reply, "text", "")[:200])
            except Exception:  # a network problem must never stop the watcher
                log.exception("Could not reach Firebase")
        return accepted


def service_account_token_provider(info):
    """info: the parsed service-account JSON. Returns a function that gives a fresh access token."""
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_info(info, scopes=[FCM_SCOPE])

    def provide():
        if not credentials.valid:
            credentials.refresh(Request())
        return credentials.token

    return provide


def build_sender_from_env(env):
    """FcmSender when FCM_PROJECT_ID and a key (FCM_CREDENTIALS_FILE or FCM_CREDENTIALS_JSON) are set, otherwise LogSender."""
    project = (env.get("FCM_PROJECT_ID") or "").strip()
    path = (env.get("FCM_CREDENTIALS_FILE") or "").strip()
    raw = (env.get("FCM_CREDENTIALS_JSON") or "").strip()
    if not project or not (path or raw):
        log.info("Firebase is not configured: push notifications are log-only (the in-app feed still shows every alert)")
        return LogSender()
    try:
        info = json.loads(raw) if raw else json.load(open(path, encoding="utf-8"))
        return FcmSender(project, service_account_token_provider(info))
    except Exception:
        log.exception("Firebase credentials could not be read: push notifications are log-only")
        return LogSender()


class PushHook:
    """The 'push' hook: register(token) is called when a phone registers (the world state keeps the list)."""

    def __init__(self, world):
        self.world = world

    def register(self, token):
        log.info("Phone registered for push (%d registered)", len(self.world.push_tokens()))


class AlertWatcher:
    """Sends a notification once for every new alert at or above the threshold."""

    def __init__(self, world, sender, interval=0.5, severities=PUSH_SEVERITIES):
        self.world, self.sender, self.interval, self.severities = world, sender, interval, severities
        self._seen = {self._key(a) for a in world.alerts(200)}  # alerts that exist at start-up are not announced
        self._stop = threading.Event()
        self._thread = None

    @staticmethod
    def _key(alert):
        return alert["event_id"] + "|" + alert["ts"]

    def poll_once(self):
        """Checks for new alerts and sends them. Returns the notifications that were sent."""
        sent = []
        names = {h["host_id"]: h["name"] for h in self.world.graph()["hosts"]}
        for alert in reversed(self.world.alerts(200)):  # oldest first
            key = self._key(alert)
            if key in self._seen:
                continue
            self._seen.add(key)
            tokens = self.world.push_tokens()
            if alert["severity"] in self.severities and tokens:
                notification = alert_notification(alert, names.get(alert["host"], alert["host"]))
                self.sender.send(tokens, notification)
                sent.append(notification)
        return sent

    def start(self):
        self._thread = threading.Thread(target=self._loop, name="push-watcher", daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop.wait(self.interval):
            try:
                self.poll_once()
            except Exception:
                log.exception("The push watcher hit an error and carries on")

    def stop(self):
        self._stop.set()

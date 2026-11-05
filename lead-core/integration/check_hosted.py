"""Checks that a running copy of the app (localhost or the hosted address) is ready for the demo. Standard library only.

    python lead-core/integration/check_hosted.py https://YOUR-APP.onrender.com YOUR-ADMIN-PASSWORD
It wakes a sleeping free host (the first answer can take a minute), then checks the pieces a phone needs: the health answer, the web app page,
the install files (manifest and service workers), the sign-in, the live state and the scenario list. It starts no replay and changes nothing.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar


class Checker:
    def __init__(self, base, fetch=None):
        self.base = base.rstrip("/")
        self.results = []
        self.fetch = fetch or self._http

    def _http(self, method, path, body=None, timeout=90):
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        if method.upper() in ("POST", "PUT", "PATCH", "DELETE") and path != "/api/x/login":
            headers["X-Precog-Request"] = "1"
            if data is None:
                data = b"{}"
                headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with self._opener.open(request, timeout=timeout) as reply:
                return reply.status, dict(reply.headers), reply.read()
        except urllib.error.HTTPError as error:
            return error.code, dict(error.headers), error.read()

    _opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def check(self, name, ok, detail=""):
        self.results.append((name, bool(ok)))
        print("  %s  %s%s" % ("ok  " if ok else "FAIL", name, ("  (" + detail + ")") if detail else ""))
        return bool(ok)

    def run(self, password):
        started = time.monotonic()
        status, _, body = self.fetch("GET", "/api/x/health")
        woke = round(time.monotonic() - started, 1)
        if not self.check("the backend answers /api/x/health", status == 200, "%s, %s s" % (status, woke)):
            return False
        health = json.loads(body)
        self.check("data mode is live", health.get("data_mode") == "live", str(health.get("data_mode")))
        needed = {"events", "graph", "replay", "containment", "precog", "push", "incidents"}
        self.check("every part is registered", needed <= set(health.get("hooks", [])), "missing: %s" % sorted(needed - set(health.get("hooks", []))))
        bad = {k: v for k, v in health.get("modules", {}).items() if v != "registered"}
        self.check("no part failed to load", not bad, str(bad))
        status, _, page = self.fetch("GET", "/app/")
        self.check("the web app page loads", status == 200 and b"Precog SOC" in page, str(status))
        for path, label in (("/app/manifest.webmanifest", "the install manifest"), ("/app/sw.js", "the service worker"), ("/app/push/push-sw.js", "the push service worker"), ("/app/icons/icon-192.png", "the app icon")):
            status, _, _ = self.fetch("GET", path)
            self.check(label + " is served", status == 200, "%s %s" % (path, status))
        status, _, _ = self.fetch("GET", "/api/x/state")
        self.check("the state needs a sign-in (401 when signed out)", status == 401, str(status))
        status, _, _ = self.fetch("POST", "/api/x/login", {"username": "admin", "password": password})
        if not self.check("sign in works", status == 200, str(status)):
            return False
        status, _, state = self.fetch("GET", "/api/x/state")
        self.check("the live state is served", status == 200 and "graph" in json.loads(state))
        status, _, scenarios = self.fetch("GET", "/api/x/replay/scenarios")
        self.check("the four scenarios are listed", status == 200 and len(json.loads(scenarios)) == 4)
        return all(ok for _, ok in self.results)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print(__doc__)
        return 2
    ok = Checker(argv[0]).run(argv[1])
    print("READY for the demo" if ok else "NOT ready: fix the lines marked FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

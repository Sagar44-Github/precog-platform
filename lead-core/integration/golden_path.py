"""Runs the whole golden path headlessly through the REAL backend and its REAL /api/x routes, and checks every step.

Run from the repo root (backend environment on, .env filled in):
    python lead-core/integration/golden_path.py                 one run
    python lead-core/integration/golden_path.py --runs 5        the five rehearsals in a row (PRD SM-5)
Options: --speed 20 (replay speed; 1 is the real 7-second pace)   --log PATH (default lead-core/integration/rehearsals.csv)
For each run it prints a line per check and the stage timings, appends one line to the rehearsal log, and exits 0 only if every run passed.
Needs DETECT, GRAPH, VIZ and Precog merged. It never starts the live sniffer and attacks nothing: the attack is the scripted replay.
"""
import argparse
import csv
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lead-core" / "backend"))


class Run:
    def __init__(self, client, speed):
        self.client, self.speed = client, speed
        self.checks, self.timings = [], {}

    def check(self, name, ok, detail=""):
        self.checks.append((name, bool(ok), detail))
        print("   %s  %s%s" % ("ok  " if ok else "FAIL", name, ("  (" + detail + ")") if detail else ""))
        return bool(ok)

    def get(self, path):
        return self.client.get(path).get_json()

    def post(self, path, body=None):
        reply = self.client.post(path, json=body or {}, headers={"X-Precog-Request": "1"})
        return reply.status_code, reply.get_json()

    def wait(self, condition, timeout=30.0, step=0.005):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            state = self.get("/api/x/state")
            if condition(state):
                return state
            time.sleep(step)
        return None

    def execute(self, password):
        status, _ = self.post("/api/x/login", {"username": "admin", "password": password})
        if not self.check("sign in", status == 200, "status %s" % status):
            return False
        t0 = time.monotonic()
        status, body = self.post("/api/x/replay/start", {"scenario_id": "golden-path", "speed": self.speed})
        if not self.check("replay starts", status == 200 and body["state"] == "running", str(body)[:80]):
            return False
        state = self.wait(lambda s: s["replay"]["state"] == "waiting_for_decision" and s["forecast"] is not None)
        if not self.check("replay stops at the decision point with a forecast", state is not None):
            return False
        self.timings["to_decision_s"] = round(time.monotonic() - t0, 2)
        forecast = state["forecast"]
        top = forecast["targets"][0]
        self.check("host-a is compromised", [h["state"] for h in state["graph"]["hosts"] if h["host_id"] == "host-a"] == ["compromised"])
        self.check("forecast has up to three ranked targets", 1 <= len(forecast["targets"]) <= 3 and [t["rank"] for t in forecast["targets"]] == list(range(1, len(forecast["targets"]) + 1)))
        self.check("Precog predicts the web server first", top["host_id"] == "server-b", "%s %.0f %%" % (top["host_id"], top["confidence"] * 100))
        self.check("NIDS's real detector raised alerts from the packets", any(a["source"] == "nids_detector" and a["severity"] == "HIGH" for a in state["alerts"]))
        status, action = self.post("/api/x/containment/propose", {"target_host": top["host_id"], "forecast_id": forecast["forecast_id"], "requested_by": "mobile"})
        self.check("Contain asks for confirmation first", status == 200 and action["status"] == "pending_confirmation")
        self.check("nothing changed before confirmation", self.get("/api/x/graph")["hosts"][2]["state"] == "normal")
        t1 = time.monotonic()
        status, action = self.post("/api/x/containment/confirm", {"action_id": action["action_id"]})
        self.check("confirmation executes the containment", status == 200 and action["status"] == "executed")
        final = self.wait(lambda s: s["replay"]["state"] == "finished")
        if not self.check("replay finishes by itself after the decision", final is not None):
            return False
        self.timings["decision_to_finish_s"] = round(time.monotonic() - t1, 2)
        hosts = {h["host_id"]: h["state"] for h in final["graph"]["hosts"]}
        self.check("the web server ended up contained", hosts["server-b"] == "contained")
        self.check("the attack chain ended early (only host-a compromised)", final["graph"]["compromised_path"] == ["host-a"])
        self.check("the move toward Web Server B was blocked", any("was blocked" in a["explanation"] and "Web Server B" in a["explanation"] for a in final["alerts"]))
        resolved = [f for f in self.get("/api/x/forecasts") if f["status"] == "hit"]
        self.check("the forecast was resolved as a blocked hit", len(resolved) == 1 and resolved[0]["outcome"]["blocked"] is True and resolved[0]["outcome"]["rank_hit"] == 1)
        metrics = self.get("/api/x/metrics/precog")
        self.check("the accuracy counter ticked up", metrics["forecasts_resolved"] == 1 and metrics["hits"] == 1 and metrics["hit_rate"] == 1.0)
        self.check("containment success rate is 100 %", metrics["containment_success_rate"] == 1.0)
        again = self.wait(lambda s: any("ended early" in (a["result"] or "") for a in s["actions"]), timeout=5)     # the re-evaluation watcher checks every 0.1 s
        self.check("re-evaluation says the chain ended early", again is not None)
        sessions = self.get("/api/x/sessions")
        self.check("the session was archived", len(sessions) >= 1 and sessions[0]["ended_at"] is not None)
        return all(ok for _, ok, _ in self.checks)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--speed", type=float, default=20.0)
    parser.add_argument("--log", default=str(REPO_ROOT / "lead-core" / "integration" / "rehearsals.csv"))
    args = parser.parse_args(argv)

    # run_app changes the process working directory to the bundled NIDS app.
    # Resolve user-provided relative paths before importing/starting it.
    log = Path(args.log)
    if not log.is_absolute():
        log = REPO_ROOT / log
    log = log.resolve()

    import run_app

    run_app.load_env_file(REPO_ROOT / ".env")
    os.environ["DATA_MODE"] = "live"
    os.environ["PUSH_WATCHER"] = "0"
    password = os.environ.get("ADMIN_PASSWORD", "")
    app = run_app.create_app()
    replay = app.extensions["precog"]["hooks"].get("replay")
    missing = [n for n in ("events", "graph", "replay", "containment", "precog") if not app.extensions["precog"]["hooks"].has(n)]
    if missing:
        print("These parts are not merged yet, so the golden path cannot run: " + ", ".join(missing))
        return 2
    replay.settle_seconds = 0.2
    new = not log.exists()
    streak = 0
    with open(log, "a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        if new:
            writer.writerow(["timestamp_utc", "speed", "result", "failed_checks", "to_decision_s", "decision_to_finish_s"])
        for number in range(1, args.runs + 1):
            print("Run %d of %d (speed %sx)" % (number, args.runs, args.speed))
            run = Run(app.test_client(), args.speed)
            ok = run.execute(password)
            streak = streak + 1 if ok else 0
            failed = "; ".join(n for n, good, _ in run.checks if not good)
            writer.writerow([datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), args.speed, "PASS" if ok else "FAIL", failed,
                             run.timings.get("to_decision_s", ""), run.timings.get("decision_to_finish_s", "")])
            handle.flush()
            print("   -> %s %s" % ("PASS" if ok else "FAIL", run.timings))
            replay.stop()
    print("consecutive successes at the end: %d of %d runs (the plan asks for 5 in a row before demo day)" % (streak, args.runs))
    return 0 if streak == args.runs else 1


if __name__ == "__main__":
    sys.exit(main())

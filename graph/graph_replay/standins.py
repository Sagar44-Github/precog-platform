"""Small stand-ins for other roles' modules. ONLY for GRAPH's tests and the demo script, never registered in the real backend.

StandInEvents behaves like DETECT's 'events' hook (it makes contract-valid security events and shows them in the world state).
StandInPrecog behaves like LEAD-CORE's future 'precog' hook (it only remembers what it was told).
"""
import itertools
import threading
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class StandInEvents:
    def __init__(self, world=None):
        self.world = world
        self._lock = threading.Lock()
        self._counter = itertools.count(1)
        self.packet_batches = []
        self.techniques = []

    def _event(self, host, severity, explanation, technique_id=None, source="scripted", packet_id=None):
        event = {"event_id": "evt-%06d" % next(self._counter), "ts": _now(), "host": host, "packet_id": packet_id, "anomaly": True,
                 "risk_score": 90.0, "severity": severity, "explanation": explanation, "technique_id": technique_id,
                 "technique_name": ("Technique " + technique_id) if technique_id else None, "source": source}
        if self.world is not None:
            self.world.add_alert(event)
        return event

    def process_packets(self, rows):
        with self._lock:
            self.packet_batches.append(list(rows))
            return [self._event(r["src_ip"], r["severity"], "Packet to port %s." % r["dst_port"], None, "nids_detector", r["id"])
                    for r in rows if r.get("severity") in ("HIGH", "MEDIUM", "LOW")]

    def process_technique(self, host, technique_id, note=None, compromise=False, severity="HIGH", risk_score=None):
        with self._lock:
            self.techniques.append({"host": host, "technique_id": technique_id, "note": note, "compromise": compromise})
            return self._event(host, severity, (note or "Technique %s." % technique_id), technique_id)

    def audit_record(self, entry_type, ref_id, summary):
        return None

    def reset(self):
        with self._lock:
            self._counter = itertools.count(1)
            self.packet_batches, self.techniques = [], []


class StandInPrecog:
    def __init__(self):
        self.calls = []

    def reset(self):
        self.calls = []

    def on_compromise(self, host):
        self.calls.append(("compromise", host))

    def on_attempt(self, from_host, to_host, blocked):
        self.calls.append(("attempt", from_host, to_host, blocked))

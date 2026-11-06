"""Turns detections into security events: the readable alerts every other part of the product uses.

Two kinds of input:
  * process_packets(rows)   - packets already labelled by NIDS's detector. Only alerts become events.
  * process_technique(...)  - a scripted attack-technique event (imitating an attack simulation tool).

Each event follows the security_event contract, is shown to the analyst through the world state,
and is written to the audit log.
"""
import itertools
import threading
from datetime import datetime, timezone

from .audit import utc_now
from .explain import explain_dataset_event, explain_packet, explain_technique

ALERT_SEVERITIES = ("HIGH", "MEDIUM", "LOW")
DEFAULT_RISK = {"HIGH": 90.0, "MEDIUM": 65.0, "LOW": 35.0}
PACKET_FIELDS = (
    "id", "timestamp", "src_ip", "dst_ip", "protocol", "src_port", "dst_port", "packet_size", "flags",
    "anomaly", "risk_score", "suspicious_port", "alert", "severity",
)


def packet_to_dict(packet):
    """Copy the fields we need from a NIDS Packet object (or any object with the same attributes)."""
    return {name: getattr(packet, name, None) for name in PACKET_FIELDS}


def to_iso_utc(value):
    """Accept a datetime or text such as '2026-10-03 10:00:01' and return '2026-10-03T10:00:01Z'.
    A time without a zone is treated as UTC. Anything unreadable becomes 'now' so an alert is never lost."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            return utc_now()
    else:
        return utc_now()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clamp_score(value, default):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:  # NaN
        return default
    return round(max(0.0, min(100.0, number)), 2)


class EventProcessor:
    def __init__(self, hosts, techniques, audit=None, world=None, contracts=None):
        self.hosts = hosts
        self.techniques = techniques
        self.audit = audit
        self.world = world
        self.contracts = contracts
        self._lock = threading.Lock()
        self._counter = itertools.count(1)
        self.skipped_unlabelled = 0

    # ---------- helpers ----------
    def _next_id(self):
        with self._lock:
            return "evt-%06d" % next(self._counter)

    def _finish(self, event):
        """Check the contract, show the event to the world state, write the audit line."""
        if self.contracts is not None:
            self.contracts.validate("security_event", event)
        if self.world is not None:
            self.world.add_alert(event)
        if self.audit is not None:
            self.audit.record("detection", event["event_id"], "%s alert on %s: %s" % (
                event["severity"], event["host"], event["explanation"]), ts=event["ts"])
        return event

    # ---------- inputs ----------
    def process_packets(self, rows):
        """rows: dicts (or packet_to_dict results) of packets labelled by NIDS. Returns the new events."""
        events = []
        for row in rows:
            severity = row.get("severity")
            if severity is None:
                self.skipped_unlabelled += 1
                continue
            if severity not in ALERT_SEVERITIES:
                continue  # NORMAL traffic is not an alert
            src_ip, dst_ip = row.get("src_ip"), row.get("dst_ip")
            port = row.get("dst_port")
            technique = self.techniques.technique_for_port(port) if port is not None else None
            event = {
                "event_id": self._next_id(),
                "ts": to_iso_utc(row.get("timestamp")),
                "host": self.hosts.host_or_address(src_ip),
                "packet_id": row.get("id"),
                "anomaly": row.get("anomaly") == -1,
                "risk_score": _clamp_score(row.get("risk_score"), DEFAULT_RISK[severity]),
                "severity": severity,
                "explanation": explain_packet(
                    self.hosts.name_of(src_ip), self.hosts.name_of(dst_ip), row.get("protocol") or "network",
                    port, row.get("packet_size") if row.get("packet_size") is not None else "unknown", severity, technique),
                "technique_id": technique["id"] if technique else None,
                "technique_name": technique["name"] if technique else None,
                "source": "nids_detector",
            }
            events.append(self._finish(event))
        return events

    def process_technique(self, host, technique_id, note=None, compromise=False, severity="HIGH", risk_score=None):
        """A scripted technique event. Unknown hosts or technique ids are errors, so a typo in a scenario file shows up at once."""
        if not self.hosts.is_known(host):
            raise ValueError("Unknown host '%s'. Known hosts: %s" % (host, ", ".join(self.hosts.host_ids())))
        if severity not in ALERT_SEVERITIES:
            raise ValueError("severity must be one of %s" % ", ".join(ALERT_SEVERITIES))
        technique = self.techniques.require(technique_id)
        event = {
            "event_id": self._next_id(),
            "ts": utc_now(),
            "host": host,
            "packet_id": None,
            "anomaly": True,
            "risk_score": _clamp_score(risk_score, DEFAULT_RISK[severity]),
            "severity": severity,
            "explanation": explain_technique(self.hosts.name_of(host), technique, note, compromise),
            "technique_id": technique["id"],
            "technique_name": technique["name"],
            "source": "scripted",
        }
        return self._finish(event)

    def process_dataset_event(self, row, compromise=False):
        """Publish one bounded dataset-pipeline alert using pack host names and provenance.

        This path is separate from NIDS packet processing: large packs never enter NIDS's
        retained packet table or its whole-table detector reads.
        """
        if not isinstance(row, dict):
            raise ValueError("dataset event must be an object")
        host = row.get("host")
        if not self.hosts.is_known(host):
            raise ValueError("Unknown dataset host '%s'" % host)
        severity = row.get("severity", "HIGH")
        if row.get("blocked"):
            severity = "HIGH"
        elif row.get("source") == "graph_novelty" and severity not in ALERT_SEVERITIES:
            severity = "MEDIUM"
        if severity not in ALERT_SEVERITIES:
            return None
        source = row.get("source")
        if source not in ("dataset_labels", "graph_novelty", "recorded_counterfactual"):
            raise ValueError("source must identify a supported dataset pipeline mode")
        technique_id = row.get("technique_id")
        technique = self.techniques.get(technique_id) if technique_id else None
        if technique_id and technique is None:
            raise ValueError("Unknown mapped technique '%s'" % technique_id)
        event = {
            "event_id": self._next_id(),
            "ts": to_iso_utc(row.get("timestamp")),
            "host": host,
            "packet_id": row.get("packet_id") if isinstance(row.get("packet_id"), int) and not isinstance(row.get("packet_id"), bool) else None,
            "anomaly": source != "dataset_labels" or bool(row.get("label")),
            "risk_score": DEFAULT_RISK[severity],
            "severity": severity,
            "explanation": explain_dataset_event(
                self.hosts.name_of(host), row.get("label"), row.get("attack_class"),
                technique=technique, blocked=bool(row.get("blocked")),
                detector_mode="graph-novelty" if source == "graph_novelty" else "labels",
            ),
            "technique_id": technique["id"] if technique else None,
            "technique_name": technique["name"] if technique else None,
            "source": source,
        }
        return self._finish(event)

    # ---------- shared services ----------
    def audit_record(self, entry_type, ref_id, summary):
        """Other roles (forecasts, containment) write their audit lines through this method."""
        if self.audit is None:
            return None
        return self.audit.record(entry_type, ref_id, summary)

    def reset(self, clear_audit=True):
        """Start a fresh replay: event numbers begin again at evt-000001."""
        with self._lock:
            self._counter = itertools.count(1)
            self.skipped_unlabelled = 0
        if clear_audit and self.audit is not None:
            self.audit.clear()

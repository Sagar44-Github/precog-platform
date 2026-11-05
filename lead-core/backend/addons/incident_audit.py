"""Bounded, add-on-owned incident audit ledger with atomic replacement writes."""
import json
import os
from pathlib import Path
import tempfile
import threading


MAX_AUDIT_RECORDS = 5000


class IncidentAuditLog:
    def __init__(self, path, contracts=None, clock=None):
        self.path = Path(path).resolve()
        self.contracts = contracts
        self.clock = clock
        self._lock = threading.RLock()

    def _now(self):
        if self.clock:
            return self.clock()
        from .incident_engine import utc_now

        return utc_now()

    def read_all(self):
        with self._lock:
            if not self.path.is_file():
                return []
            records = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(records, list):
                raise ValueError("The incident audit ledger must contain a JSON array.")
            return records

    def record(self, event_type, incident_id, summary, actor, role, text=None, reason=None):
        if event_type not in ("note", "status_change"):
            raise ValueError("Unsupported incident audit event type.")
        with self._lock:
            records = self.read_all()
            previous = 0
            if records:
                try:
                    previous = int(records[-1]["audit_id"].split("-")[-1])
                except (KeyError, ValueError, AttributeError):
                    raise ValueError("The incident audit ledger contains an invalid sequence id.")
            entry = {
                "audit_id": "IAUD-%06d" % (previous + 1),
                "type": event_type,
                "incident_id": incident_id,
                "timestamp": self._now(),
                "actor": actor,
                "role": role,
                "summary": summary,
                "text": text,
                "reason": reason,
            }
            if self.contracts is not None:
                self.contracts.validate("incident_audit_entry", entry)
            records = (records + [entry])[-MAX_AUDIT_RECORDS:]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary_name = tempfile.mkstemp(prefix=".incident-audit-", suffix=".tmp", dir=str(self.path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                    json.dump(records, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary_name, self.path)
            finally:
                try:
                    if os.path.exists(temporary_name):
                        os.unlink(temporary_name)
                except OSError:
                    pass
            return entry

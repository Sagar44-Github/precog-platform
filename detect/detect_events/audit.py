"""The audit log: one JSON line per detection, forecast and containment.

Nothing secret or personal may be written. scrub() removes anything that looks like a password,
token, key or email address before a line is saved.
"""
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

ENTRY_TYPES = ("detection", "forecast", "containment")

_SECRET_WORDS = re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|authorization)\b(\s*[:=]\s*)\S+")
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_LONG_HEX = re.compile(r"\b[0-9a-fA-F]{32,}\b")
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(-----END [A-Z ]*PRIVATE KEY-----|$)", re.S)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def scrub(text):
    """Return text with secrets and email addresses replaced by [redacted]."""
    text = _PRIVATE_KEY.sub("[redacted]", str(text))
    text = _BEARER.sub("Bearer [redacted]", text)  # first, so "Authorization: Bearer abc" loses the token too
    text = _SECRET_WORDS.sub(lambda m: m.group(1) + m.group(2) + "[redacted]", text)
    text = _LONG_HEX.sub("[redacted]", text)
    return _EMAIL.sub("[redacted]", text)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AuditLog:
    def __init__(self, path, contracts=None):
        self.path = Path(path)
        self._contracts = contracts
        self._lock = threading.Lock()

    def record(self, entry_type, ref_id, summary, ts=None):
        if entry_type not in ENTRY_TYPES:
            raise ValueError("Audit type must be one of %s, not %r" % (", ".join(ENTRY_TYPES), entry_type))
        entry = {"ts": ts or utc_now(), "type": entry_type, "ref_id": str(ref_id), "summary": scrub(summary)}
        if self._contracts is not None:
            self._contracts.validate("audit_entry", entry)
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return entry

    def read_all(self):
        with self._lock:
            if not self.path.is_file():
                return []
            lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def clear(self):
        with self._lock:
            if self.path.is_file():
                self.path.unlink()

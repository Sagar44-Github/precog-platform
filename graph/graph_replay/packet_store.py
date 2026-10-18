"""Where replayed packets are written.

NidsPacketStore writes into NIDS's own packets table (this is how NIDS's detector sees them).
MemoryPacketStore does the same in memory, for tests and the demo script, with a tiny stand-in detector.
"""
import threading
from datetime import datetime, timezone

PACKET_FIELDS = ("id", "timestamp", "src_ip", "dst_ip", "protocol", "src_port", "dst_port", "packet_size", "flags",
                 "anomaly", "risk_score", "suspicious_port", "alert", "severity")
SUSPICIOUS_PORTS = {22, 23, 3389, 445, 135, 137, 138, 139, 4444, 6666, 31337}  # the ports NIDS treats as suspicious


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)  # NIDS stores plain UTC date-times


class NidsPacketStore:
    """nids: an object with SessionLocal and Packet (the add-on loader's ctx.nids)."""

    def __init__(self, nids):
        self._session_factory = nids.SessionLocal
        self._packet_class = nids.Packet

    def insert(self, rows):
        """rows: dicts with src_ip, dst_ip, protocol, src_port, dst_port, packet_size, flags. Packets are written UNLABELLED
        (NIDS's detector fills in severity and score). Returns the new row ids in order."""
        session = self._session_factory()
        try:
            objects = [self._packet_class(timestamp=_now(), src_ip=r["src_ip"], dst_ip=r["dst_ip"], protocol=r["protocol"],
                                          src_port=r["src_port"], dst_port=r["dst_port"], packet_size=r["packet_size"],
                                          flags=r.get("flags")) for r in rows]
            session.add_all(objects)
            session.commit()
            return [o.id for o in objects]
        finally:
            session.close()

    def fetch(self, ids):
        session = self._session_factory()
        try:
            found = session.query(self._packet_class).filter(self._packet_class.id.in_(list(ids))).order_by(self._packet_class.id).all()
            return [{name: getattr(p, name, None) for name in PACKET_FIELDS} for p in found]
        finally:
            session.close()

    def clear(self):
        session = self._session_factory()
        try:
            session.query(self._packet_class).delete()
            session.commit()
        finally:
            session.close()


class MemoryPacketStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._rows = []
        self._next_id = 1

    def insert(self, rows):
        with self._lock:
            ids = []
            for r in rows:
                row = {name: None for name in PACKET_FIELDS}
                row.update(id=self._next_id, timestamp=_now().strftime("%Y-%m-%d %H:%M:%S"), src_ip=r["src_ip"], dst_ip=r["dst_ip"],
                           protocol=r["protocol"], src_port=r["src_port"], dst_port=r["dst_port"], packet_size=r["packet_size"],
                           flags=r.get("flags"))
                self._rows.append(row)
                ids.append(self._next_id)
                self._next_id += 1
            return ids

    def fetch(self, ids):
        wanted = set(ids)
        with self._lock:
            return [dict(r) for r in self._rows if r["id"] in wanted]

    def clear(self):
        with self._lock:
            self._rows = []
            self._next_id = 1

    def all(self):
        with self._lock:
            return [dict(r) for r in self._rows]


def simple_detector(store):
    """A stand-in for NIDS's detector, only for tests and the demo: labels unlabelled rows HIGH on the suspicious ports."""

    def run():
        with store._lock:
            for row in store._rows:
                if row["severity"] is None:
                    hot = row["dst_port"] in SUSPICIOUS_PORTS
                    row.update(severity="HIGH" if hot else "NORMAL", alert=hot, suspicious_port=hot, anomaly=1, risk_score=80.0 if hot else 10.0)

    return run

"""Small helpers shared by DETECT's tests (a unique file name, so it never clashes with other roles' tests)."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def packet(**changes):
    """A NIDS-labelled packet row. Override any field."""
    row = {"id": 1, "timestamp": "2026-10-03 10:00:01", "src_ip": "192.168.1.11", "dst_ip": "192.168.1.12",
           "protocol": "TCP", "src_port": 40000, "dst_port": 22, "packet_size": 2500, "flags": "S",
           "anomaly": 1, "risk_score": 49.93, "suspicious_port": True, "alert": True, "severity": "HIGH"}
    row.update(changes)
    return row

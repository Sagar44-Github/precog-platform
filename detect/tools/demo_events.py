"""See DETECT's work with your own eyes. No server needed.

Run from the repo root:   python detect/tools/demo_events.py
It feeds a few made-up NIDS-labelled packets and one scripted technique through the event processor
and prints the readable alerts and the audit log.
"""
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "lead-core" / "backend"))
sys.path.insert(0, str(REPO_ROOT / "detect"))

from addons.contracts import Contracts  # noqa: E402
from addons.world_state import WorldState  # noqa: E402
from detect_events import AuditLog, EventProcessor, HostMap, TechniqueTable  # noqa: E402
from detect_events import TECHNIQUES_FILE  # noqa: E402,F401 (imported to show where the table lives)

PACKETS = [
    {"id": 1, "timestamp": "2026-10-03 10:00:01", "src_ip": "192.168.1.11", "dst_ip": "192.168.1.12", "protocol": "TCP",
     "src_port": 51000, "dst_port": 443, "packet_size": 300, "anomaly": 1, "risk_score": 47.5, "severity": "NORMAL"},
    {"id": 2, "timestamp": "2026-10-03 10:00:02", "src_ip": "192.168.1.11", "dst_ip": "192.168.1.12", "protocol": "TCP",
     "src_port": 40000, "dst_port": 22, "packet_size": 2500, "anomaly": 1, "risk_score": 49.9, "severity": "HIGH"},
    {"id": 3, "timestamp": "2026-10-03 10:00:03", "src_ip": "192.168.1.11", "dst_ip": "192.168.1.20", "protocol": "TCP",
     "src_port": 40001, "dst_port": 31337, "packet_size": 4500, "anomaly": -1, "risk_score": 59.6, "severity": "HIGH"},
]


def main():
    contracts = Contracts(REPO_ROOT / "contracts")
    world = WorldState(contracts)
    audit_path = Path(tempfile.mkdtemp(prefix="detect-demo-")) / "audit.jsonl"
    processor = EventProcessor(
        HostMap.from_file(REPO_ROOT / "contracts" / "data" / "hosts.json"),
        TechniqueTable.from_file(TECHNIQUES_FILE),
        audit=AuditLog(audit_path, contracts), world=world, contracts=contracts)

    print("--- 3 packets in, only alerts come out ---")
    for event in processor.process_packets(PACKETS):
        print("%s  %-6s  %s" % (event["event_id"], event["severity"], event["explanation"]))
    print("\n--- one scripted technique ---")
    event = processor.process_technique("host-a", "T1110", note="Repeated failed logins", compromise=True)
    print("%s  %-6s  %s" % (event["event_id"], event["severity"], event["explanation"]))
    print("\n--- the world state now holds %d alerts (version %d) ---" % (len(world.alerts()), world.version))
    print("\n--- audit log (%s) ---" % audit_path)
    for line in processor.audit.read_all():
        print(line["ts"], line["type"], line["ref_id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

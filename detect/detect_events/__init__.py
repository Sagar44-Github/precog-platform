"""DETECT's package: security event processing, ATT&CK technique lookup and audit logging.

The backend calls register(ctx) once at start-up. This module hands over one object, the
EventProcessor, through the 'events' hook:

    ctx.hooks.get("events").process_packets(rows)                       -> list of security_event dicts
    ctx.hooks.get("events").process_technique(host, technique_id, ...)  -> one security_event dict
    ctx.hooks.get("events").audit_record(type, ref_id, summary)         -> audit line (other roles use this)
    ctx.hooks.get("events").reset()                                     -> new replay, numbering restarts
"""
import logging
from pathlib import Path

from .audit import AuditLog
from .events import EventProcessor, packet_to_dict
from .hosts import HostMap
from .reports import load_detection_report
from .techniques import TechniqueTable

log = logging.getLogger("precog.detect")

PACKAGE_DIR = Path(__file__).resolve().parent
TECHNIQUES_FILE = PACKAGE_DIR / "data" / "attack_techniques.json"

__all__ = ["register", "EventProcessor", "HostMap", "TechniqueTable", "AuditLog", "packet_to_dict"]


def register(ctx):
    config = ctx.config
    hosts = HostMap.from_file(config.contracts_dir / "data" / "hosts.json")
    techniques = TechniqueTable.from_file(TECHNIQUES_FILE)
    audit = AuditLog(config.repo_root / "lead-core" / "backend" / "data" / "audit" / "audit.jsonl", ctx.contracts)
    processor = EventProcessor(hosts, techniques, audit=audit, world=ctx.world, contracts=ctx.contracts)
    ctx.hooks.register("events", processor)

    # In live mode the real offline evaluation replaces the fake sample report.
    if config.data_mode == "live":
        report_path = config.repo_root / "detect" / "offline_model" / "results" / "detection_report.json"
        try:
            report = load_detection_report(report_path, ctx.contracts)
        except Exception as exc:  # a bad report must never stop the server
            log.warning("Detection report not loaded: %s", exc)
            report = None
        if report is not None:
            ctx.world.set_detection_report(report)
            log.info("Detection report loaded from %s", report_path)
        else:
            log.info("No detection report found yet (%s)", report_path)

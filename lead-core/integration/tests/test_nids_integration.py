"""Checks about NIDS itself: it still works untouched, and our code can drive it.

These tests document what we verified about NIDS before building on it.
"""
import datetime
import os
from pathlib import Path

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]  # set by conftest.py

NIDS_DIR = Path(__file__).resolve().parents[2] / "backend" / "nids"


def test_our_admin_password_works_on_nids_own_login_and_the_default_does_not(flask_app):
    with flask_app.test_client() as c:
        assert c.post("/login", data={"username": "admin", "password": "password123"}).status_code == 200  # page re-shown
        assert c.get("/api/stats").status_code == 302  # still not logged in: redirected to the login page
    with flask_app.test_client() as c:
        reply = c.post("/login", data={"username": "admin", "password": ADMIN_PASSWORD})
        assert reply.status_code == 302 and reply.headers["Location"].endswith("/")
        assert c.get("/api/stats").status_code == 200


def test_nids_endpoints_work_on_sqlite(flask_app):
    with flask_app.test_client() as c:
        c.post("/login", data={"username": "admin", "password": ADMIN_PASSWORD})
        for path in ("/api/stats", "/api/alerts", "/api/packets", "/api/protocol_counts", "/api/throughput"):
            assert c.get(path).status_code == 200, path


def test_our_code_can_write_packets_and_call_the_detector_directly(ctx):
    from database.models import Packet, SessionLocal
    from ml.anomaly_detector import run_detection

    nids = ctx["nids"]
    session = nids.SessionLocal()
    now = datetime.datetime.utcnow()
    session.add(Packet(timestamp=now, src_ip="192.168.1.11", dst_ip="192.168.1.12", protocol="TCP", src_port=51000, dst_port=443, packet_size=300, flags="S"))
    session.add(Packet(timestamp=now, src_ip="192.168.1.11", dst_ip="192.168.1.20", protocol="TCP", src_port=40000, dst_port=3389, packet_size=900, flags="S"))
    session.commit()
    ids = [p.id for p in session.query(Packet).order_by(Packet.id.desc()).limit(2).all()]
    session.close()

    run_detection()  # NIDS's own function, called in the same process, right now

    session = SessionLocal()
    rows = {p.id: p for p in session.query(Packet).filter(Packet.id.in_(ids)).all()}
    session.close()
    labelled = sorted(rows.values(), key=lambda p: p.id)
    assert all(p.severity is not None for p in labelled)
    assert labelled[0].severity == "NORMAL"      # ordinary web traffic
    assert labelled[1].severity == "HIGH"        # port 3389 is on NIDS's suspicious-port list
    assert labelled[1].alert is True


def test_pcap_upload_returns_results_but_does_not_store_packets(flask_app, ctx):
    """NIDS's PCAP upload only ANALYSES the file. It never writes the packets to the database."""
    from database.models import Packet, SessionLocal

    session = SessionLocal()
    before = session.query(Packet).count()
    session.close()
    with flask_app.test_client() as c:
        c.post("/login", data={"username": "admin", "password": ADMIN_PASSWORD})
        with open(NIDS_DIR / "test_traffic.pcap", "rb") as f:
            reply = c.post("/api/upload_pcap", data={"file": (f, "test_traffic.pcap")}, content_type="multipart/form-data")
    assert reply.status_code == 200
    body = reply.get_json()
    assert body["stats"]["total"] == 95 and body["stats"]["high"] > 0
    session = SessionLocal()
    after = session.query(Packet).count()
    session.close()
    assert after == before


def test_nids_files_are_untouched_by_us():
    """We import NIDS; we never edit it. This guards the 'unchanged copy' rule."""
    app_text = (NIDS_DIR / "dashboard" / "app.py").read_text(encoding="utf-8")
    assert 'app.secret_key = "super_secret_cyber_key"' in app_text  # still the original line; we override it from outside


def test_a_background_thread_can_write_and_detect_while_requests_are_read(flask_app, ctx):
    """The replay controller will run in a background thread while clients poll.
    SQLite must cope with that without 'database is locked' errors."""
    import threading

    from database.models import Packet
    from ml.anomaly_detector import run_detection

    nids = ctx["nids"]
    problems = []

    def writer():
        try:
            for i in range(15):
                session = nids.SessionLocal()
                session.add(Packet(timestamp=datetime.datetime.utcnow(), src_ip="192.168.1.11", dst_ip="192.168.1.20", protocol="TCP",
                                   src_port=40000 + i, dst_port=22 if i % 2 else 443, packet_size=500, flags="S"))
                session.commit()
                session.close()
                run_detection()
        except Exception as exc:  # pragma: no cover - only runs when something is wrong
            problems.append(repr(exc))

    thread = threading.Thread(target=writer)
    thread.start()
    with flask_app.test_client() as c:
        c.post("/login", data={"username": "admin", "password": ADMIN_PASSWORD})
        while thread.is_alive():
            reply = c.get("/api/stats")
            if reply.status_code != 200:
                problems.append("stats answered %s" % reply.status_code)
                break
    thread.join()
    assert problems == []

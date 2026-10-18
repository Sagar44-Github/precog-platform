import json
import threading

import pytest

from addons.contracts import ContractError
from detect_events.audit import AuditLog, scrub


def test_record_writes_one_json_line_and_read_all_returns_it(audit):
    audit.record("detection", "evt-000001", "something happened", ts="2026-10-03T10:00:00Z")
    lines = audit.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["ref_id"] == "evt-000001"
    assert audit.read_all() == [{"ts": "2026-10-03T10:00:00Z", "type": "detection", "ref_id": "evt-000001", "summary": "something happened"}]


def test_reading_a_missing_log_gives_an_empty_list(tmp_path):
    assert AuditLog(tmp_path / "nothing.jsonl").read_all() == []


def test_unknown_entry_type_is_refused(audit):
    with pytest.raises(ValueError):
        audit.record("gossip", "x", "y")


def test_entries_are_checked_against_the_contract(tmp_path, contracts):
    log = AuditLog(tmp_path / "a.jsonl", contracts)
    with pytest.raises(ContractError):
        log.record("detection", "evt-1", "")  # an empty summary breaks the audit_entry contract
    assert log.read_all() == []


def test_clear_removes_the_file(audit):
    audit.record("forecast", "fc-1", "x")
    audit.clear()
    assert audit.read_all() == []
    audit.clear()  # clearing twice is fine


def test_many_threads_writing_do_not_corrupt_lines(audit):
    def work(n):
        for i in range(25):
            audit.record("containment", "act-%d-%d" % (n, i), "line")

    threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(audit.read_all()) == 200


@pytest.mark.parametrize("text", [
    "login with password=hunter2 failed",
    "Authorization: Bearer abcDEF123._-token",
    "api_key: sk_live_123456",
    "token=abc123",
    "key is 0123456789abcdef0123456789abcdef0123",
    "mail me at student@example.com",
    "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAKj34GkxFhD90vcNLYLInFEX6Ppy1tPf9Cnzj4p4WGeKLs1Pt8Qu\n-----END RSA PRIVATE KEY-----",
])
def test_secrets_and_emails_are_scrubbed(text):
    cleaned = scrub(text)
    assert "[redacted]" in cleaned
    for secret in ("hunter2", "abcDEF123", "sk_live_123456", "abc123", "0123456789abcdef", "student@example.com", "MIIBOgIBAAJBAKj34"):
        assert secret not in cleaned


def test_ordinary_text_is_not_changed():
    text = "HIGH alert on host-a: Workstation A sent a 2500-byte TCP packet to port 22."
    assert scrub(text) == text


def test_audit_log_scrubs_before_writing(audit):
    audit.record("detection", "evt-1", "found password=letmein in a packet")
    assert "letmein" not in audit.path.read_text(encoding="utf-8")

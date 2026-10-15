"""The world state: versions, polling answers, forecasts and thread safety."""
import copy
import json
import threading
from pathlib import Path

import pytest

from addons.contracts import Contracts, ContractError
from addons.world_state import MAX_ALERTS, WorldState

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"


def sample(name):
    return json.loads((CONTRACTS_DIR / "samples" / (name + ".sample.json")).read_text(encoding="utf-8"))


@pytest.fixture()
def w():
    return WorldState(Contracts(CONTRACTS_DIR))


def test_every_write_adds_one_to_the_version(w):
    assert w.version == 0
    w.add_alert(sample("security_event"))
    assert w.version == 1
    w.set_graph(sample("graph_snapshot"))
    assert w.version == 2


def test_poll_with_current_version_says_nothing_changed(w):
    w.add_alert(sample("security_event"))
    assert w.snapshot(since=w.version) == {"version": 1, "changed": False}


def test_poll_with_old_version_returns_everything(w):
    w.add_alert(sample("security_event"))
    snap = w.snapshot(since=0)
    assert snap["changed"] is True and snap["version"] == 1
    assert {"graph", "alerts", "forecast", "actions", "replay", "metrics"} <= set(snap)
    assert Contracts(CONTRACTS_DIR).errors("world_state", snap) == []


def test_first_poll_without_since_returns_everything(w):
    assert w.snapshot()["changed"] is True


def test_newest_alert_comes_first(w):
    first, second = sample("security_event"), sample("security_event")
    second["event_id"] = "evt-000002"
    w.add_alert(first)
    w.add_alert(second)
    assert [a["event_id"] for a in w.alerts()] == ["evt-000002", "evt-000001"]


def test_alert_list_is_capped(w):
    event = sample("security_event")
    for i in range(MAX_ALERTS + 25):
        event = dict(event, event_id="evt-%06d" % i)
        w.add_alert(event)
    assert len(w.alerts(limit=10_000)) == MAX_ALERTS


def test_a_new_forecast_supersedes_the_pending_one(w):
    first = sample("forecast")
    second = dict(copy.deepcopy(first), forecast_id="fc-000002")
    w.set_forecast(first)
    w.set_forecast(second)
    assert w.current_forecast()["forecast_id"] == "fc-000002"
    assert [f["status"] for f in w.forecasts()] == ["superseded", "pending"]


def test_resolving_a_forecast_records_the_outcome(w):
    w.set_forecast(sample("forecast"))
    w.resolve_forecast("fc-000001", "hit", {"attempted_host": "server-b", "rank_hit": 1, "blocked": True})
    assert w.current_forecast() is None
    resolved = w.forecasts(status="hit")[0]
    assert resolved["outcome"]["blocked"] is True


def test_resolving_an_unknown_forecast_is_an_error(w):
    with pytest.raises(KeyError):
        w.resolve_forecast("fc-999999", "hit", {"attempted_host": "x", "rank_hit": 1, "blocked": False})


def test_resolve_needs_hit_or_miss(w):
    w.set_forecast(sample("forecast"))
    with pytest.raises(ValueError):
        w.resolve_forecast("fc-000001", "maybe", None)


def test_action_with_same_id_is_replaced_not_duplicated(w):
    action = sample("containment_action")
    w.upsert_action(action)
    w.upsert_action(dict(action, status="executed", confirmed_at="2026-10-03T10:00:09Z", result="Contained"))
    assert len(w.actions()) == 1 and w.actions()[0]["status"] == "executed"


def test_bad_data_is_refused_and_does_not_change_the_version(w):
    bad = sample("security_event")
    bad["severity"] = "SEVERE"
    with pytest.raises(ContractError):
        w.add_alert(bad)
    assert w.version == 0 and w.alerts() == []


def test_reads_return_copies_not_the_inside_objects(w):
    w.add_alert(sample("security_event"))
    w.alerts()[0]["host"] = "tampered"
    assert w.alerts()[0]["host"] == "host-a"


def test_reset_forgets_the_replay_but_keeps_history_and_bumps_version(w):
    w.load_full_state(sample("world_state"))
    w.set_session(sample("session_record"))
    w.archive_session()
    before = w.version
    w.reset()
    assert w.version == before + 1
    assert w.alerts() == [] and w.current_forecast() is None and len(w.sessions()) == 1


def test_push_tokens_are_not_duplicated(w):
    assert w.add_push_token("abc") == 1
    assert w.add_push_token("abc") == 1
    assert w.add_push_token("def") == 2


def test_many_threads_writing_at_once_do_not_lose_updates():
    w = WorldState(None)
    event = sample("security_event")

    def work(n):
        for i in range(50):
            w.add_alert(dict(event, event_id="evt-%d-%d" % (n, i)))

    threads = [threading.Thread(target=work, args=(n,)) for n in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert w.version == 500
    assert len(w.alerts(limit=10_000)) == MAX_ALERTS

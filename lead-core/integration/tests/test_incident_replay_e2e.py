"""Acceptance runs for C1 incidents through the real replay and HTTP routes."""
import time

import pytest


def poll(client, test, timeout=12):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = client.get('/api/x/state').get_json()
        if test(last):
            return last
        time.sleep(0.01)
    raise AssertionError('Replay did not reach the expected state: %r' % (last or {}))


@pytest.fixture()
def replay_stack(flask_app, ctx, monkeypatch):
    monkeypatch.setenv('PUSH_WATCHER', '0')
    hooks = ctx['hooks']
    required = {'events', 'graph', 'replay', 'precog', 'containment', 'incidents'}
    if not required.issubset(set(hooks.registered())):
        from addons.loader import AddonContext, ROLE_PACKAGES, _load_role_packages

        hooks._items.clear()
        context = AddonContext(ctx['world'], hooks, ctx['config'], ctx['contracts'], ctx['nids'], flask_app)
        _load_role_packages(context, ROLE_PACKAGES)
    replay = hooks.require('replay')
    replay.settle_seconds = 0
    replay.decision_timeout = 4
    yield hooks
    replay.stop()
    hooks.get('containment').shutdown()


def start(client, scenario):
    response = client.post('/api/x/replay/start', json={'scenario_id': scenario, 'speed': 40})
    assert response.status_code == 200, response.get_data(as_text=True)


def incidents(client):
    result = client.get('/api/x/incidents?limit=100')
    assert result.status_code == 200, result.get_data(as_text=True)
    return result.get_json()['items']


def normalized(item, timeline):
    return {
        'incident_id': item['incident_id'],
        'title': item['title'],
        'status': item['status'],
        'severity': item['severity'],
        'alert_ids': item['alert_ids'],
        'affected_hosts': item['affected_hosts'],
        'compromised_hosts': item['compromised_hosts'],
        'attack_path': item['attack_path'],
        'techniques': item['techniques'],
        'forecast_ids': item['forecast_ids'],
        'action_ids': item['action_ids'],
        'timeline': [
            (event['event_id'], event['type'], event['summary'], event['host_ids'])
            for event in timeline
        ],
    }


def test_golden_path_lateral_spread_quiet_scan_and_repeat_determinism(logged_in, replay_stack):
    # Golden Path keeps the existing one-host containment demo and marks the incident contained
    # after the forecasted move is blocked, while listing the compromised source host honestly.
    start(logged_in, 'golden-path')
    waiting = poll(logged_in, lambda state: state['replay']['state'] == 'waiting_for_decision')
    forecast = waiting['forecast']
    proposal = logged_in.post('/api/x/containment/propose', json={
        'target_host': 'server-b', 'forecast_id': forecast['forecast_id'], 'requested_by': 'console',
    }).get_json()
    confirmed = logged_in.post('/api/x/containment/confirm', json={'action_id': proposal['action_id']})
    assert confirmed.status_code == 200 and confirmed.get_json()['status'] == 'executed'
    final = poll(logged_in, lambda state: state['replay']['state'] == 'finished')
    cases = incidents(logged_in)
    assert len(cases) == 1
    golden = cases[0]
    assert golden['status'] == 'contained', {key: golden.get(key) for key in ('status', 'forecast_outcome', 'forecasts', 'actions', 'compromised_hosts', 'affected_hosts')}
    assert golden['compromised_hosts'] == ['host-a']
    assert golden['forecast_outcome']['label'] == 'blocked hit'
    assert len([action for action in golden['actions'] if action['status'] == 'executed']) == 1
    assert final['graph']['compromised_path'] == ['host-a']

    # Lateral spread groups the related alerts into one evolving investigation.
    start(logged_in, 'lateral-spread')
    poll(logged_in, lambda state: state['replay']['state'] == 'waiting_for_decision')
    assert logged_in.post('/api/x/replay/resume').status_code == 200
    poll(logged_in, lambda state: state['replay']['state'] == 'finished')
    spread = incidents(logged_in)
    assert len(spread) == 1 and len(spread[0]['alert_ids']) >= 3
    assert {'host-a', 'file-server'} <= set(spread[0]['affected_hosts'])

    # Quiet Scan stays low severity and open because it never compromises a host or invokes response.
    start(logged_in, 'quiet-scan')
    poll(logged_in, lambda state: state['replay']['state'] == 'finished')
    first = incidents(logged_in)
    assert len(first) == 1 and first[0]['severity'] == 'LOW'
    assert first[0]['status'] == 'open' and first[0]['compromised_hosts'] == []
    first_timeline = logged_in.get('/api/x/incidents/%s/timeline' % first[0]['incident_id']).get_json()
    first_normalized = normalized(first[0], first_timeline)

    start(logged_in, 'quiet-scan')
    poll(logged_in, lambda state: state['replay']['state'] == 'finished')
    second = incidents(logged_in)
    second_timeline = logged_in.get('/api/x/incidents/%s/timeline' % second[0]['incident_id']).get_json()
    assert len(second) == 1
    assert first_normalized == normalized(second[0], second_timeline)

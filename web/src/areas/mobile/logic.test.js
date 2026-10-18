import test from 'node:test'
import assert from 'node:assert/strict'
import {
  CONFIRM_SECONDS, accuracyText, attackPath, containReducer, filterAlerts, forecastRows, formatTime, highAlertCount, hostName, initialContain,
  mitreUrl, outcomeText, percent, severityMeta, sliderComplete, threatLevel,
} from './logic.js'

const hosts = (states) => ['host-a', 'host-b', 'server-b'].map((id, i) => ({ host_id: id, name: ['Workstation A', 'Workstation B', 'Web Server B'][i], zone: 'user', state: states[i] || 'normal' }))
const world = (over = {}) => ({ graph: { hosts: hosts(over.states || []), edges: [], compromised_path: over.path || [] }, alerts: over.alerts || [], forecast: over.forecast || null, metrics: over.metrics || null })
const forecast = { forecast_id: 'fc-1', status: 'pending', targets: [{ rank: 1, host_id: 'server-b', confidence: 0.74 }, { rank: 2, host_id: 'host-b', confidence: 0.15 }], technique_hint: null, outcome: null }

test('threat level: calm, watching, under attack, contained', () => {
  assert.equal(threatLevel(world()).word, 'Calm')
  assert.equal(threatLevel(world({ alerts: [{}] })).word, 'Watching')
  assert.equal(threatLevel(world({ states: ['compromised'], alerts: [{}] })).word, 'Under attack')
  assert.equal(threatLevel(world({ states: ['normal', 'normal', 'contained'] })).word, 'Contained')
})

test('under attack outranks contained when both are present', () => {
  assert.equal(threatLevel(world({ states: ['compromised', 'normal', 'contained'] })).key, 'attack')
})

test('threat caption lists compromised hosts and the pending forecast', () => {
  const level = threatLevel(world({ states: ['compromised', 'compromised'], forecast }))
  assert.equal(level.caption, '2 hosts compromised, 1 forecast pending')
  assert.equal(threatLevel(world({ states: ['compromised'] })).caption, '1 host compromised')
  assert.equal(threatLevel(world()).caption, 'No alerts yet')
})

test('threat level is null before the first reply', () => {
  assert.equal(threatLevel(null), null)
})

test('host names come from the graph and unknown ids are kept', () => {
  assert.equal(hostName(world(), 'server-b'), 'Web Server B')
  assert.equal(hostName(world(), 'ghost'), 'ghost')
  assert.equal(hostName(null, 'x'), 'x')
})

test('forecast rows have names and whole percentages', () => {
  assert.deepEqual(forecastRows(world({ forecast })), [
    { rank: 1, hostId: 'server-b', name: 'Web Server B', percent: 74 },
    { rank: 2, hostId: 'host-b', name: 'Workstation B', percent: 15 }])
  assert.deepEqual(forecastRows(world()), [])
  assert.equal(percent(0.075), 8)
})

test('severity words and icons', () => {
  assert.equal(severityMeta('HIGH').word, 'High')
  assert.equal(severityMeta('MEDIUM').icon, '◆')
  assert.equal(severityMeta('WEIRD').word, 'Unrated')
})

test('times are shown as HH:MM:SS and NIDS times count as UTC', () => {
  assert.equal(formatTime('2026-10-03T10:00:01Z', 'UTC'), '10:00:01')
  assert.equal(formatTime('2026-10-03 10:00:01', 'UTC'), '10:00:01')
  assert.equal(formatTime('', 'UTC'), '')
  assert.equal(formatTime('nonsense', 'UTC'), 'nonsense')
})

test('technique links use a slash for sub-techniques', () => {
  assert.equal(mitreUrl('T1110'), 'https://attack.mitre.org/techniques/T1110/')
  assert.equal(mitreUrl('T1021.004'), 'https://attack.mitre.org/techniques/T1021/004/')
  assert.equal(mitreUrl(null), null)
})

test('alert filter and the high-alert count', () => {
  const alerts = [{ severity: 'HIGH' }, { severity: 'LOW' }, { severity: 'HIGH' }]
  assert.equal(filterAlerts(alerts, 'ALL').length, 3)
  assert.equal(filterAlerts(alerts, 'HIGH').length, 2)
  assert.equal(highAlertCount(alerts), 2)
})

test('attack path ends with the top predicted host', () => {
  const path = attackPath(world({ path: ['host-a'], forecast }))
  assert.deepEqual(path.steps, [{ hostId: 'host-a', name: 'Workstation A' }])
  assert.deepEqual(path.next, { hostId: 'server-b', name: 'Web Server B', percent: 74 })
  assert.equal(attackPath(world()).next, null)
})

test('outcome wording: blocked hit, hit, miss, and nothing while pending', () => {
  const w = world()
  const hit = { status: 'hit', outcome: { attempted_host: 'server-b', rank_hit: 1, blocked: true } }
  assert.deepEqual(outcomeText(hit, w), { tone: 'contained', text: 'Precog was right. The move toward Web Server B was blocked.' })
  assert.equal(outcomeText({ ...hit, outcome: { ...hit.outcome, blocked: false } }, w).tone, 'happened')
  const miss = { status: 'miss', outcome: { attempted_host: 'host-b', rank_hit: null, blocked: false } }
  assert.deepEqual(outcomeText(miss, w), { tone: 'muted', text: 'Precog missed. The attacker went to Workstation B instead.' })
  assert.equal(outcomeText(forecast, w), null)
})

test('accuracy text', () => {
  assert.equal(accuracyText(null), 'No forecasts resolved yet')
  assert.equal(accuracyText({ forecasts_resolved: 0 }), 'No forecasts resolved yet')
  assert.equal(accuracyText({ forecasts_resolved: 4, hits: 3, hit_rate: 0.75 }), '3 / 4 (75 %)')
})

test('the containment flow walks through its steps', () => {
  let s = containReducer(initialContain, { type: 'tap' })
  assert.equal(s.step, 'proposing')
  s = containReducer(s, { type: 'proposed', action: { action_id: 'act-1' } })
  assert.equal(s.step, 'confirming')
  s = containReducer(s, { type: 'confirm' })
  assert.equal(s.step, 'sending')
  s = containReducer(s, { type: 'confirmed', action: { action_id: 'act-1', status: 'executed' } })
  assert.equal(s.step, 'done')
})

test('cancel returns to idle; stray events are ignored', () => {
  let s = containReducer(containReducer(initialContain, { type: 'tap' }), { type: 'proposed', action: { action_id: 'a' } })
  assert.equal(containReducer(s, { type: 'cancel' }).step, 'idle')
  assert.equal(containReducer(initialContain, { type: 'confirm' }).step, 'idle')
  assert.equal(containReducer(initialContain, { type: 'proposed', action: {} }).step, 'idle')
  assert.equal(containReducer(initialContain, { type: 'nonsense' }), initialContain)
})

test('the sheet expires after 60 ticks with the expired message', () => {
  let s = containReducer(containReducer(initialContain, { type: 'tap' }), { type: 'proposed', action: { action_id: 'a' } })
  for (let i = 0; i < CONFIRM_SECONDS - 1; i += 1) s = containReducer(s, { type: 'tick' })
  assert.equal(s.step, 'confirming')
  assert.equal(s.secondsLeft, 1)
  s = containReducer(s, { type: 'tick' })
  assert.equal(s.step, 'expired')
  assert.equal(s.message, 'This request expired. Try again.')
})

test('errors can happen at any step and a new tap starts again', () => {
  let s = containReducer(initialContain, { type: 'error', message: 'Not built' })
  assert.equal(s.step, 'error')
  assert.equal(s.message, 'Not built')
  assert.equal(containReducer(s, { type: 'tap' }).step, 'proposing')
})

test('the slider confirms only past 80 percent', () => {
  assert.equal(sliderComplete(0.79), false)
  assert.equal(sliderComplete(0.8), true)
})

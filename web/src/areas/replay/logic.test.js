import test from 'node:test'
import assert from 'node:assert/strict'
import { blankScenario, eventHosts, eventLabel, normalizeForComparison, resequence, safeScenarioFilename, timelineLanes } from './logic.js'

test('blank scenario provides a valid first technique event', () => {
  const draft = blankScenario()
  assert.equal(draft.scenario_id, 'user-new-scenario')
  assert.equal(draft.events[0].seq, 1)
  assert.equal(draft.events[0].kind, 'technique')
})

test('resequence preserves event content and establishes ordered sequence numbers', () => {
  const rows = resequence([{ offset_ms: 0 }, { offset_ms: 1 }])
  assert.deepEqual(rows.map((row) => row.seq), [1, 2])
})

test('event hosts and labels cover each scripted event kind', () => {
  assert.deepEqual(eventHosts({ kind: 'technique', host: 'host-a' }), ['host-a'])
  assert.deepEqual(eventHosts({ kind: 'attempt', from_host: 'host-a', to_host: 'server-b' }), ['host-a', 'server-b'])
  const traffic = { kind: 'traffic', packets: [{ src_host: 'host-a', dst_host: 'server-b' }, { src_host: 'host-a', dst_host: 'file-server' }] }
  assert.deepEqual(eventHosts(traffic), ['host-a', 'server-b', 'file-server'])
  assert.match(eventLabel(traffic), /traffic links/)
})

test('timeline lanes group events by host and show display names', () => {
  const lanes = timelineLanes([{ seq: 1, offset_ms: 0, kind: 'attempt', from_host: 'host-a', to_host: 'server-b' }], [
    { host_id: 'host-a', name: 'Workstation A' }, { host_id: 'server-b', name: 'Web Server B' },
  ])
  assert.deepEqual(lanes.map((item) => item.name), ['Workstation A', 'Web Server B'])
})

test('comparison normalization ignores times but retains IDs and outcomes', () => {
  const left = { event_id: 'evt-000001', ts: '2026-01-01', first_alert_at: '2026-01-01', duration_seconds: 1, outcome: 'hit' }
  const right = { event_id: 'evt-000001', ts: '2027-01-01', first_alert_at: '2027-01-01', duration_seconds: 10, outcome: 'hit' }
  assert.deepEqual(normalizeForComparison(left), normalizeForComparison(right))
  assert.notDeepEqual(normalizeForComparison(left), normalizeForComparison({ ...right, outcome: 'miss' }))
})

test('download filenames cannot contain paths or markup', () => {
  assert.equal(safeScenarioFilename('../bad<name>'), '---bad-name-.json')
})

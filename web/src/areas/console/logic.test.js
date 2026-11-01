import test from 'node:test'
import assert from 'node:assert/strict'
import { CONFIRM_SECONDS, containReducer, formatTime, initialContain, replayButtons, replayWord, sceneSummary, threatLevel, timelineMarks } from './logic.js'

const host = (id, name, state = 'normal') => ({ host_id: id, name, zone: 'user', state })
const world = (states, over = {}) => ({ graph: { hosts: states.map((s, i) => host('h' + i, 'Host ' + i, s)) }, alerts: over.alerts || [], forecast: over.forecast || null })

test('threat level uses the same four words as the phone', () => {
  assert.equal(threatLevel(world(['normal'])).word, 'Calm')
  assert.equal(threatLevel(world(['normal'], { alerts: [{}] })).word, 'Watching')
  assert.equal(threatLevel(world(['compromised', 'contained'])).word, 'Under attack')
  assert.equal(threatLevel(world(['contained'])).word, 'Contained')
  assert.equal(threatLevel(null), null)
})

test('replay words and which buttons work in each state', () => {
  assert.equal(replayWord({ state: 'waiting_for_decision' }), 'Waiting for your decision')
  assert.equal(replayWord(null), 'Idle')
  assert.deepEqual(replayButtons({ state: 'idle' }), { start: true, pause: false, resume: false, restart: false })
  assert.deepEqual(replayButtons({ state: 'running' }), { start: false, pause: true, resume: false, restart: true })
  assert.deepEqual(replayButtons({ state: 'paused' }), { start: false, pause: false, resume: true, restart: true })
  assert.deepEqual(replayButtons({ state: 'waiting_for_decision' }), { start: false, pause: false, resume: true, restart: true })
  assert.deepEqual(replayButtons({ state: 'finished' }), { start: true, pause: false, resume: false, restart: true })
})

test('the scene summary lists compromised, contained and the forecast', () => {
  const s = world(['compromised', 'normal', 'contained'], { forecast: { status: 'pending', targets: [{ host_id: 'h1', confidence: 0.74 }] } })
  assert.equal(sceneSummary(s), '3 hosts. 1 compromised: Host 0. 1 contained: Host 2. 1 forecast: Host 1 74 %.')
  assert.equal(sceneSummary(null), 'No data yet.')
})

test('timeline marks run from the oldest alert (0) to the newest (1)', () => {
  const marks = timelineMarks([{ event_id: 'a', severity: 'HIGH', ts: '2026-10-03T10:00:00Z' }, { event_id: 'b', severity: 'LOW', ts: '2026-10-03T10:00:10Z' }, { event_id: 'c', severity: 'HIGH', ts: '2026-10-03T10:00:05Z' }])
  assert.deepEqual(marks.map((m) => m.position), [0, 1, 0.5])
  assert.deepEqual(timelineMarks([]), [])
  assert.equal(timelineMarks([{ event_id: 'a', severity: 'HIGH', ts: '2026-10-03T10:00:00Z' }])[0].position, 1)
})

test('times are HH:MM:SS and NIDS times count as UTC', () => {
  assert.equal(formatTime('2026-10-03 10:00:01', 'UTC'), '10:00:01')
  assert.equal(formatTime('', 'UTC'), '')
})

test('the console containment flow: propose, confirm, done; cancel; expiry; errors', () => {
  let s = containReducer(containReducer(initialContain, { type: 'tap' }), { type: 'proposed', action: { action_id: 'a' } })
  assert.equal(s.step, 'confirming')
  assert.equal(containReducer(s, { type: 'cancel' }).step, 'idle')
  const done = containReducer(containReducer(s, { type: 'confirm' }), { type: 'confirmed', action: { action_id: 'a' } })
  assert.equal(done.step, 'done')
  for (let i = 0; i < CONFIRM_SECONDS; i += 1) s = containReducer(s, { type: 'tick' })
  assert.equal(s.step, 'expired')
  assert.equal(s.message, 'This request expired. Try again.')
  assert.equal(containReducer(initialContain, { type: 'error', message: 'No' }).message, 'No')
  assert.equal(containReducer(initialContain, { type: 'confirm' }).step, 'idle')
})

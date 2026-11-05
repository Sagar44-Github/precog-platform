import test from 'node:test'
import assert from 'node:assert/strict'
import { durationLabel, incidentStats, savedFilterList, severityTone } from './logic.js'

test('severity encoding uses the UI token classes and falls back to low', () => {
  assert.equal(severityTone('HIGH'), 'high')
  assert.equal(severityTone('MEDIUM'), 'medium')
  assert.equal(severityTone('unexpected'), 'low')
})

test('duration labels remain compact and clamp invalid or negative values', () => {
  assert.equal(durationLabel(59), '59s')
  assert.equal(durationLabel(125), '2m 5s')
  assert.equal(durationLabel(3665), '1h 1m')
  assert.equal(durationLabel(-3), '0s')
  assert.equal(durationLabel('unknown'), '0s')
})

test('case summary counts severity, open and forecasted state', () => {
  assert.deepEqual(incidentStats([
    { severity: 'HIGH', status: 'open', forecasts: [{}] },
    { severity: 'MEDIUM', status: 'reopened', forecasts: [] },
    { severity: 'HIGH', status: 'contained', forecasts: [{}] },
  ]), { high: 2, open: 2, forecasted: 2 })
})

test('saved filters ignore invalid storage and cap entries', () => {
  assert.deepEqual(savedFilterList('{bad json'), [])
  assert.deepEqual(savedFilterList('{"x":1}'), [])
  const raw = JSON.stringify(Array.from({ length: 10 }, (_, index) => ({ label: `view-${index}`, filters: {} })))
  assert.equal(savedFilterList(raw).length, 8)
  assert.equal(savedFilterList(raw)[0].label, 'view-2')
})

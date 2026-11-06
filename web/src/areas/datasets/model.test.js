import test from 'node:test'
import assert from 'node:assert/strict'
import { capabilityLabel, comparisonRows, isSwitchable } from './model.js'

test('dataset capability labels distinguish source data from generated estimates', () => {
  assert.equal(capabilityLabel('native'), 'Included in source pack')
  assert.equal(capabilityLabel('derived'), 'Derived for this simulation')
  assert.equal(capabilityLabel('unsupported'), 'Not provided')
})

test('dataset comparison covers the union of declared capabilities', () => {
  const rows = comparisonRows({ capabilities: { topology: 'native', host_compromise: 'derived' } }, { capabilities: { topology: 'derived', detection_labels: 'native' } })
  assert.deepEqual(rows.map((row) => row.key), ['detection_labels', 'host_compromise', 'topology'])
  assert.equal(rows.find((row) => row.key === 'topology').right, 'Derived for this simulation')
})

test('only installed registry entries are switchable', () => {
  assert.equal(isSwitchable({ status: 'active' }), true)
  assert.equal(isSwitchable({ status: 'available' }), true)
  assert.equal(isSwitchable({ status: 'unavailable' }), false)
  assert.equal(isSwitchable(undefined), false)
})

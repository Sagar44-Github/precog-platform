import assert from 'node:assert/strict'
import test from 'node:test'
import { allowedPlaybooksForRole, filterGovernanceRecords, previewProbabilityPercent } from './logic.js'

const playbooks = [
  { playbook_id: 'contain-host', allowed_roles: ['analyst', 'admin'] },
  { playbook_id: 'contain-zone', allowed_roles: ['admin'] },
  { playbook_id: 'release-host', allowed_roles: ['admin'] },
]

test('playbook selector mirrors the server role matrix', () => {
  assert.deepEqual(allowedPlaybooksForRole(playbooks, 'viewer'), [])
  assert.deepEqual(allowedPlaybooksForRole(playbooks, 'analyst').map((item) => item.playbook_id), ['contain-host'])
  assert.deepEqual(allowedPlaybooksForRole(playbooks, 'admin').map((item) => item.playbook_id), ['contain-host', 'contain-zone', 'release-host'])
})

test('impact probability is labelled as removed or restored by action kind', () => {
  assert.equal(previewProbabilityPercent({ probability_removed: 0.736, probability_restored: 0 }, 'contain-host'), 74)
  assert.equal(previewProbabilityPercent({ probability_removed: 0, probability_restored: 0.154 }, 'release-host'), 15)
  assert.equal(previewProbabilityPercent(null, 'contain-host'), 0)
})

test('governance history filters statuses across approvals and releases', () => {
  const records = {
    approvals: [{ action_id: 'one', playbook_id: 'contain-host', status: 'executed', proposed_at: '2026-01-01T00:00:00Z' }],
    releases: [{ action_id: 'two', playbook_id: 'release-host', status: 'released', proposed_at: '2026-01-02T00:00:00Z' }],
  }
  assert.deepEqual(filterGovernanceRecords(records, 'all').map((item) => item.action_id), ['two', 'one'])
  assert.deepEqual(filterGovernanceRecords(records, 'released').map((item) => item.action_id), ['two'])
  assert.deepEqual(filterGovernanceRecords(records, 'all', 'contain-host').map((item) => item.action_id), ['one'])
})

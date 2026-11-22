import test from 'node:test'
import assert from 'node:assert/strict'
import { defaultReachablePair, hasFeasibleRoute } from './workspace-defaults.js'

test('default route is selected from reachable active-workspace hosts', () => {
  const hosts = ['node-1', 'node-2', 'node-3', 'isolated'].map((host_id) => ({ host_id }))
  const edges = [
    { from_host: 'node-1', to_host: 'node-2' },
    { from_host: 'node-2', to_host: 'node-3' },
    { from_host: 'node-3', to_host: 'node-1' },
  ]
  assert.deepEqual(defaultReachablePair(hosts, edges), { from: 'node-1', to: 'node-3' })
  assert.equal(hasFeasibleRoute('node-1', 'node-3', edges), true)
  assert.equal(hasFeasibleRoute('node-1', 'isolated', edges), false)
})

test('route defaults handle empty, single-host and disconnected topologies', () => {
  assert.deepEqual(defaultReachablePair([], []), { from: '', to: '' })
  assert.deepEqual(defaultReachablePair([{ host_id: 'only' }], []), { from: 'only', to: 'only' })
  assert.deepEqual(defaultReachablePair([{ host_id: 'a' }, { host_id: 'b' }], []), { from: 'a', to: 'a' })
})

test('route selection scales to dense 300-host workspace topologies', () => {
  const hosts = Array.from({ length: 300 }, (_, index) => ({ host_id: `h-${index}` }))
  const edges = []
  for (let source = 0; source < hosts.length; source += 1) {
    for (let offset = 1; offset <= 8; offset += 1) {
      const target = (source + offset) % hosts.length
      edges.push({ from_host: hosts[source].host_id, to_host: hosts[target].host_id })
    }
  }
  const pair = defaultReachablePair(hosts, edges)
  assert.equal(hasFeasibleRoute(pair.from, pair.to, edges), true)
  assert.notEqual(pair.from, pair.to)
})

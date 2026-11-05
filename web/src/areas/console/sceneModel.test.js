import test from 'node:test'
import assert from 'node:assert/strict'
import { buildScene, coneOpacity, coneWidth, layoutFor, pulseScale } from './sceneModel.js'

const host = (id, zone, state = 'normal') => ({ host_id: id, name: id.toUpperCase(), zone, state })
const world = (over = {}) => ({
  graph: { hosts: [host('a', 'user', 'compromised'), host('b', 'user'), host('s', 'dmz'), host('d', 'internal', 'contained')], edges: over.edges || [], compromised_path: over.path || ['a'] },
  alerts: [], forecast: over.forecast ?? null,
})
const forecast = { status: 'pending', from_host: 'a', targets: [{ rank: 1, host_id: 's', confidence: 0.74 }, { rank: 2, host_id: 'b', confidence: 0.07 }] }

test('compromised hosts are octahedrons, contained hosts are cubes, normal hosts are small spheres', () => {
  const { nodes } = buildScene(world())
  const by = Object.fromEntries(nodes.map((n) => [n.id, n]))
  assert.deepEqual([by.a.shape, by.a.radius], ['octahedron', 6])
  assert.deepEqual([by.d.shape, by.d.radius], ['cube', 8])
  assert.deepEqual([by.b.shape, by.b.radius], ['sphere', 4])
  assert.equal(by.a.colorVar, '--state-compromised')
  assert.equal(by.d.colorVar, '--state-contained')
})

test('every host has a fixed position and the zones sit side by side', () => {
  const { nodes } = buildScene(world())
  const by = Object.fromEntries(nodes.map((n) => [n.id, n]))
  assert.ok(by.a.x < by.s.x && by.s.x < by.d.x)
  assert.notDeepEqual([by.a.y, by.a.z], [by.b.y, by.b.z])
  assert.deepEqual(layoutFor('dmz', 0, 1), { x: 0, y: 0, z: -0 })
})

test('predicted targets carry their percentage, others do not', () => {
  const { nodes } = buildScene(world({ forecast }))
  const by = Object.fromEntries(nodes.map((n) => [n.id, n]))
  assert.equal(by.s.predicted, 74)
  assert.equal(by.b.predicted, 7)
  assert.equal(by.a.predicted, null)
})

test('asset profiles add role, risk, simulated weakness count, selected state, and overlay to scene nodes', () => {
  const assets = [{ host_id: 's', role: 'Web server', risk_score: 73, weaknesses: [{ id: 'DEMO-1' }, { id: 'DEMO-2' }] }]
  const { nodes } = buildScene(world({ forecast }), assets, { selectedHostId: 's', overlay: 'weakness' })
  const server = nodes.find((node) => node.id === 's')
  assert.equal(server.role, 'Web server')
  assert.equal(server.risk, 73)
  assert.equal(server.weaknessCount, 2)
  assert.equal(server.selected, true)
  assert.equal(server.overlay, 'weakness')
})

test('cones exist only for a pending forecast and grow stronger with confidence', () => {
  assert.deepEqual(buildScene(world()).cones, [])
  assert.deepEqual(buildScene(world({ forecast: { ...forecast, status: 'hit' } })).cones, [])
  const { cones } = buildScene(world({ forecast }))
  assert.equal(cones.length, 2)
  assert.deepEqual([cones[0].from, cones[0].to], ['a', 's'])
  assert.ok(cones[0].width > cones[1].width && cones[0].opacity > cones[1].opacity)
  assert.ok(coneOpacity(0.07) > 0 && coneOpacity(0.07) < 0.25)
  assert.ok(coneWidth(1) > coneWidth(0))
})

test('edges along the attack path are marked', () => {
  const { links } = buildScene(world({ edges: [{ from_host: 'a', to_host: 's', first_seen: 'x' }, { from_host: 'b', to_host: 's', first_seen: 'x' }], path: ['a', 's'] }))
  assert.deepEqual(links.map((l) => l.onPath), [true, false])
  assert.equal(links[0].key, 'a>s')
})

test('zones list their hosts', () => {
  const { zones } = buildScene(world())
  assert.deepEqual(zones.find((z) => z.zone === 'user').hostIds, ['a', 'b'])
})

test('no state gives an empty scene', () => {
  assert.deepEqual(buildScene(null), { nodes: [], links: [], cones: [], zones: [] })
})

test('the pulse grows to 1.6 and back within 600 ms and is 1 outside it', () => {
  assert.equal(pulseScale(0), 1)
  assert.equal(pulseScale(300), 1.6)
  assert.ok(pulseScale(150) > 1 && pulseScale(150) < 1.6)
  assert.equal(pulseScale(600), 1)
  assert.equal(pulseScale(5000), 1)
})

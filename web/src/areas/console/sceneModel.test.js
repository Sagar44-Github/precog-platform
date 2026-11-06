import test from 'node:test'
import assert from 'node:assert/strict'
import { buildScene, buildTwinScene, CLUSTER_THRESHOLD, coneOpacity, coneWidth, exposureScale, forecastScale, layoutFor, pulseScale, riskScale } from './sceneModel.js'

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
  const first = layoutFor('dmz', 0, 1)
  assert.deepEqual([first.x, first.y, first.z], [0, 0, 0])
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
  assert.deepEqual(buildScene(null), { nodes: [], links: [], cones: [], zones: [], lowDetail: false })
})

test('large topologies cluster deterministically and expand one zone at a time', () => {
  const hosts = Array.from({ length: 300 }, (_, index) => {
    const zone = ['user', 'dmz', 'internal', 'application', 'data', 'management'][Math.floor(index / 50)]
    return { host_id: `h-${index}`, name: `Host ${index}`, zone, state: index === 1 ? 'compromised' : 'normal', risk: index % 10 }
  })
  const links = Array.from({ length: 299 }, (_, index) => ({ key: `h-${index}>h-${index + 1}`, source: `h-${index}`, target: `h-${index + 1}`, onPath: index < 2 }))
  const state = { graph: { hosts, edges: links.map((link) => ({ from_host: link.source, to_host: link.target })), compromised_path: ['h-0', 'h-1', 'h-2'] }, alerts: [], forecast: null }
  const collapsed = buildScene(state)
  assert.equal(hosts.length, 300)
  assert.equal(collapsed.lowDetail, true)
  assert.equal(collapsed.nodes.length, 6)
  assert.equal(collapsed.nodes[0].isCluster, true)
  assert.equal(collapsed.nodes.find((node) => node.zone === 'user').stateCounts.compromised, 1)
  assert.deepEqual(collapsed, buildScene(state))
  const expanded = buildScene(state, [], { expandedZones: ['user'] })
  assert.equal(expanded.nodes.filter((node) => node.zone === 'user' && !node.isCluster).length, 50)
  assert.equal(expanded.nodes.length, 55)
  assert.ok(expanded.nodes.every((node) => Number.isFinite(node.x) && Number.isFinite(node.y) && Number.isFinite(node.z)))
  assert.ok(CLUSTER_THRESHOLD <= hosts.length)
})

test('the pulse grows to 1.6 and back within 600 ms and is 1 outside it', () => {
  assert.equal(pulseScale(0), 1)
  assert.equal(pulseScale(300), 1.6)
  assert.ok(pulseScale(150) > 1 && pulseScale(150) < 1.6)
  assert.equal(pulseScale(600), 1)
  assert.equal(pulseScale(5000), 1)
})

const twinTopology = {
  hosts: [
    { host_id: 'a', name: 'Workstation A', zone: 'user', state: 'normal', risk: 2, exposure: 4, services: ['ssh/22'], weaknesses: [] },
    { host_id: 'b', name: 'Web Server B', zone: 'dmz', state: 'normal', risk: 8, exposure: 3, services: ['http/80'], weaknesses: [] },
  ],
  zones: [{ zone: 'user', host_ids: ['a'] }, { zone: 'dmz', host_ids: ['b'] }],
  feasible_edges: [{ from_host: 'a', to_host: 'b', likelihood: 0.8 }],
  compromised_path: ['a', 'b'],
}

test('digital twin maps topology, snapshot state, and attack path into a fixed scene', () => {
  const scene = buildTwinScene(twinTopology, { graph: { hosts: [host('b', 'dmz', 'compromised')] } })
  assert.equal(scene.nodes.length, 2)
  assert.ok(scene.nodes[0].x < scene.nodes[1].x)
  assert.equal(scene.nodes[1].state, 'compromised')
  assert.equal(scene.links[0].onPath, true)
  assert.deepEqual(scene.zones.map((zone) => zone.label), ['USER', 'DMZ'])
})

test('risk, exposure, and forecast overlays encode magnitude with node size', () => {
  assert.ok(riskScale(8) > riskScale(2))
  assert.ok(exposureScale(8) > exposureScale(2))
  assert.ok(forecastScale(0.8) > forecastScale(0.2))
  const state = { graph: { hosts: [] }, forecast: { targets: [{ host_id: 'b', confidence: 0.8 }] } }
  const normal = buildTwinScene(twinTopology, state, { overlay: 'state' })
  const forecast = buildTwinScene(twinTopology, state, { overlay: 'forecast' })
  assert.ok(forecast.nodes[1].radius > normal.nodes[1].radius)
  assert.equal(forecast.nodes[1].predicted, 80)
})

test('risk and exposure values are bounded and tolerate missing values', () => {
  assert.equal(riskScale(100), riskScale(10))
  assert.equal(exposureScale(-4), exposureScale(0))
  assert.equal(forecastScale(null), forecastScale(0))
})

test('missing twin topology returns an empty scene', () => {
  assert.deepEqual(buildTwinScene(null, null), { nodes: [], links: [], cones: [], zones: [], lowDetail: false })
})

test('300-host twin collapses to zone clusters and bundles dense links', () => {
  const zones = ['user', 'dmz', 'internal', 'application', 'data', 'management']
  const hosts = Array.from({ length: 300 }, (_, index) => ({
    host_id: `t-${index}`, name: `Twin ${index}`, zone: zones[Math.floor(index / 50)], state: 'normal', risk: 4, exposure: 2,
  }))
  const feasible_edges = Array.from({ length: 300 }, (_, index) => ({
    from_host: `t-${index}`, to_host: `t-${(index + 50) % 300}`, likelihood: 0.4,
  }))
  const topology = { hosts, zones: zones.map((zone) => ({ zone, host_ids: hosts.filter((host) => host.zone === zone).map((host) => host.host_id) })), feasible_edges, compromised_path: [] }
  const model = buildTwinScene(topology, null)
  assert.equal(model.lowDetail, true)
  assert.equal(model.nodes.length, zones.length)
  assert.equal(model.nodes.filter((node) => node.isCluster).length, zones.length)
  assert.equal(model.links.length, zones.length)
  assert.ok(model.links.every((link) => link.count === 50))
  const liteCompatible = buildTwinScene(topology, null, { expandedZones: ['user'] })
  assert.equal(liteCompatible.nodes.filter((node) => node.zone === 'user' && !node.isCluster).length, 50)
})

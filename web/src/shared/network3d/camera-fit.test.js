import test from 'node:test'
import assert from 'node:assert/strict'
import { fitDistance, nodeGeometryKey } from './camera-fit.js'

function nodesInGrid(count, { offset = 0, spacing = 34 } = {}) {
  const columns = Math.ceil(Math.sqrt(count))
  return Array.from({ length: count }, (_, index) => ({
    id: `node-${index}`, x: offset + (index % columns) * spacing,
    y: (index % 3) * 5, z: Math.floor(index / columns) * spacing,
    radius: index % 4 === 0 ? 8 : 4,
  }))
}

test('fits small, medium, 120-host and 300-host graphs around their actual bounds', () => {
  for (const count of [1, 6, 30, 120, 300]) {
    const nodes = nodesInGrid(count, { offset: 420 })
    const fit = fitDistance(nodes, 1440, 900)
    assert.ok(fit, `${count} nodes should produce a fit`)
    assert.ok(fit.distance > fit.radius)
    assert.ok(Math.asin(fit.radius / fit.distance) < fit.limitingHalfFov, `${count}-node graph fits the limiting viewport dimension`)
    for (const node of nodes) {
      const distance = Math.hypot(node.x - fit.center.x, node.y - fit.center.y, node.z - fit.center.z)
      assert.ok(distance + node.radius * 4 <= fit.radius + 1e-8, `${count}-node graph bounds should be enclosed`)
    }
  }
})

test('narrow viewports request more distance than wide ones', () => {
  const nodes = nodesInGrid(30)
  const wide = fitDistance(nodes, 1440, 900)
  const portrait = fitDistance(nodes, 390, 844)
  assert.ok(portrait.distance > wide.distance)
  assert.ok(fitDistance(nodes, 820, 1180).distance > wide.distance)
})

test('single-node, invalid-coordinate and empty inputs have safe results', () => {
  const fit = fitDistance([{ id: 'one', x: 90, y: -12, z: 6, radius: 10 }], 390, 844)
  assert.deepEqual(fit.center, { x: 90, y: -12, z: 6 })
  assert.equal(fit.radius, 40)
  assert.equal(fitDistance([{ x: NaN, y: 0, z: 0 }], 300, 400), null)
  assert.equal(fitDistance([], 300, 400), null)
})

test('geometry key reacts to position or radius changes but ignores state-only changes', () => {
  const start = [{ id: 'a', x: 1, y: 2, z: 3, radius: 4, state: 'normal' }]
  assert.equal(nodeGeometryKey(start), nodeGeometryKey([{ ...start[0], state: 'compromised' }]))
  assert.notEqual(nodeGeometryKey(start), nodeGeometryKey([{ ...start[0], x: 5 }]))
  assert.notEqual(nodeGeometryKey(start), nodeGeometryKey([{ ...start[0], radius: 8 }]))
})

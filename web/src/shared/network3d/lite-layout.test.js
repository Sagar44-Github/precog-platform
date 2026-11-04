import test from 'node:test'
import assert from 'node:assert/strict'
import { buildLiteLayout } from './lite-layout.js'

test('Lite layout groups hosts by zone and resolves network links', () => {
  const model = {
    nodes: [{ id: 'a', zone: 'user' }, { id: 'b', zone: 'user' }, { id: 's', zone: 'dmz' }],
    links: [{ key: 'a>s', source: 'a', target: 's' }],
  }
  const layout = buildLiteLayout(model)
  assert.equal(layout.nodes.length, 3)
  assert.ok(layout.nodes[0].px < layout.nodes[2].px)
  assert.notEqual(layout.nodes[0].py, layout.nodes[1].py)
  assert.deepEqual([layout.links[0].from.id, layout.links[0].to.id], ['a', 's'])
})

test('Lite layout accepts a resized viewport and an empty model', () => {
  const model = { nodes: [{ id: 'a', zone: 'user' }], links: [] }
  const wide = buildLiteLayout(model, 800, 500)
  assert.ok(wide.nodes[0].px < 800 && wide.nodes[0].py < 500)
  assert.deepEqual(buildLiteLayout(null).nodes, [])
})

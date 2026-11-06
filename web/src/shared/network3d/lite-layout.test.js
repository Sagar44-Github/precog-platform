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
  assert.notDeepEqual([layout.nodes[0].px, layout.nodes[0].py], [layout.nodes[1].px, layout.nodes[1].py])
  assert.deepEqual([layout.links[0].from.id, layout.links[0].to.id], ['a', 's'])
})

test('Lite layout accepts a resized viewport and an empty model', () => {
  const model = { nodes: [{ id: 'a', zone: 'user' }], links: [] }
  const wide = buildLiteLayout(model, 800, 500)
  assert.ok(wide.nodes[0].px < 800 && wide.nodes[0].py < 500)
  assert.deepEqual(buildLiteLayout(null).nodes, [])
})

test('Lite layout keeps 300 hosts inside their zones with distinct stable positions', () => {
  const zones = ['user', 'dmz', 'internal', 'application', 'data', 'management']
  const nodes = Array.from({ length: 300 }, (_, index) => ({ id: `h-${index}`, zone: zones[Math.floor(index / 50)] }))
  const model = { nodes, links: [{ source: 'h-0', target: 'h-50' }] }
  const layout = buildLiteLayout(model, 1200, 720)
  assert.equal(layout.nodes.length, 300)
  assert.equal(layout.zones.length, 6)
  assert.ok(layout.nodes.every((node) => node.px >= 0 && node.px <= 1200 && node.py >= 0 && node.py <= 720))
  assert.deepEqual(layout.nodes, buildLiteLayout(model, 1200, 720).nodes)
  assert.equal(layout.links.length, 1)
})

test('virtual table window bounds work at the beginning, middle and end', async () => {
  const { virtualWindow } = await import('./lite-layout.js')
  assert.deepEqual(virtualWindow(300, 0, 60, 300, 2), { start: 0, end: 9, offset: 0, totalHeight: 18000 })
  const middle = virtualWindow(300, 6000, 60, 300, 2)
  assert.equal(middle.start, 98)
  assert.equal(middle.end, 107)
  assert.equal(middle.offset, 5880)
  assert.equal(virtualWindow(300, 999999, 60, 300, 2).end, 300)
  assert.deepEqual(virtualWindow(10, 0, 0, 300), { start: 0, end: 0, offset: 0, totalHeight: 0 })
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { browserVar, readSceneColors } from './theme3d.js'

test('scene colors normalize modern CSS HSL into a Three.js-compatible value', () => {
  let color = ''
  const documentRef = {
    documentElement: {},
    createElement: () => ({ getContext: () => ({ set fillStyle(value) { color = value.startsWith('hsl(') ? 'rgb(94, 105, 120)' : value }, get fillStyle() { return color } }) }),
  }
  const getStyle = () => ({ getPropertyValue: () => 'hsl(215 12% 42%)' })
  assert.equal(browserVar('--state-normal', documentRef, getStyle), 'rgb(94, 105, 120)')
})

test('scene color normalization keeps fallback behavior when a canvas context is unavailable', () => {
  const documentRef = { documentElement: {}, createElement: () => ({ getContext: () => null }) }
  assert.equal(browserVar('--forecast', documentRef, () => ({ getPropertyValue: () => 'hsl(260 45% 62%)' })), 'hsl(260 45% 62%)')
  assert.equal(readSceneColors(() => 'violet').forecast, 'violet')
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { autoViewMode, CAMERA_PRESETS, supportsWebGL } from './camera-presets.js'

test('automatic view uses Lite below desktop width, reduced motion, or missing WebGL', () => {
  assert.equal(autoViewMode({ width: 1023, reducedMotion: false, webgl: true }), 'lite')
  assert.equal(autoViewMode({ width: 1440, reducedMotion: true, webgl: true }), 'lite')
  assert.equal(autoViewMode({ width: 1440, reducedMotion: false, webgl: false }), 'lite')
  assert.equal(autoViewMode({ width: 1440, reducedMotion: false, webgl: true }), '3d')
})

test('camera presets provide isometric, top, and side views', () => {
  assert.deepEqual(Object.keys(CAMERA_PRESETS), ['isometric', 'top', 'side'])
  assert.equal(CAMERA_PRESETS.top.position.y > CAMERA_PRESETS.side.position.y, true)
})

test('WebGL capability detection handles missing documents safely', () => {
  assert.equal(supportsWebGL(null), false)
  assert.equal(supportsWebGL({ createElement: () => ({ getContext: () => null }) }), false)
})

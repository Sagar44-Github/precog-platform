import test from 'node:test'
import assert from 'node:assert/strict'
import { createQualityManager, initialQuality, qualitySettings, recordFrame } from './qualityManager.js'

test('low-power, phone, reduced-motion, data-saver and software renderers start Lite', () => {
  assert.equal(initialQuality({ phone: true }), 'lite')
  assert.equal(initialQuality({ saveData: true }), 'lite')
  assert.equal(initialQuality({ reducedMotion: true }), 'lite')
  assert.equal(initialQuality({ renderer: 'Google SwiftShader' }), 'lite')
  assert.equal(initialQuality({}), 'high')
})

test('quality settings cap pixel ratio in high, balanced and lite tiers', () => {
  const desktop = createQualityManager({ devicePixelRatio: 3 })
  const phone = createQualityManager({ phone: true, devicePixelRatio: 3 })
  const balanced = qualitySettings({ tier: 'balanced' }, 3)
  assert.equal(qualitySettings(desktop, 3).pixelRatio, 1.75)
  assert.equal(balanced.pixelRatio, 1.35)
  assert.equal(qualitySettings(phone, 3).pixelRatio, 1)
})

test('frame-time budget steps quality down and never raises it during a session', () => {
  let manager = createQualityManager({})
  for (let index = 0; index < 180; index += 1) manager = recordFrame(manager, 35)
  assert.equal(manager.tier, 'lite')
  for (let index = 0; index < 600; index += 1) manager = recordFrame(manager, 5)
  assert.equal(manager.tier, 'lite')
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { demoState, normalizeDemoStep } from './demoState.js'

test('the demonstration advances through detection, reconstruction, forecast and confirmed containment', () => {
  assert.deepEqual([0, 1, 2, 3, 4].map((step) => {
    const state = demoState(step)
    return [state.detected, state.reconstructed, state.forecast, state.contained]
  }), [
    [false, false, false, false],
    [true, false, false, false],
    [true, true, false, false],
    [true, true, true, false],
    [true, true, true, true],
  ])
})

test('step input is deterministic, rounded to a valid step, and safe for invalid input', () => {
  assert.equal(normalizeDemoStep(2.2), 2)
  assert.equal(normalizeDemoStep(-1), 0)
  assert.equal(normalizeDemoStep(9), 4)
  assert.equal(normalizeDemoStep(Number.NaN), 0)
  assert.deepEqual(demoState(3), demoState(3))
})

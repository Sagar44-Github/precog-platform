import test from 'node:test'
import assert from 'node:assert/strict'
import { isStale, stateUrl, applyReply } from './pollingLogic.js'

test('not stale before the first success', () => {
  assert.equal(isStale(null, 10_000, 1500), false)
})

test('not stale within twice the interval', () => {
  assert.equal(isStale(1000, 3500, 1500), false)
})

test('stale after more than twice the interval', () => {
  assert.equal(isStale(1000, 4001, 1500), true)
})

test('first poll has no since, later polls do', () => {
  assert.equal(stateUrl(null), '/api/x/state')
  assert.equal(stateUrl(0), '/api/x/state?since=0')
  assert.equal(stateUrl(12), '/api/x/state?since=12')
})

test('an unchanged reply keeps the old state', () => {
  const old = { version: 3, changed: true, alerts: [] }
  assert.equal(applyReply(old, { version: 3, changed: false }), old)
})

test('a changed reply replaces the state', () => {
  const next = { version: 4, changed: true, alerts: [1] }
  assert.equal(applyReply({ version: 3 }, next), next)
})

test('a broken reply is ignored', () => {
  const old = { version: 3 }
  assert.equal(applyReply(old, null), old)
  assert.equal(applyReply(old, { nope: 1 }), old)
})

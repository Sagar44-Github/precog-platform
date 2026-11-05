import test from 'node:test'
import assert from 'node:assert/strict'
import { api } from './api.js'

test('alert search forwards nonempty filters to the existing search endpoint', async (t) => {
  const original = globalThis.fetch
  let requested
  globalThis.fetch = async (url) => {
    requested = String(url)
    return { ok: true, json: async () => ({ items: [], total: 0 }) }
  }
  t.after(() => { globalThis.fetch = original })

  await api.searchAlerts({ q: 'ssh login', severity: 'HIGH', cursor: '', limit: 50 })
  const url = new URL(requested, 'http://precog.test')
  assert.equal(url.pathname, '/api/x/alerts/search')
  assert.equal(url.searchParams.get('q'), 'ssh login')
  assert.equal(url.searchParams.get('severity'), 'HIGH')
  assert.equal(url.searchParams.get('limit'), '50')
  assert.equal(url.searchParams.has('cursor'), false)
})

test('report collection and detail use their authenticated API routes', async (t) => {
  const original = globalThis.fetch
  const requested = []
  globalThis.fetch = async (url) => {
    requested.push(String(url))
    return { ok: true, json: async () => ({ items: [] }) }
  }
  t.after(() => { globalThis.fetch = original })

  await api.reports()
  await api.report('session/with space')
  assert.equal(requested[0], '/api/x/reports')
  assert.equal(requested[1], '/api/x/reports/session%2Fwith%20space')
})

test('system health and audit pages call their existing endpoints', async (t) => {
  const original = globalThis.fetch
  const requested = []
  globalThis.fetch = async (url) => {
    requested.push(String(url))
    return { ok: true, json: async () => ({ items: [], checks: {} }) }
  }
  t.after(() => { globalThis.fetch = original })

  await api.system()
  await api.audit({ type: 'incident', ref_id: 'inc 01', q: '', from: '2026-11-01', cursor: '50', limit: 50 })
  assert.equal(requested[0], '/api/x/system')
  const url = new URL(requested[1], 'http://precog.test')
  assert.equal(url.pathname, '/api/x/audit')
  assert.equal(url.searchParams.get('type'), 'incident')
  assert.equal(url.searchParams.get('ref_id'), 'inc 01')
  assert.equal(url.searchParams.get('from'), '2026-11-01')
  assert.equal(url.searchParams.get('cursor'), '50')
  assert.equal(url.searchParams.get('limit'), '50')
  assert.equal(url.searchParams.has('q'), false)
})

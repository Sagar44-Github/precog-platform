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

test('topology and inventory helpers expose the active workspace endpoints', async (t) => {
  const calls = []
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url) => {
    calls.push(String(url))
    return { ok: true, status: 200, json: async () => ({ items: [], hosts: [] }) }
  }
  t.after(() => { globalThis.fetch = originalFetch })
  const { api } = await import('./api.js')
  await api.assets()
  await api.topologySummary({ offset: 40, limit: 20, q: 'node-0042', zone: 'application' })
  await api.timeTravel({ limit: 200, session_id: 'session 01' })
  assert.equal(calls[0], '/api/x/assets')
  assert.equal(calls[1], '/api/x/topology/summary?offset=40&limit=20&q=node-0042&zone=application')
  assert.equal(calls[2], '/api/x/time-travel?limit=200&session_id=session+01')
})

test('workspace UI helpers use the existing registry, card, and confirmed activation routes', async (t) => {
  const calls = []
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options })
    return { ok: true, status: 200, json: async () => ({ workspaces: [], id: 'synth-enterprise-30' }) }
  }
  t.after(() => { globalThis.fetch = originalFetch })
  await api.workspaces()
  await api.workspaceCard('bad/id')
  await api.activateWorkspace('synth-enterprise-30')
  assert.equal(calls[0].url, '/api/x/workspaces')
  assert.equal(calls[1].url, '/api/x/workspaces/bad%2Fid/card')
  assert.equal(calls[2].url, '/api/x/workspaces/synth-enterprise-30/activate')
  assert.deepEqual(JSON.parse(calls[2].options.body), { confirm: true })
})

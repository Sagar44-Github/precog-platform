import test from 'node:test'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { Route, Routes } from 'react-router-dom'
import { StaticRouter } from 'react-router-dom/server.js'
import AppShell from '../../shared/AppShell.jsx'
import { AuthProvider } from '../../shared/AuthContext.jsx'
import { ThemeProvider } from '../../shared/theme-context.jsx'
import { UiPreferencesProvider } from '../../shared/ui-preferences.jsx'
import AlertsPage from './alerts.jsx'
import AlertDetailPage from './alert-detail.jsx'
import AuditPage from './audit.jsx'
import HostDetailPage from './host-detail.jsx'
import HostsPage from './hosts.jsx'
import SettingsPage from './settings.jsx'
import SystemPage from './system.jsx'

function render(path) {
  return renderToStaticMarkup(<StaticRouter location={path}><AuthProvider><ThemeProvider><UiPreferencesProvider><AppShell><Routes>
    <Route path="/alerts" element={<AlertsPage />} />
    <Route path="/alerts/:alertId" element={<AlertDetailPage />} />
    <Route path="/hosts" element={<HostsPage />} />
    <Route path="/hosts/:hostId" element={<HostDetailPage />} />
    <Route path="/audit" element={<AuditPage />} />
    <Route path="/system" element={<SystemPage />} />
    <Route path="/settings" element={<SettingsPage />} />
  </Routes></AppShell></UiPreferencesProvider></ThemeProvider></AuthProvider></StaticRouter>)
}

test('alerts route renders search, filters, export, and simulation context', () => {
  const html = render('/alerts')
  assert.match(html, /Search and review detection events/)
  assert.match(html, /Export CSV/)
  assert.match(html, /Apply filters/)
  assert.match(html, /SIMULATION/)
})

test('alert detail route keeps event context and a return path', () => {
  const html = render('/alerts/evt-demo')
  assert.match(html, /Alert detail/)
  assert.match(html, /Back to alerts/)
  assert.match(html, /technique context/)
})

test('asset routes state that simulated weaknesses are synthetic', () => {
  const inventory = render('/hosts')
  const detail = render('/hosts/host-a')
  assert.match(inventory, /six simulated hosts/)
  assert.match(detail, /Host detail/)
})

test('audit and system pages describe the records and runtime inspection', () => {
  assert.match(render('/audit'), /Read-only records written by detection/)
  assert.match(render('/system'), /Loaded modules, registration hooks/)
})

test('settings provide persisted display preference controls', () => {
  const html = render('/settings')
  assert.match(html, /Data density/)
  assert.match(html, /Default severity/)
  assert.match(html, /presentation only/)
})

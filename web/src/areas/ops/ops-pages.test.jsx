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
import IncidentsPage from './incidents.jsx'
import IncidentDetailPage from './incident-detail.jsx'
import ReportsPage from './reports.jsx'
import ReportDetailPage from './report-detail.jsx'
import ForecastsPage from './forecasts.jsx'
import ForecastDetailPage from './forecast-detail.jsx'
import AnalyticsPage from './analytics.jsx'
import ContainmentPage from './containment.jsx'
import ReplayStudioPage from './replay-studio.jsx'
import ScenarioBuilderPage from './scenario-builder.jsx'
import TopologyExplorerPage from '../console/topology-explorer.jsx'
import HelpPage from './help.jsx'
import AboutPage from './about.jsx'

function render(path) {
  return renderToStaticMarkup(<StaticRouter location={path}><AuthProvider><ThemeProvider><UiPreferencesProvider><AppShell><Routes>
    <Route path="/alerts" element={<AlertsPage />} />
    <Route path="/alerts/:alertId" element={<AlertDetailPage />} />
    <Route path="/incidents" element={<IncidentsPage />} />
    <Route path="/incidents/:incidentId" element={<IncidentDetailPage />} />
    <Route path="/reports" element={<ReportsPage />} />
    <Route path="/reports/:sessionId" element={<ReportDetailPage />} />
    <Route path="/forecasts" element={<ForecastsPage />} />
    <Route path="/forecasts/:forecastId" element={<ForecastDetailPage />} />
    <Route path="/analytics" element={<AnalyticsPage />} />
    <Route path="/containment" element={<ContainmentPage />} />
    <Route path="/replay" element={<ReplayStudioPage />} />
    <Route path="/scenarios" element={<ScenarioBuilderPage />} />
    <Route path="/console/topology" element={<TopologyExplorerPage />} />
    <Route path="/help" element={<HelpPage />} />
    <Route path="/about" element={<AboutPage />} />
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

test('incident routes expose case search and refresh-safe detail loading', () => {
  const list = render('/incidents')
  const detail = render('/incidents/inc-ses-000001')
  assert.match(list, /Replay sessions are grouped into incident cases/)
  assert.match(list, /All statuses/)
  assert.match(list, /SIMULATION/)
  assert.match(detail, /Incident detail/)
  assert.match(detail, /Loading workspace data/)
})

test('report routes offer printable session summaries and explicit metric scope', () => {
  const list = render('/reports')
  const detail = render('/reports/ses-000001')
  assert.match(list, /Printable, exportable summaries/)
  assert.match(list, /not overall model accuracy/)
  assert.match(detail, /PRINTABLE REPORT/)
  assert.match(detail, /Print report/)
  assert.match(detail, /Export timeline CSV/)
})

test('forecast routes expose the replay ledger, read-only what-if, and explainability detail', () => {
  const ledger = render('/forecasts')
  const detail = render('/forecasts/fc-000001')
  assert.match(ledger, /Every recorded prediction keeps its original candidate set/)
  assert.match(ledger, /Read-only what-if/)
  assert.match(ledger, /Model analytics/)
  assert.match(detail, /Review the prediction as it was captured/)
  assert.match(detail, /Back to forecasts/)
})

test('analytics route starts with a scoped loading view and shell navigation entries', () => {
  const html = render('/analytics')
  assert.match(html, /Held-out model evaluation, calibration, baselines/)
  assert.match(html, /Loading workspace data/)
  assert.match(html, /Forecasts/)
  assert.match(html, /Analytics/)
  assert.match(html, /SIMULATION/)
})

test('containment route shows simulation guardrails, action history, and read-only viewer access', () => {
  const html = render('/containment')
  assert.match(html, /Containment/)
  assert.match(html, /do not change a real network/)
  assert.match(html, /Action history/)
  assert.match(html, /Read-only role/)
  assert.match(html, /Containment/)
  assert.match(html, /SIMULATION/)
})

test('replay studio exposes controls, event sequence, time travel, and session compare', () => {
  const html = render('/replay')
  assert.match(html, /Replay Studio/)
  assert.match(html, /Replay controls/)
  assert.match(html, /Time travel/)
  assert.match(html, /Compare finished sessions/)
  assert.match(html, /session counters describe these runs/i)
  assert.match(html, /SIMULATION/)
})

test('scenario builder lists the simulation library and explains viewer limits', () => {
  const html = render('/scenarios')
  assert.match(html, /Scenario builder/)
  assert.match(html, /Scenario library/)
  assert.match(html, /Viewer accounts can browse scenarios/)
  assert.match(html, /do not generate real traffic/)
  assert.match(html, /SIMULATION/)
})

test('topology explorer is refresh-safe and keeps its simulation header while loading', () => {
  const html = render('/console/topology')
  assert.match(html, /Topology explorer/)
  assert.match(html, /SIMULATION ONLY/)
  assert.match(html, /topology-loading/)
})

test('help page includes the walkthrough, shortcuts, glossary, and simulation quickstart', () => {
  const html = render('/help')
  assert.match(html, /Help &amp; walkthrough/)
  assert.match(html, /Start guided tour/)
  assert.match(html, /Golden Path quickstart/)
  assert.match(html, /Precision@1 \/ @3/)
  assert.match(html, /SIMULATION/)
})

test('about page states the simulation scope, architecture, limitations, and credits', () => {
  const html = render('/about')
  assert.match(html, /About Precog SOC/)
  assert.match(html, /Simulation environment/)
  assert.match(html, /Limitations/)
  assert.match(html, /Credits and licensing/)
  assert.match(html, /no vulnerability scan is run/i)
})

test('guided tour deep links render a keyboard-operated dialog at the requested step', () => {
  const html = render('/console/topology?tour=golden-path&step=0')
  assert.match(html, /role="dialog" aria-modal="true"/)
  assert.match(html, /Start with the network/)
  assert.match(html, /STEP 1 OF 7/)
  assert.match(html, /Close tour/)
})

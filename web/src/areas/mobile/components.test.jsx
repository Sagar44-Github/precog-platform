import test from 'node:test'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { AccuracyCounter, AlertCard, AttackPath2D, ForecastBars, OutcomeCard, SeverityBadge, StateChip, ThreatLevelCard } from './components.jsx'
import { TabBar } from './index.jsx'
import { HomeScreen } from './screens.jsx'
import { ToastProvider } from '../../shared/components.jsx'

const alert = { event_id: 'evt-000001', ts: '2026-10-03T10:00:01Z', host: 'host-a', severity: 'HIGH', explanation: 'Workstation A sent a 2500-byte TCP packet to port 22 (SSH, remote login) on Workstation B.',
  technique_id: 'T1021.004', technique_name: 'SSH', source: 'nids_detector', risk_score: 49.9, packet_id: 2, anomaly: false }
const state = {
  graph: { hosts: [{ host_id: 'host-a', name: 'Workstation A', zone: 'user', state: 'compromised' }, { host_id: 'server-b', name: 'Web Server B', zone: 'dmz', state: 'normal' }], edges: [], compromised_path: ['host-a'] },
  alerts: [alert],
  forecast: { forecast_id: 'fc-1', status: 'pending', targets: [{ rank: 1, host_id: 'server-b', confidence: 0.74 }], technique_hint: { technique_id: 'T1021', technique_name: 'Remote Services', probability: 0.41 }, outcome: null },
  metrics: { forecasts_resolved: 1, hits: 1, hit_rate: 1, calibration_bins: [] },
}
const html = (el) => renderToStaticMarkup(<MemoryRouter>{el}</MemoryRouter>)

test('severity badge shows icon and word, not colour alone', () => {
  const out = html(<SeverityBadge severity="HIGH" />)
  assert.match(out, /▲/)
  assert.match(out, /High/)
})

test('state chip shows the word for each state', () => {
  assert.match(html(<StateChip state="compromised" />), /Compromised/)
  assert.match(html(<StateChip state="contained" />), /Contained/)
})

test('threat level card says Under attack with its caption and dims when stale', () => {
  const out = html(<ThreatLevelCard state={state} stale={false} />)
  assert.match(out, /Under attack/)
  assert.match(out, /1 host compromised, 1 forecast pending/)
  assert.match(html(<ThreatLevelCard state={state} stale />), /data-stale="true"/)
})

test('alert card shows the explanation, the technique and the host id', () => {
  const out = html(<AlertCard alert={alert} />)
  assert.match(out, /Workstation A sent a 2500-byte/)
  assert.match(out, /SSH · T1021\.004/)
  assert.match(out, /host-a/)
})

test('a scripted alert is tagged scripted', () => {
  assert.match(html(<AlertCard alert={{ ...alert, source: 'scripted' }} />), /scripted/)
})

test('forecast bars use the word predicts, show names and percentages, and the technique line', () => {
  const out = html(<ForecastBars state={state} />)
  assert.match(out, /Precog predicts the next target/)
  assert.match(out, /Web Server B/)
  assert.match(out, /74 %/)
  assert.match(out, /Likely next technique: Remote Services/)
  assert.doesNotMatch(out, /will /)
})

test('forecast bars explain themselves when nothing is pending', () => {
  assert.match(html(<ForecastBars state={{ ...state, forecast: null }} />), /No forecast right now/)
})

test('the accuracy counter carries its honesty label', () => {
  const out = html(<AccuracyCounter metrics={state.metrics} />)
  assert.match(out, /1 \/ 1 \(100 %\)/)
  assert.match(out, /Session counter, not the model(&#x27;|')s overall accuracy\./)
})

test('attack path lists the compromised host and the predicted next one', () => {
  const out = html(<AttackPath2D state={state} />)
  assert.match(out, /Workstation A/)
  assert.match(out, /Web Server B predicted, 74 %/)
})

test('outcome card says a miss as plainly as a hit', () => {
  const miss = { status: 'miss', outcome: { attempted_host: 'server-b', rank_hit: null, blocked: false } }
  assert.match(html(<OutcomeCard forecast={miss} state={state} />), /Precog missed\. The attacker went to Web Server B instead\./)
  assert.equal(html(<OutcomeCard forecast={state.forecast} state={state} />), '')
})

test('the tab bar has four tabs, a high-alert count and a forecast dot', () => {
  const out = html(<TabBar state={state} />)
  for (const word of ['Home', 'Alerts', 'Forecast', 'History']) assert.match(out, new RegExp(word))
  assert.match(out, /1 high alerts/)
  assert.match(out, /A forecast is pending/)
})

test('the home screen shows the threat level, the contain button, the latest alert and the accuracy', () => {
  const out = html(<ToastProvider><HomeScreen state={state} stale={false} /></ToastProvider>)
  assert.match(out, /Under attack/)
  assert.match(out, /Contain Web Server B/)
  assert.match(out, /Latest alert/)
  assert.match(out, /Precog accuracy this session/)
})

test('the home screen shows grey loading bars before the first reply', () => {
  assert.match(html(<ToastProvider><HomeScreen state={null} stale={false} /></ToastProvider>), /Loading/)
})

test('the home screen has no contain button when no forecast is pending', () => {
  assert.doesNotMatch(html(<ToastProvider><HomeScreen state={{ ...state, forecast: null }} stale={false} /></ToastProvider>), /Contain /)
})

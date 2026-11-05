import test from 'node:test'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server.js'
import { AlertsPanel, ConsoleContain, ForecastPanel, LeftRail, NodeDetailPanel, ReplayControls, SceneSummary, TimelineStrip, TopBar } from './panels.jsx'
import { AlertVolumeChart, ForecastAccuracyChart } from '../charts/index.jsx'

const alert = { event_id: 'evt-000001', ts: '2026-10-03T10:00:01Z', host: 'host-a', severity: 'HIGH', explanation: 'Workstation A sent a packet to port 22.', technique_id: null, technique_name: null, source: 'scripted', risk_score: 80, packet_id: null, anomaly: true }
const state = {
  version: 5,
  graph: { hosts: [{ host_id: 'host-a', name: 'Workstation A', zone: 'user', state: 'compromised' }, { host_id: 'server-b', name: 'Web Server B', zone: 'dmz', state: 'normal' }], edges: [], compromised_path: ['host-a'] },
  alerts: [alert],
  forecast: { forecast_id: 'fc-000001', status: 'pending', from_host: 'host-a', targets: [{ rank: 1, host_id: 'server-b', confidence: 0.74 }], technique_hint: null, outcome: null },
  replay: { state: 'waiting_for_decision', scenario_id: 'golden-path', speed: 1, position: 3 },
  metrics: { forecasts_resolved: 1, hits: 1, hit_rate: 1, calibration_bins: [] },
}
const html = (el) => renderToStaticMarkup(<StaticRouter location="/console">{el}</StaticRouter>)

test('the replay top bar shows the threat level and the connection', () => {
  const out = html(<TopBar state={state} stale={false} />)
  assert.match(out, /Threat: Under attack/)
  assert.match(out, /Connected/)
  assert.match(html(<TopBar state={state} stale />), /Offline · stale data/)
})

test('replay controls say "Waiting for your decision" and enable only the useful buttons', () => {
  const out = html(<ReplayControls replay={state.replay} />)
  assert.match(out, /Waiting for your decision/)
  assert.match(out, /c-waiting/)
  assert.match(out, /aria-label="Pause replay"[^>]*disabled/)
  assert.doesNotMatch(out, /aria-label="Resume replay"[^>]*disabled/)
  assert.doesNotMatch(out, /aria-label="Restart replay"[^>]*disabled/)
  assert.match(out, /<button[^>]*disabled[^>]*>Start/)
})

test('an idle replay can only be started', () => {
  const out = html(<ReplayControls replay={{ state: 'idle', scenario_id: null, speed: 1, position: 0 }} />)
  assert.match(out, /Idle/)
  assert.doesNotMatch(out, /<button[^>]*disabled[^>]*>Start/)
  assert.match(out, /aria-label="Restart replay"[^>]*disabled/)
})

test('viewer replay controls are read-only and analysts cannot restart', () => {
  const viewer = html(<ReplayControls replay={state.replay} permissions={{ can_run_replay: false, can_restart_replay: false }} />)
  assert.match(viewer, /Viewer access · read only/)
  assert.doesNotMatch(viewer, /aria-label="Scenario"/)
  assert.doesNotMatch(viewer, /Start/)
  const analyst = html(<ReplayControls replay={state.replay} permissions={{ can_run_replay: true, can_restart_replay: false }} />)
  assert.match(analyst, /aria-label="Scenario"/)
  assert.doesNotMatch(analyst, /aria-label="Restart replay"/)
})

test('the console view tabs use a compact operator hierarchy with the selected view marked', () => {
  const out = html(<LeftRail view="alerts" onChange={() => {}} />)
  for (const word of ['Network', 'Events', 'Metrics']) assert.match(out, new RegExp(word))
  assert.match(out, /aria-label="Events"[^>]*>|aria-pressed="true"[^>]*aria-label="Events"/)
})

test('the contain button names the top predicted host, and is absent without a forecast', () => {
  assert.match(html(<ConsoleContain state={state} />), /Contain Web Server B/)
  assert.equal(html(<ConsoleContain state={{ ...state, forecast: null }} />), '')
  assert.equal(html(<ConsoleContain state={state} allowed={false} />), '')
})

test('the forecast panel shows the forecast bars, the contain button and a collapsible attack path', () => {
  const out = html(<ForecastPanel state={state} resolved={null} />)
  assert.match(out, /74%/)
  assert.match(out, /Contain Web Server B/)
  assert.match(out, /Observed attack path/)
  assert.match(out, /<details class="disclosure c-module" open=/)
})

test('the node panel shows the host, its state, its recent alerts and Contain when it is predicted', () => {
  const out = html(<NodeDetailPanel state={state} hostId="server-b" onClose={() => {}} />)
  assert.match(out, /Web Server B/)
  assert.match(out, /Contain Web Server B/)
  const compromised = html(<NodeDetailPanel state={state} hostId="host-a" onClose={() => {}} />)
  assert.match(compromised, /Workstation A sent a packet/)
  assert.doesNotMatch(compromised, /Contain /)
  assert.equal(html(<NodeDetailPanel state={state} hostId="ghost" onClose={() => {}} />), '')
})

test('the alerts panel lists alerts or says there are none', () => {
  assert.match(html(<AlertsPanel state={state} />), /href="\/alerts\/evt-000001"/)
  assert.match(html(<AlertsPanel state={state} />), /Workstation A sent a packet/)
  assert.match(html(<AlertsPanel state={{ ...state, alerts: [] }} />), /No alerts yet/)
})

test('the timeline strip has a mark per alert and a forecast marker', () => {
  const out = html(<TimelineStrip alerts={[alert]} forecast={state.forecast} />)
  assert.match(out, /1 alerts on the timeline/)
  assert.match(out, /data-severity="HIGH"/)
  assert.match(out, /A forecast was made/)
  assert.match(out, /class="c-timeline-track" aria-hidden="true">.*class="c-mark"/s)
  assert.match(html(<TimelineStrip alerts={[]} forecast={null} />), /Timeline populates as the simulation runs/)
})

test('the scene summary is text for screen readers', () => {
  assert.match(html(<SceneSummary state={state} />), /2 hosts\. 1 compromised: Workstation A\. 1 forecast: Web Server B 74 %\./)
})

test('charts show an empty state instead of an empty frame', () => {
  assert.match(html(<ForecastAccuracyChart metrics={{ calibration_bins: [] }} />), /No forecasts resolved yet/)
  assert.match(html(<AlertVolumeChart alerts={[]} />), /No alerts yet/)
})

test('charts with data draw a canvas with a text summary for screen readers', () => {
  const bins = { calibration_bins: [{ bin_low: 0.7, bin_high: 0.8, mean_confidence: 0.74, observed_rate: 1, count: 1 }] }
  assert.match(html(<ForecastAccuracyChart metrics={bins} />), /<canvas[^>]*aria-label="Calibration: stated 74 %, observed 100 %/)
  assert.match(html(<AlertVolumeChart alerts={[alert]} />), /<canvas[^>]*aria-label="1 alerts over 1 minute/)
})

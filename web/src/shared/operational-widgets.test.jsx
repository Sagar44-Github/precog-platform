import test from 'node:test'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { AccuracyCounter, AttackPath2D, ForecastBars, OutcomeCard, SeverityBadge, StateChip } from './operational-widgets.jsx'

const state = {
  graph: { hosts: [{ host_id: 'host-a', name: 'Workstation A', state: 'compromised' }, { host_id: 'server-b', name: 'Web Server B', state: 'normal' }], compromised_path: ['host-a'] },
  forecast: { status: 'pending', targets: [{ rank: 1, host_id: 'server-b', confidence: 0.74 }], technique_hint: { technique_name: 'Remote Services' } },
  metrics: { forecasts_resolved: 1, hits: 1, hit_rate: 1 },
}
const html = (element) => renderToStaticMarkup(element)

test('severity and host badges include readable state text with semantic classes', () => {
  assert.match(html(<SeverityBadge severity="HIGH" />), /soc-severity-high[^>]*><span aria-hidden="true">▲<\/span>High/)
  assert.match(html(<StateChip state="contained" />), /soc-host-contained[^>]*>.*Contained/)
})

test('forecast list explains its estimate and shows target names and probabilities', () => {
  const out = html(<ForecastBars state={state} />)
  assert.match(out, /Precog predicts the next target/)
  assert.match(out, /Web Server B/)
  assert.match(out, /74%/)
  assert.match(out, /Likely next technique: Remote Services/)
  assert.doesNotMatch(out, /will /)
  assert.match(html(<ForecastBars state={{ ...state, forecast: null }} />), /No forecast right now/)
})

test('accuracy counter labels its values as session-only', () => {
  const out = html(<AccuracyCounter metrics={state.metrics} />)
  assert.match(out, /1 \/ 1 \(100 %\)/)
  assert.match(out, /Session counter, not the model’s overall accuracy/)
})

test('attack path states compromised and forecast hosts', () => {
  const out = html(<AttackPath2D state={state} />)
  assert.match(out, /Workstation A/)
  assert.match(out, /Web Server B predicted, 74%/)
})

test('misses are explicit and pending forecasts do not show an outcome', () => {
  const miss = { status: 'miss', outcome: { attempted_host: 'server-b', rank_hit: null, blocked: false } }
  assert.match(html(<OutcomeCard forecast={miss} state={state} />), /Precog missed\. The attacker went to Web Server B instead\./)
  assert.equal(html(<OutcomeCard forecast={state.forecast} state={state} />), '')
})

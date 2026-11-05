import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { Button, PageFrame, PageHeader, ResourceNotice, useResource } from './shared.jsx'
import './forecast-analytics.css'

function percent(value, digits = 1) {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(digits)}%`
}

function CalibrationPlot({ bins }) {
  const left = 34
  const top = 12
  const size = 144
  const points = bins.map((bin) => ({
    x: left + bin.mean_confidence * size,
    y: top + (1 - bin.observed_rate) * size,
    label: `${(bin.mean_confidence * 100).toFixed(1)}% stated, ${(bin.observed_rate * 100).toFixed(1)}% observed, ${bin.count} predictions`,
  }))
  return <div className="calibration-chart">
    <svg viewBox="0 0 214 188" role="img" aria-label="Calibration curve: stated confidence compared with observed hit rate">
      <line className="calibration-axis" x1={left} y1={top + size} x2={left + size} y2={top + size} />
      <line className="calibration-axis" x1={left} y1={top} x2={left} y2={top + size} />
      <line className="calibration-reference" x1={left} y1={top + size} x2={left + size} y2={top} />
      {[0, 0.5, 1].map((value) => <g key={value}>
        <text className="calibration-tick" x={left + value * size} y={top + size + 15} textAnchor="middle">{Math.round(value * 100)}%</text>
        <text className="calibration-tick" x={left - 7} y={top + (1 - value) * size + 3} textAnchor="end">{Math.round(value * 100)}%</text>
      </g>)}
      {points.map((point, index) => <circle className="calibration-point" key={index} cx={point.x} cy={point.y} r="4"><title>{point.label}</title></circle>)}
      <text className="calibration-axis-label" x={left + size / 2} y="185" textAnchor="middle">Stated confidence</text>
      <text className="calibration-axis-label" x="9" y={top + size / 2} transform={`rotate(-90 9 ${top + size / 2})`} textAnchor="middle">Observed hit rate</text>
    </svg>
    <div className="calibration-legend"><span><i className="calibration-legend-point" /> Markov model</span><span><i className="calibration-legend-line" /> Perfect calibration</span></div>
  </div>
}

function TallyCell({ tally }) {
  return <><strong>{percent(tally.precision_at_1)}</strong><span>{tally.rank1_hits} rank-one hits</span></>
}

export default function AnalyticsPage() {
  const [revision, setRevision] = useState(0)
  const load = useCallback(() => api.analytics(), [revision])
  const { data, loading, error, refresh } = useResource(load, 'precog-analytics')
  useEffect(() => {
    const timer = window.setInterval(() => setRevision((value) => value + 1), 1500)
    return () => window.clearInterval(timer)
  }, [])
  return <PageFrame className="forecast-page analytics-page">
    <PageHeader eyebrow="PRECOG / MODEL EVALUATION" title="Analytics" description="Held-out model evaluation, calibration, baselines, and current replay counters are reported in separate sections." actions={<><Link className="ops-button ops-button-secondary" to="/forecasts">Open forecast ledger</Link><Button className="ops-button-secondary" type="button" onClick={() => { refresh(); setRevision((value) => value + 1) }}>Refresh metrics</Button></>} />
    <ResourceNotice loading={loading} error={error} data={data} onRetry={refresh} />
    {data && <>
      <section className="analytics-scope-note"><span className="ops-eyebrow">EVALUATION SCOPE</span><p>{data.evaluation.source}</p><span>{data.evaluation.training_sequences} training routes · {data.evaluation.test_sequences} held-out routes · smoothing α {data.evaluation.alpha}</span></section>

      <section className="analytics-section" aria-labelledby="heldout-title">
        <div className="analytics-section-heading"><div><p className="ops-eyebrow">OFFLINE HELD-OUT EVALUATION</p><h3 id="heldout-title">Model and baseline results</h3></div><span className="analytics-scope-tag">NOT GOLDEN PATH COUNTS</span></div>
        <div className="ops-stat-grid analytics-stat-grid">
          <div className="ops-stat"><span>Forecasts evaluated</span><strong>{data.evaluation.node_model.forecasts}</strong></div>
          <div className="ops-stat"><span>Markov precision@1</span><strong>{percent(data.evaluation.node_model.precision_at_1)}</strong><small>± {percent(data.evaluation.node_model.precision_at_1_std_error)} standard error</small></div>
          <div className="ops-stat"><span>Markov precision@3</span><strong>{percent(data.evaluation.node_model.precision_at_3)}</strong></div>
          <div className="ops-stat"><span>Expected calibration error</span><strong>{percent(data.evaluation.node_model.expected_calibration_error, 2)}</strong></div>
        </div>
        <div className="analytics-results-grid">
          <article className="ops-card"><div className="ops-card-header"><div><h3>Top-rank comparison</h3><p>Higher precision@1 means the first ranked host matched more often.</p></div></div><div className="ops-table-wrap"><table className="ops-table analytics-baseline-table"><thead><tr><th>Method</th><th>Precision@1</th><th>Standard error</th><th>Precision@3</th><th>Calibration error</th></tr></thead><tbody>
            <tr><td>Markov model</td><td>{percent(data.evaluation.node_model.precision_at_1)}</td><td>{percent(data.evaluation.node_model.precision_at_1_std_error, 2)}</td><td>{percent(data.evaluation.node_model.precision_at_3)}</td><td>{percent(data.evaluation.node_model.expected_calibration_error, 2)}</td></tr>
            {data.evaluation.baselines.map((baseline) => <tr key={baseline.name}><td>{baseline.name}</td><td>{percent(baseline.metrics.precision_at_1)}</td><td>{percent(baseline.metrics.precision_at_1_std_error, 2)}</td><td>{percent(baseline.metrics.precision_at_3)}</td><td>{percent(baseline.metrics.expected_calibration_error, 2)}</td></tr>)}
          </tbody></table></div></article>
          <article className="ops-card"><div className="ops-card-header"><div><h3>Calibration curve</h3><p>Each dot compares stated confidence with observed hit rate.</p></div></div><div className="ops-card-body"><CalibrationPlot bins={data.evaluation.calibration_bins} /></div></article>
        </div>
        <div className="forecast-honesty-note analytics-honesty-list">{data.honesty_notes.slice(0, 3).map((note) => <p key={note}>{note}</p>)}</div>
      </section>

      <section className="analytics-section" aria-labelledby="session-title">
        <div className="analytics-section-heading"><div><p className="ops-eyebrow">CURRENT AND ARCHIVED REPLAYS</p><h3 id="session-title">Session counters</h3></div><Link className="ops-text-link" to="/reports">Open session reports</Link></div>
        <p className="analytics-session-label">Session counter, not the model's overall accuracy.</p>
        <article className="ops-card"><div className="ops-card-header"><div><h3>Live model-versus-baseline tally</h3><p>{data.live_tally.forecasts_resolved} resolved forecasts in the bounded replay archive</p></div></div><div className="ops-table-wrap"><table className="ops-table analytics-tally-table"><thead><tr><th>Ranking method</th><th>Session precision@1</th></tr></thead><tbody>
          <tr><td>Markov model</td><td><TallyCell tally={data.live_tally.model} /></td></tr>
          <tr><td>Rule-based</td><td><TallyCell tally={data.live_tally.rule_based} /></td></tr>
          <tr><td>Uniform</td><td><TallyCell tally={data.live_tally.uniform} /></td></tr>
        </tbody></table></div></article>
        <article className="ops-card analytics-session-calibration"><div className="ops-card-header"><div><h3>Current session calibration bins</h3><p>These counts update from observed replay outcomes.</p></div></div>{data.session.calibration_bins.length ? <div className="ops-table-wrap"><table className="ops-table"><thead><tr><th>Confidence range</th><th>Mean confidence</th><th>Observed rate</th><th>Predictions</th></tr></thead><tbody>{data.session.calibration_bins.map((bin) => <tr key={bin.bin_low}><td>{Math.round(bin.bin_low * 100)}–{Math.round(bin.bin_high * 100)}%</td><td>{percent(bin.mean_confidence)}</td><td>{percent(bin.observed_rate)}</td><td>{bin.count}</td></tr>)}</tbody></table></div> : <div className="analytics-empty">No resolved forecasts in the current session yet. Run a replay to populate these counters.</div>}</article>
      </section>

      <section className="analytics-section" aria-labelledby="detection-title">
        <div className="analytics-section-heading"><div><p className="ops-eyebrow">DETECT / OFFLINE REPORT</p><h3 id="detection-title">Detection model report</h3></div><span className="analytics-scope-tag">SEPARATE DATASET</span></div>
        {data.detection_report ? <article className="ops-card detection-report-card"><div className="ops-card-header"><div><h3>{data.detection_report.model}</h3><p>{data.detection_report.dataset} · {data.detection_report.split}</p></div></div><div className="ops-card-body"><div className="ops-stat-grid detection-stat-grid">
          <div className="ops-stat"><span>Precision</span><strong>{percent(data.detection_report.precision, 2)}</strong></div><div className="ops-stat"><span>Recall</span><strong>{percent(data.detection_report.recall, 2)}</strong></div><div className="ops-stat"><span>F1 score</span><strong>{percent(data.detection_report.f1, 2)}</strong></div><div className="ops-stat"><span>False positive rate</span><strong>{percent(data.detection_report.false_positive_rate, 2)}</strong></div>
        </div><p className="forecast-honesty-note">{data.detection_report.notes}</p></div></article> : <div className="analytics-empty">No offline detection report is loaded.</div>}
      </section>
    </>}
  </PageFrame>
}

import { useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { Button, EmptyMessage, PageFrame, PageHeader, ResourceNotice, Severity, SourceBadge, formatTime, useResource } from './shared.jsx'
import './incidents-reports.css'

function download(filename, content, type) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function csvCell(value) {
  let text = String(value ?? '')
  if (/^[\t\r =+\-@]/.test(text)) text = `'${text}`
  return `"${text.replaceAll('"', '""')}"`
}

export default function ReportDetailPage() {
  const { sessionId } = useParams()
  const load = useCallback(() => api.report(sessionId), [sessionId])
  const { data: report, loading, error, refresh } = useResource(load, sessionId)
  const title = report?.scenario_id || 'Replay session report'

  function exportJson() {
    if (report) download(`${report.session_id}-report.json`, JSON.stringify(report, null, 2), 'application/json')
  }
  function exportCsv() {
    if (!report) return
    const rows = [['kind', 'timestamp', 'reference', 'host', 'summary']]
    report.timeline.forEach((item) => rows.push([item.kind, item.ts, item.ref_id, item.host || '', item.label]))
    download(`${report.session_id}-timeline.csv`, rows.map((row) => row.map(csvCell).join(',')).join('\r\n'), 'text/csv;charset=utf-8')
  }

  return <PageFrame className="report-detail-page">
    <PageHeader eyebrow="REVIEW / PRINTABLE REPORT" title={title} description={report ? `Session ${report.session_id} · replay-only evidence from ${formatTime(report.started_at)}` : 'A printable record of one replay session.'} actions={<><Link to="/reports" className="ops-button ops-button-secondary report-no-print">Back to reports</Link><Button className="ops-button-secondary report-no-print" type="button" onClick={exportCsv} disabled={!report}>Export timeline CSV</Button><Button className="ops-button-secondary report-no-print" type="button" onClick={exportJson} disabled={!report}>Export JSON</Button><Button className="report-print-button report-no-print" type="button" onClick={() => window.print()} disabled={!report}>Print report</Button></>} />
    <ResourceNotice loading={loading} error={error} data={report} onRetry={refresh} />
    {report && <article className="report-print-root">
      <header className="report-document-header"><div><p className="ops-eyebrow">PRECOG SOC · SIMULATION REPORT</p><h2>{title}</h2><p className="ops-mono">{report.session_id}</p></div><div><span className="incident-simulation-tag">SIMULATED REPLAY</span><small>{report.ended_at ? `Completed ${formatTime(report.ended_at)}` : 'Session is still in progress'}</small></div></header>
      <section className="report-summary-grid" aria-label="Session summary">
        <div className="ops-stat"><span>Session severity</span><strong><Severity value={report.severity} /></strong></div>
        <div className="ops-stat"><span>Alerts recorded</span><strong>{report.alert_count}</strong></div>
        <div className="ops-stat"><span>Resolved forecasts</span><strong>{report.metrics.forecasts_resolved}</strong></div>
        <div className="ops-stat"><span>Top-three hits</span><strong>{report.metrics.precision_at_3 === null ? '—' : `${Math.round(report.metrics.precision_at_3 * 100)}%`}</strong></div>
      </section>
      <aside className="report-honesty-note"><b>Metric scope</b><p>{report.metrics.honesty_note}</p><p>These counts describe this replay session only. A forecast miss remains a miss in the report.</p></aside>
      <section className="ops-card report-section"><div className="ops-card-header"><div><h3>Replay timeline</h3><p>Detection, prediction, and simulated containment records in time order</p></div></div>
        {report.timeline.length ? <ol className="incident-timeline">{report.timeline.map((item, index) => <li className={`incident-timeline-item incident-kind-${item.kind}`} key={`${item.ref_id}-${item.kind}-${index}`}><span className="incident-timeline-marker" aria-hidden="true" /><div><span className="incident-kind-label">{item.kind}</span><b>{item.label}</b><small>{formatTime(item.ts)} · {item.ref_id}{item.host ? ` · ${item.host}` : ''}</small></div></li>)}</ol> : <div className="ops-card-body"><EmptyMessage title="No timeline entries">Events appear here as the replay processes its scripted scenario.</EmptyMessage></div>}
      </section>
      <section className="ops-card report-section"><div className="ops-card-header"><div><h3>Detection records</h3><p>Source and ATT&amp;CK labels are preserved from the event pipeline</p></div></div>
        {report.alerts.length ? <div className="ops-table-wrap" role="region" aria-label="Session alert details" tabIndex={0}><table className="ops-table"><thead><tr><th>Time</th><th>Severity</th><th>Host</th><th>Technique</th><th>Source</th><th>Explanation</th></tr></thead><tbody>{report.alerts.map((alert) => <tr key={alert.event_id}><td data-label="Time">{formatTime(alert.ts)}</td><td data-label="Severity"><Severity value={alert.severity} /></td><td data-label="Host" className="ops-mono">{alert.host}</td><td data-label="Technique">{alert.technique_id ? `${alert.technique_id} · ${alert.technique_name}` : '—'}</td><td data-label="Source"><SourceBadge value={alert.source} /></td><td data-label="Explanation">{alert.explanation}</td></tr>)}</tbody></table></div> : <div className="ops-card-body"><p className="muted">No detections recorded in this session.</p></div>}
      </section>
      <div className="report-evidence-grid">
        <section className="ops-card report-section"><div className="ops-card-header"><div><h3>Forecast outcomes</h3><p>Ranked predictions and observed results</p></div></div><div className="ops-card-body">{report.forecasts.length ? report.forecasts.map((forecast) => <article className="incident-ledger-row" key={forecast.forecast_id}><b>{forecast.forecast_id} · {forecast.status}</b><span>{forecast.targets.map((target) => `${target.rank}. ${target.host_id} (${Math.round(target.confidence * 100)}%)`).join(' · ') || 'No candidates'}</span><small>{forecast.outcome ? `Observed ${forecast.outcome.attempted_host}; ${forecast.outcome.rank_hit ? `rank ${forecast.outcome.rank_hit} hit` : 'miss'}${forecast.outcome.blocked ? ' · blocked' : ''}` : 'Pending outcome'}</small></article>) : <p className="muted">No forecasts recorded.</p>}</div></section>
        <section className="ops-card report-section"><div className="ops-card-header"><div><h3>Simulated response actions</h3><p>Proposed and confirmed containment records</p></div></div><div className="ops-card-body">{report.actions.length ? report.actions.map((action) => <article className="incident-ledger-row" key={action.action_id}><b>{action.target_host} · {action.status}</b><span>{action.action_id}</span><small>{action.result || `Proposed ${formatTime(action.proposed_at)}`}</small></article>) : <p className="muted">No actions recorded.</p>}</div></section>
      </div>
      <footer className="report-document-footer">Replay-only demonstration. Containment changes in-memory demo state and does not affect a real network.</footer>
    </article>}
  </PageFrame>
}

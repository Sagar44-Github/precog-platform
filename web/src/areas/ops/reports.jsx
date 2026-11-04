import { useCallback } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { Button, EmptyMessage, PageFrame, PageHeader, ResourceNotice, Severity, formatTime, useResource } from './shared.jsx'
import './incidents-reports.css'

export default function ReportsPage() {
  const load = useCallback(() => api.reports(), [])
  const { data, loading, error, refresh } = useResource(load, 'reports')
  return <PageFrame className="reports-page">
    <PageHeader eyebrow="REVIEW / REPLAY RECORDS" title="Session reports" description="Printable, exportable summaries of each replay, with the session timeline, prediction outcomes, simulated actions, and honest per-session counters." actions={<Button className="ops-button-secondary" type="button" onClick={refresh}>Refresh reports</Button>} />
    <ResourceNotice loading={loading} error={error} data={data} onRetry={refresh} />
    {data && <section className="report-index" aria-label="Replay session reports">
      {data.items.length ? data.items.map((report) => <article className="report-index-card ops-card" key={report.session_id}>
        <div className="report-index-mark" aria-hidden="true"><span /></div>
        <div className="report-index-main"><p className="ops-eyebrow">{report.ended_at ? 'COMPLETED SESSION' : 'CURRENT SESSION'}</p><h3>{report.scenario_id || 'Replay session'}</h3><p className="report-index-meta"><span className="ops-mono">{report.session_id}</span><span>{formatTime(report.started_at)}</span></p></div>
        <div className="report-index-stat"><span>Alerts</span><b>{report.alert_count}</b><Severity value={report.severity} /></div>
        <div className="report-index-stat"><span>Resolved forecasts</span><b>{report.forecasts_resolved}</b><small>{report.hit_rate === null ? 'No outcomes yet' : `${Math.round(report.hit_rate * 100)}% session hit rate`}</small></div>
        <Link className="ops-button ops-button-secondary report-open-link" to={`/reports/${encodeURIComponent(report.session_id)}`}>Open report <span aria-hidden="true">↗</span></Link>
      </article>) : <div className="ops-card"><EmptyMessage title="No replay sessions yet">Start a deterministic replay to create the first session report.</EmptyMessage></div>}
    </section>}
    <aside className="report-integrity-note"><b>Reading these counters</b><p>They summarize resolved forecasts in one session. They are not overall model accuracy; precision@3 may be trivial when only three or fewer hosts are reachable.</p></aside>
  </PageFrame>
}

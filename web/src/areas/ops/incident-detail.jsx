import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { Button, EmptyMessage, PageFrame, PageHeader, ResourceNotice, Severity, SourceBadge, formatTime, useResource } from './shared.jsx'
import './incidents-reports.css'

export default function IncidentDetailPage() {
  const { incidentId } = useParams()
  const [revision, setRevision] = useState(0)
  const [note, setNote] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const load = useCallback(() => api.incident(incidentId), [incidentId, revision])
  const { data, loading, error, refresh } = useResource(load, incidentId)

  async function addNote(event) {
    event.preventDefault()
    if (!note.trim()) return
    setSaving(true)
    setMessage('')
    try {
      await api.addIncidentNote(incidentId, note.trim())
      setNote('')
      setMessage('Analyst note added to this simulated case.')
      setRevision((value) => value + 1)
    } catch (reason) {
      setMessage(reason.message || 'Could not save the note.')
    } finally { setSaving(false) }
  }

  async function updateStatus(status) {
    setSaving(true)
    setMessage('')
    try {
      await api.setIncidentStatus(incidentId, status)
      setMessage(`Incident status updated to ${status}.`)
      setRevision((value) => value + 1)
    } catch (reason) {
      setMessage(reason.message || 'Could not update incident status.')
    } finally { setSaving(false) }
  }

  const incident = data
  return <PageFrame className="incident-detail-page">
    <PageHeader eyebrow="RESPONSE / CASE EVIDENCE" title={incident?.title || 'Incident detail'} description={incident?.summary || 'Review a replay-session case and its supporting evidence.'} actions={<Link to="/incidents" className="ops-button ops-button-secondary">Back to incidents</Link>} />
    <ResourceNotice loading={loading} error={error} data={data} onRetry={refresh} />
    {incident && <>
      <div className="ops-stat-grid incident-stat-grid">
        <div className="ops-stat"><span>Case status</span><strong><span className={`incident-status incident-status-${incident.status}`}>{incident.status}</span></strong></div>
        <div className="ops-stat"><span>Highest severity</span><strong><Severity value={incident.severity} /></strong></div>
        <div className="ops-stat"><span>Alerts</span><strong>{incident.alert_count}</strong></div>
        <div className="ops-stat"><span>Hosts observed</span><strong>{incident.hosts.length}</strong></div>
      </div>
      <div className="incident-action-bar ops-card">
        <div><b>Analyst case status</b><span>Changes are recorded in the demo audit log.</span></div>
        <label className="ops-field"><span>Status</span><select value={incident.status} onChange={(event) => updateStatus(event.target.value)} disabled={saving} aria-label="Incident status"><option value="open">Open</option><option value="contained">Contained</option><option value="closed">Closed</option></select></label>
      </div>
      {message && <p className="incident-feedback" role="status">{message}</p>}
      <div className="incident-detail-columns">
        <div className="incident-evidence-column">
          <section className="ops-card"><div className="ops-card-header"><div><h3>Session timeline</h3><p>Observed alerts, predicted targets, and simulated response actions</p></div></div>
            {incident.timeline.length ? <ol className="incident-timeline">{incident.timeline.map((item, index) => <li className={`incident-timeline-item incident-kind-${item.kind}`} key={`${item.ref_id}-${item.kind}-${index}`}>
              <span className="incident-timeline-marker" aria-hidden="true" />
              <div><span className="incident-kind-label">{item.kind}</span><b>{item.label}</b><small>{formatTime(item.ts)} · {item.ref_id}{item.host ? ` · ${item.host}` : ''}</small></div>
            </li>)}</ol> : <div className="ops-card-body"><EmptyMessage title="No timeline evidence yet">The case will collect session events as the replay runs.</EmptyMessage></div>}
          </section>
          <section className="ops-card"><div className="ops-card-header"><div><h3>Detection evidence</h3><p>Alert records associated with session {incident.session_id}</p></div></div>
            {incident.alerts.length ? <div className="ops-table-wrap"><table className="ops-table"><thead><tr><th>Observed</th><th>Severity</th><th>Host</th><th>Technique</th><th>Source</th></tr></thead><tbody>{incident.alerts.map((alert) => <tr key={alert.event_id}>
              <td data-label="Observed">{formatTime(alert.ts)}</td><td data-label="Severity"><Severity value={alert.severity} /></td>
              <td data-label="Host"><Link className="ops-text-link ops-mono" to={`/hosts/${encodeURIComponent(alert.host)}`}>{alert.host}</Link></td>
              <td data-label="Technique">{alert.technique_id ? `${alert.technique_id} · ${alert.technique_name}` : '—'}</td><td data-label="Source"><SourceBadge value={alert.source} /></td>
            </tr>)}</tbody></table></div> : <div className="ops-card-body"><EmptyMessage title="No alert evidence">This replay has not recorded a detection alert.</EmptyMessage></div>}
          </section>
          <section className="ops-card"><div className="ops-card-header"><div><h3>Forecast and action ledger</h3><p>Predictions and two-step containment records for this session</p></div></div><div className="ops-card-body incident-ledgers">
            <div><h4>Predictions</h4>{incident.forecasts.length ? incident.forecasts.map((forecast) => <article className="incident-ledger-row" key={forecast.forecast_id}><b>{forecast.forecast_id} <span className={`incident-forecast-state forecast-${forecast.status}`}>{forecast.status}</span></b><span>{forecast.targets.map((target) => `${target.rank}. ${target.host_id} (${Math.round(target.confidence * 100)}%)`).join(' · ') || 'No candidates'}</span><small>{forecast.outcome ? `Observed ${forecast.outcome.attempted_host}; ${forecast.outcome.rank_hit ? `rank ${forecast.outcome.rank_hit} hit` : 'not in top three'}${forecast.outcome.blocked ? ' · blocked by simulated containment' : ''}` : 'Pending outcome'}</small></article>) : <p className="muted">No forecasts recorded.</p>}</div>
            <div><h4>Simulated actions</h4>{incident.actions.length ? incident.actions.map((action) => <article className="incident-ledger-row" key={action.action_id}><b>{action.target_host} · {action.status}</b><span>{action.action_id}</span><small>{action.result || `Requested ${formatTime(action.proposed_at)}`}</small></article>) : <p className="muted">No containment actions recorded.</p>}</div>
          </div></section>
        </div>
        <aside className="incident-side-column">
          <section className="ops-card"><div className="ops-card-header"><div><h3>Hosts referenced</h3><p>Observed alert/origin hosts and action targets</p></div></div><div className="ops-card-body incident-host-list">{incident.hosts.length ? incident.hosts.map((host) => <Link key={host} to={`/hosts/${encodeURIComponent(host)}`} className="incident-host-link">{host}<span>Asset detail ↗</span></Link>) : <p className="muted">No hosts recorded.</p>}</div></section>
          <section className="ops-card"><div className="ops-card-header"><div><h3>ATT&amp;CK techniques</h3><p>Labels attached to scripted or detector events</p></div></div><div className="ops-card-body">{incident.techniques.length ? <ul className="incident-techniques">{incident.techniques.map((technique) => <li key={technique.technique_id}><b>{technique.technique_id}</b><span>{technique.technique_name}</span></li>)}</ul> : <p className="muted">No ATT&amp;CK labels were attached.</p>}</div></section>
          <section className="ops-card"><div className="ops-card-header"><div><h3>Analyst notes</h3><p>Notes stay in this running demo process</p></div></div><div className="ops-card-body">
            <form className="incident-note-form" onSubmit={addNote}><label className="ops-field"><span>Add a note</span><textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={2000} rows={4} placeholder="Record a review observation…" /></label><div><small>{note.length} / 2000</small><Button type="submit" disabled={saving || !note.trim()}>Add note</Button></div></form>
            {incident.notes.length ? <ol className="incident-notes">{[...incident.notes].reverse().map((item) => <li key={item.note_id}><p>{item.text}</p><small>{item.author} · {formatTime(item.created_at)}</small></li>)}</ol> : <p className="incident-no-notes">No analyst notes yet.</p>}
          </div></section>
        </aside>
      </div>
    </>}
  </PageFrame>
}

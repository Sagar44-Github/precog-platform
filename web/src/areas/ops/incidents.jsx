import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { Button, EmptyMessage, Field, FilterBar, PageFrame, PageHeader, ResourceNotice, SearchField, Severity, TableLink, formatTime, useResource } from './shared.jsx'
import './incidents-reports.css'

export default function IncidentsPage() {
  const [draft, setDraft] = useState({ q: '', status: '', severity: '' })
  const [applied, setApplied] = useState(draft)
  const [revision, setRevision] = useState(0)
  const load = useCallback(() => api.incidents({ ...applied, limit: 100 }), [applied, revision])
  const { data, loading, error, refresh } = useResource(load, JSON.stringify(applied))

  function apply(event) {
    event.preventDefault()
    setApplied({ ...draft })
  }

  function reset() {
    const empty = { q: '', status: '', severity: '' }
    setDraft(empty)
    setApplied(empty)
  }

  return <PageFrame className="incident-list-page">
    <PageHeader eyebrow="RESPONSE / SESSION CASES" title="Incidents" description="Replay sessions are grouped into incident cases so alert evidence, predicted targets, simulated actions, and analyst notes stay together." actions={<Button className="ops-button-secondary" type="button" onClick={() => { refresh(); setRevision((value) => value + 1) }}>Refresh cases</Button>} />
    <FilterBar className="ops-incident-filter" onSubmit={apply} onReset={reset}>
      <Field label="Search"><SearchField value={draft.q} onChange={(event) => setDraft({ ...draft, q: event.target.value })} placeholder="Scenario, host, technique…" /></Field>
      <Field label="Status"><select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}><option value="">All statuses</option><option value="open">Open</option><option value="contained">Contained</option><option value="closed">Closed</option></select></Field>
      <Field label="Highest severity"><select value={draft.severity} onChange={(event) => setDraft({ ...draft, severity: event.target.value })}><option value="">All severities</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option><option>NORMAL</option></select></Field>
    </FilterBar>
    <ResourceNotice loading={loading} error={error} data={data} onRetry={refresh} />
    {data && <section className="ops-card" aria-label="Incident cases">
      <div className="ops-card-header"><div><h3>Replay cases</h3><p>{data.total} incidents · grouped by session id</p></div><span className="incident-simulation-tag">SIMULATED ACTIVITY</span></div>
      {data.items.length ? <div className="ops-table-wrap"><table className="ops-table"><thead><tr><th>Incident</th><th>Status</th><th>Severity</th><th>Evidence</th><th>Hosts</th><th>Started</th></tr></thead><tbody>
        {data.items.map((incident) => <tr key={incident.incident_id}>
          <td data-label="Incident"><TableLink to={`/incidents/${encodeURIComponent(incident.incident_id)}`}>{incident.title}</TableLink><span className="cell-secondary cell-mono">{incident.incident_id} · {incident.session_id}</span></td>
          <td data-label="Status"><span className={`incident-status incident-status-${incident.status}`}>{incident.status}</span></td>
          <td data-label="Severity"><Severity value={incident.severity} /></td>
          <td data-label="Evidence">{incident.alert_count} alerts<span className="cell-secondary">{incident.forecasts.length} forecasts · {incident.actions.length} actions</span></td>
          <td data-label="Hosts">{incident.hosts.length} hosts referenced<span className="cell-secondary cell-mono">{incident.hosts.join(', ') || '—'}</span></td>
          <td data-label="Started"><span className="cell-secondary">{formatTime(incident.started_at)}</span></td>
        </tr>)}
      </tbody></table></div> : <EmptyMessage title="No incidents match these filters">Complete or start a replay to build a case from simulated alerts and response records.</EmptyMessage>}
    </section>}
    <p className="incident-honesty-note">Cases are replay-session groupings, not claims about real intrusions. Notes and status are held in memory for this running demo.</p>
  </PageFrame>
}

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, NavLink, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../shared/AuthContext.jsx'
import { apiGet, apiPost } from '../../shared/api.js'
import { Icon } from '../../shared/icons.jsx'
import { SimulationBadge } from '../../shared/components.jsx'
import { ThemeToggle } from '../../shared/theme-context.jsx'
import { durationLabel, incidentStats, savedFilterList, severityTone } from './logic.js'
import './incidents.css'

const FILTERS_KEY = 'precog.incident-filters.v1'

function storageRead(key, fallback) {
  try { return typeof window === 'undefined' ? fallback : window.localStorage.getItem(key) ?? fallback }
  catch { return fallback }
}

function useIncidentRefresh() {
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let alive = true
    let since = null
    const poll = async () => {
      try {
        const feed = await apiGet(`/api/x/feed${since === null ? '' : `?since=${since}`}`)
        if (!alive) return
        if (since !== null && feed.changed) setRevision((value) => value + 1)
        since = feed.revision
      } catch { /* page-level loaders show the data error; transient polling errors are quiet */ }
    }
    poll()
    const timer = window.setInterval(poll, 2500)
    return () => { alive = false; window.clearInterval(timer) }
  }, [])
  return revision
}

function Frame({ children }) {
  const { username, role, logout } = useAuth()
  const navigate = useNavigate()
  async function signOut() {
    try { await logout() } finally { navigate('/login', { replace: true }) }
  }
  return (
    <div className="incident-workbench">
      <aside className="incident-rail" aria-label="Workspace navigation">
        <Link to="/console" className="incident-brand"><span className="incident-brand-mark"><Icon name="shield" size={18} /></span><span>PRECOG <b>SOC</b><small>SIMULATION LAB</small></span></Link>
        <p className="incident-rail-label">INVESTIGATE</p>
        <nav className="incident-rail-nav" aria-label="Workspace">
          <NavLink to="/console"><Icon name="activity" /><span>Live console</span></NavLink>
          <NavLink to="/incidents"><Icon name="shield" /><span>Incidents</span></NavLink>
          <NavLink to="/mobile"><Icon name="smartphone" /><span>Mobile SOC</span></NavLink>
        </nav>
        <div className="incident-rail-bottom"><span className="incident-env-dot" />Scripted environment<br /><small>In-memory response only</small></div>
        <div className="incident-account"><span className="incident-avatar">{(username || 'A').slice(0, 1).toUpperCase()}</span><span><b>{username || 'Operator'}</b><small>{(role || 'viewer').toUpperCase()} ROLE</small></span><button type="button" onClick={signOut} aria-label="Sign out"><Icon name="logout" size={16} /></button></div>
      </aside>
      <div className="incident-main">
        <header className="incident-topbar">
          <div className="incident-crumb"><Link to="/console">Workspace</Link><Icon name="chevron" size={14} /><span>Incident response</span></div>
          <div className="incident-top-actions"><span className="incident-role">{(role || 'viewer').toUpperCase()}</span><ThemeToggle /><SimulationBadge /></div>
        </header>
        <main className="incident-content">{children}</main>
        <footer className="incident-footer"><span>PRECOG · CASE MANAGEMENT</span><span>Scripted replay evidence · simulated containment only</span></footer>
      </div>
    </div>
  )
}

function PageHeading({ eyebrow, title, description, actions }) {
  return <div className="incident-page-heading"><div><p className="incident-eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>{actions && <div className="incident-heading-actions">{actions}</div>}</div>
}

function ErrorNotice({ children }) {
  return <div className="incident-error" role="alert"><Icon name="activity" size={17} />{children}</div>
}

function EmptyCases() {
  return <div className="incident-empty"><div className="incident-empty-glyph"><Icon name="shield" size={25} /></div><h2>No incidents match these filters</h2><p>Clear a filter or run a scripted scenario to create an investigation timeline.</p><Link to="/console">Open replay console <Icon name="chevron" size={15} /></Link></div>
}

function IncidentList() {
  const revision = useIncidentRefresh()
  const [filters, setFilters] = useState(() => {
    try { return { status: '', severity: '', host: '', technique: '', ...JSON.parse(storageRead(FILTERS_KEY, '{}')) } } catch { return { status: '', severity: '', host: '', technique: '' } }
  })
  const [data, setData] = useState({ items: [], total: 0, next_cursor: null })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [saved, setSaved] = useState(() => savedFilterList(storageRead(`${FILTERS_KEY}.saved`, '[]')))
  const [cursor, setCursor] = useState(null)
  const query = useMemo(() => {
    const params = new URLSearchParams({ sort: 'updated_desc', limit: '25' })
    Object.entries(filters).forEach(([key, value]) => { if (value) params.set(key, value) })
    if (cursor) params.set('cursor', cursor)
    return params.toString()
  }, [filters, cursor])
  const load = useCallback(async () => {
    setLoading(true)
    try { setData(await apiGet(`/api/x/incidents?${query}`)); setError('') }
    catch (cause) { setError(cause.message || 'Unable to load incidents.') }
    finally { setLoading(false) }
  }, [query])
  useEffect(() => { load() }, [load, revision])
  function setFilter(key, value) { setCursor(null); setFilters((current) => ({ ...current, [key]: value })) }
  function saveCurrent() {
    const label = window.prompt('Name this saved filter')
    if (!label?.trim()) return
    const next = [...saved.filter((item) => item.label !== label.trim()), { label: label.trim(), filters }].slice(-8)
    setSaved(next); try { window.localStorage.setItem(`${FILTERS_KEY}.saved`, JSON.stringify(next)) } catch { /* Saved filters stay usable for this session. */ }
  }
  function applySaved(item) { setCursor(null); setFilters({ status: '', severity: '', host: '', technique: '', ...item.filters }) }
  const summary = incidentStats(data.items)
  return (
    <>
      <PageHeading eyebrow="CASE MANAGEMENT · LIVE REPLAY" title="Incident investigations" description="Related scripted alerts become one case with evidence, attack path, forecast outcome and analyst decisions." actions={<><Link to="/mobile/alerts" className="incident-button incident-button-quiet">Alert stream</Link><Link to="/console" className="incident-button incident-button-primary"><Icon name="play" size={15} /> Run a replay</Link></>} />
      <div className="incident-kpis" aria-label="Incident summary">
        <div><span>VISIBLE CASES</span><b>{data.total}</b><small>matching the current view</small></div>
        <div><span>HIGH SEVERITY</span><b>{summary.high}</b><small>requires analyst review</small></div>
        <div><span>OPEN</span><b>{summary.open}</b><small>awaiting disposition</small></div>
        <div><span>WITH FORECASTS</span><b>{summary.forecasted}</b><small>model estimate attached</small></div>
      </div>
      <section className="incident-filter-card" aria-label="Incident filters">
        <div className="incident-filter-title"><div><span className="incident-section-marker" />FILTER CASES</div><button type="button" className="incident-text-button" onClick={saveCurrent}>Save current filter</button></div>
        <div className="incident-filter-grid">
          <label>Status<select value={filters.status} onChange={(event) => setFilter('status', event.target.value)}><option value="">All statuses</option><option value="open">Open</option><option value="contained">Contained</option><option value="closed">Closed</option><option value="reopened">Reopened</option></select></label>
          <label>Severity<select value={filters.severity} onChange={(event) => setFilter('severity', event.target.value)}><option value="">All severities</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></select></label>
          <label>Host<input value={filters.host} onChange={(event) => setFilter('host', event.target.value)} placeholder="e.g. server-b" /></label>
          <label>Technique<input value={filters.technique} onChange={(event) => setFilter('technique', event.target.value)} placeholder="ID or technique name" /></label>
        </div>
        {!!saved.length && <div className="incident-saved-filters"><span>Saved:</span>{saved.map((item) => <button type="button" key={item.label} onClick={() => applySaved(item)}>{item.label}</button>)}</div>}
      </section>
      <div className="incident-list-heading"><h2>Case queue <span>{data.total.toString().padStart(2, '0')}</span></h2><button type="button" className="incident-text-button" onClick={() => { setCursor(null); setFilters({ status: '', severity: '', host: '', technique: '' }) }}>Clear filters</button></div>
      {error && <ErrorNotice>{error}</ErrorNotice>}
      {loading && !data.items.length ? <div className="incident-loading" aria-live="polite">Loading case records…</div> : data.items.length === 0 ? <EmptyCases /> : <div className="incident-case-list">
        {data.items.map((item) => <IncidentCard key={item.incident_id} item={item} />)}
      </div>}
      {data.next_cursor && <div className="incident-pagination"><button type="button" className="incident-button incident-button-quiet" onClick={() => setCursor(data.next_cursor)}>Load more cases</button></div>}
    </>
  )
}

function IncidentCard({ item }) {
  const path = item.attack_path?.length ? item.attack_path : item.affected_hosts
  return (
    <Link to={`/incidents/${encodeURIComponent(item.incident_id)}`} className="incident-case-card">
      <span className={`incident-severity-rail tone-${severityTone(item.severity)}`} />
      <div className="incident-case-main">
        <div className="incident-case-top"><span className="incident-case-id">{item.incident_id}</span><span className={`incident-status status-${item.status}`}>{item.status.replace('_', ' ')}</span><time>{item.updated_at?.replace('T', ' ').replace('Z', ' UTC')}</time></div>
        <h3>{item.title}</h3>
        <div className="incident-case-meta"><span className={`incident-severity-label tone-${severityTone(item.severity)}`}>{item.severity} SEVERITY</span><span>{item.alert_ids?.length || 0} alerts</span><span>{item.affected_hosts?.length || 0} hosts</span><span>{durationLabel(item.duration_seconds)}</span></div>
        <div className="incident-path-row"><span>PATH</span>{path.slice(0, 5).map((host, index) => <span className="incident-path-host" key={`${host}-${index}`}>{host}</span>)}</div>
      </div>
      <div className="incident-case-side"><span className="incident-forecast-chip">{item.forecast_outcome?.label ? item.forecast_outcome.label.toUpperCase() : item.forecasts?.length ? 'ESTIMATE ATTACHED' : 'NO FORECAST'}</span><Icon name="chevron" size={18} /></div>
    </Link>
  )
}

function IncidentDetail() {
  const { incidentId } = useParams()
  const { role } = useAuth()
  const navigate = useNavigate()
  const revision = useIncidentRefresh()
  const [incident, setIncident] = useState(null)
  const [timeline, setTimeline] = useState([])
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const canAnnotate = role === 'analyst' || role === 'admin'
  const load = useCallback(async () => {
    try {
      const [record, events] = await Promise.all([
        apiGet(`/api/x/incidents/${encodeURIComponent(incidentId)}`),
        apiGet(`/api/x/incidents/${encodeURIComponent(incidentId)}/timeline`),
      ])
      setIncident(record); setTimeline(events); setError('')
    } catch (cause) { setError(cause.message || 'Unable to load this incident.') }
  }, [incidentId])
  useEffect(() => { load() }, [load, revision])
  async function addNote(event) {
    event.preventDefault()
    if (!note.trim()) return
    setBusy(true); setError('')
    try { await apiPost(`/api/x/incidents/${encodeURIComponent(incidentId)}/notes`, { body: note }); setNote(''); await load() }
    catch (cause) { setError(cause.message || 'The note could not be saved.') }
    finally { setBusy(false) }
  }
  async function changeStatus(status) {
    const verb = status === 'closed' ? 'close' : 'reopen'
    const reason = window.prompt(`Reason to ${verb} ${incidentId}`)
    if (!reason?.trim()) return
    if (!window.confirm(`${verb === 'close' ? 'Close' : 'Reopen'} this incident? This decision is recorded in the audit log.`)) return
    setBusy(true); setError('')
    try { await apiPost(`/api/x/incidents/${encodeURIComponent(incidentId)}/status`, { status, reason, confirm: true }); await load() }
    catch (cause) { setError(cause.message || 'The status change failed.') }
    finally { setBusy(false) }
  }
  if (!incident && !error) return <div className="incident-loading" aria-live="polite">Loading investigation…</div>
  if (!incident) return <><Link className="incident-back" to="/incidents">← All incidents</Link><ErrorNotice>{error}</ErrorNotice></>
  const path = incident.attack_path?.length ? incident.attack_path : incident.affected_hosts
  return (
    <>
      <div className="incident-detail-backbar"><button type="button" onClick={() => navigate('/incidents')}>← All incidents</button><span> / {incident.incident_id}</span><div><a className="incident-button incident-button-quiet" href={`/api/x/incidents/${encodeURIComponent(incidentId)}/export?format=markdown`}>Export Markdown</a><a className="incident-button incident-button-quiet" href={`/api/x/incidents/${encodeURIComponent(incidentId)}/export`}>Export JSON</a></div></div>
      {error && <ErrorNotice>{error}</ErrorNotice>}
      <PageHeading eyebrow={`INCIDENT ${incident.incident_id} · ${incident.scenario_id || 'REPLAY'}`} title={incident.title} description="Investigation record assembled from scripted detections, the replay graph and simulated response history." actions={<span className={`incident-status status-${incident.status}`}>{incident.status.toUpperCase()}</span>} />
      <div className="incident-detail-grid">
        <section className="incident-panel incident-summary-panel">
          <div className="incident-panel-head"><div><p className="incident-eyebrow">CASE SUMMARY</p><h2>At a glance</h2></div><span className={`incident-severity-label tone-${severityTone(incident.severity)}`}>{incident.severity}</span></div>
          <div className="incident-summary-stats"><div><b>{incident.alert_ids.length}</b><span>alerts</span></div><div><b>{incident.affected_hosts.length}</b><span>affected hosts</span></div><div><b>{incident.forecasts.length}</b><span>forecasts</span></div><div><b>{durationLabel(incident.duration_seconds)}</b><span>duration</span></div></div>
          <div className="incident-summary-row"><span>Opened</span><time>{incident.created_at?.replace('T', ' ').replace('Z', ' UTC')}</time></div>
          <div className="incident-summary-row"><span>Techniques</span><span>{incident.techniques.map((item) => item.technique_id).join(', ') || '—'}</span></div>
          {incident.containment_basis && <p className="incident-basis"><b>Contained in simulation:</b> {incident.containment_basis}</p>}
          {incident.compromised_hosts?.length > 0 && <div className="incident-host-list"><span>COMPROMISED HOSTS</span>{incident.compromised_hosts.map((host) => <Link key={host} to={`/console?host=${encodeURIComponent(host)}`}>{host}</Link>)}</div>}
          {canAnnotate && <div className="incident-status-controls">{incident.status !== 'closed' ? <button type="button" disabled={busy} onClick={() => changeStatus('closed')}>Close with reason</button> : <button type="button" disabled={busy} onClick={() => changeStatus('reopened')}>Reopen with reason</button>}</div>}
          {!canAnnotate && <p className="incident-readonly">Viewer access is read-only. Ask an analyst to add notes or change case status.</p>}
        </section>
        <section className="incident-panel incident-path-panel">
          <div className="incident-panel-head"><div><p className="incident-eyebrow">ATTACK PATH · 2D VIEW</p><h2>Hosts in this case</h2></div><Link to="/console">Open network twin <Icon name="chevron" size={14} /></Link></div>
          <div className="incident-path-visual" aria-label={`Incident host path: ${path.join(' to ')}`}>
            {path.map((host, index) => <div className="incident-path-stop" key={`${host}-${index}`}><Link to={`/console?host=${encodeURIComponent(host)}`} className={incident.compromised_hosts?.includes(host) ? 'is-compromised' : ''}><span>{String(index + 1).padStart(2, '0')}</span><b>{host}</b><small>{incident.compromised_hosts?.includes(host) ? 'COMPROMISED' : 'OBSERVED'}</small></Link>{index < path.length - 1 && <i aria-hidden="true" />}</div>)}
            {!path.length && <p>No host path has been recorded yet.</p>}
          </div>
          <p className="incident-sim-note">Path is reconstructed from this replay’s graph events. It represents the six-host demo network.</p>
        </section>
        <section className="incident-panel incident-timeline-panel">
          <div className="incident-panel-head"><div><p className="incident-eyebrow">CHRONOLOGICAL EVIDENCE</p><h2>Investigation timeline</h2></div><span>{timeline.length} events</span></div>
          <ol className="incident-timeline">{timeline.map((item) => <li key={item.event_id} className={`timeline-${item.type}`}><span className="incident-timeline-dot" /><div><div className="incident-timeline-meta"><b>{item.type.replaceAll('_', ' ')}</b><time>{item.timestamp?.replace('T', ' ').replace('Z', ' UTC')}</time></div><p>{item.summary}</p>{item.ref_id && <Link to={item.type === 'alert' || item.type === 'technique' || item.type === 'compromise' ? `/mobile/alerts/${encodeURIComponent(item.ref_id)}` : `/mobile/forecast`}>Open evidence <Icon name="chevron" size={12} /></Link>}{item.actor && <small>{item.actor} · {item.role}</small>}</div></li>)}</ol>
        </section>
        <div className="incident-detail-stack">
          <section className="incident-panel incident-evidence-panel"><div className="incident-panel-head"><div><p className="incident-eyebrow">DETECTION RECORDS</p><h2>Evidence <span>{incident.evidence.length}</span></h2></div></div><div className="incident-evidence-list">{incident.evidence.map((item) => <Link key={item.event_id} to={`/mobile/alerts/${encodeURIComponent(item.event_id)}`}><span className={`incident-evidence-marker tone-${severityTone(item.severity)}`} /><span><b>{item.technique_name || item.technique_id}</b><small>{item.host} · {item.event_id}</small></span><span>{item.severity}</span><Icon name="chevron" size={15} /></Link>)}</div></section>
          <section className="incident-panel incident-forecast-panel"><div className="incident-panel-head"><div><p className="incident-eyebrow">PRECOG · MODEL ESTIMATE</p><h2>Forecast & response</h2></div></div>{incident.forecast_outcome ? <div className="incident-outcome"><b>{incident.forecast_outcome.label?.toUpperCase()}</b><span>{incident.forecast_outcome.blocked ? 'Scripted move was blocked by a confirmed simulated action.' : 'Observed next move compared with the ranked estimate.'}</span></div> : <p className="incident-quiet-copy">{incident.forecasts.length ? 'An estimate was generated; its outcome is pending.' : 'No forecast was produced for this incident.'}</p>}{incident.forecasts.map((forecast) => <div className="incident-forecast-row" key={forecast.forecast_id}><span>{forecast.forecast_id} · {forecast.status}</span><div>{forecast.targets.map((target) => <b key={target.host_id}>{target.rank}. {target.host_id} <small>{Math.round(target.confidence * 100)}%</small></b>)}</div></div>)}{incident.actions.map((action) => <div className="incident-action-row" key={action.action_id}><span>SIMULATED CONTAINMENT</span><b>{action.target_host} · {action.status.replace('_', ' ')}</b><small>{action.result || 'No execution result recorded.'}</small></div>)}<p className="incident-sim-note">Forecasts are estimates from a scripted generator over six demo hosts, not a guarantee of real-world protection.</p></section>
        </div>
        <section className="incident-panel incident-notes-panel"><div className="incident-panel-head"><div><p className="incident-eyebrow">ANALYST WORKSPACE</p><h2>Case notes <span>{incident.notes.length}</span></h2></div><span>Audit logged</span></div><div className="incident-notes-list">{incident.notes.map((item) => <article key={item.note_id}><p>{item.body}</p><footer>{item.author} · {item.role} <time>{item.created_at?.replace('T', ' ').replace('Z', ' UTC')}</time></footer></article>)}{!incident.notes.length && <p className="incident-quiet-copy">No analyst notes yet. Record a concise observation for the next reviewer.</p>}</div>{canAnnotate && <form className="incident-note-form" onSubmit={addNote}><label htmlFor="incident-note">Add a plain-text note</label><textarea id="incident-note" maxLength={2000} value={note} onChange={(event) => setNote(event.target.value)} placeholder="What should the next analyst know?"/><div><small>{note.length} / 2000 characters · Text only</small><button className="incident-button incident-button-primary" type="submit" disabled={busy || !note.trim()}>Add note</button></div></form>}</section>
      </div>
      <p className="incident-disclaimer">SIMULATION · All activity, forecasts and containment actions on this screen come from scripted replay data. Containment changes only in-memory demo state.</p>
    </>
  )
}

export default function IncidentsApp() {
  return <Frame><Routes><Route index element={<IncidentList />} /><Route path=":incidentId" element={<IncidentDetail />} /><Route path="*" element={<IncidentList />} /></Routes></Frame>
}

import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { EmptyState, LoadingState, useToast } from '../../shared/components.jsx'
import { AlertVolumeChart, ForecastAccuracyChart } from '../charts/index.jsx'
import { usePushRegistration } from '../push/index.jsx'
import DemoStart from '../../shared/DemoStart.jsx'
import { AccuracyCounter, AlertCard, AttackPath2D, ContainFlow, ForecastBars, OutcomeCard, SeverityBadge, StateChip, ThreatLevelCard, mitreUrl } from './components.jsx'
import { filterAlerts, formatTime, hostName, hostState } from './logic.js'

// The phone screens (owner: GRAPH). Each screen receives the live world state as "state".

const needsState = (state) => (state ? null : <LoadingState />)

export function HomeScreen({ state, stale, canOperate = true }) {
  const toast = useToast()
  const navigate = useNavigate()
  if (!state) return needsState(state)
  const latest = state.alerts[0]
  return (
    <div className="m-screen">
      <ThreatLevelCard state={state} stale={stale} />
      {state.replay?.state === 'idle' && (canOperate ? <DemoStart className="demo-launch-mobile" hostCount={state.graph.hosts.length} /> : <p className="m-caption">Viewer access is read-only. Ask an analyst to start a replay.</p>)}
      <section className="m-card">
        <ForecastBars state={state} />
        {state.forecast && (canOperate ? <ContainFlow state={state} onDone={toast.show} /> : <p className="m-caption">Viewer access is read-only. An analyst can propose and confirm simulated containment.</p>)}
        {canOperate && <Link className="m-btn" to={`/containment?host=${encodeURIComponent(state.forecast?.targets?.[0]?.host_id || '')}&forecast=${encodeURIComponent(state.forecast?.forecast_id || '')}`}>Open governed response</Link>}
      </section>
      <section className="m-card">
        <h2>Latest alert</h2>
        {latest ? <AlertCard alert={latest} onOpen={(a) => navigate(`/mobile/alerts/${encodeURIComponent(a.event_id)}`)} /> : <EmptyState>No alerts yet. Start the replay to see activity.</EmptyState>}
      </section>
      <section className="m-card"><AccuracyCounter metrics={state.metrics} /></section>
      <PushPrimer />
    </div>
  )
}

export function AlertsScreen({ state }) {
  const [filter, setFilter] = useState('ALL')
  const navigate = useNavigate()
  if (!state) return needsState(state)
  const shown = filterAlerts(state.alerts, filter)
  return (
    <div className="m-screen">
      <h1 className="m-title">Alerts</h1>
      <div className="m-filters" role="group" aria-label="Filter by severity">
        {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map((key) => (
          <button type="button" key={key} className="m-btn m-filter" aria-pressed={filter === key} onClick={() => setFilter(key)}>{key === 'ALL' ? 'All' : key[0] + key.slice(1).toLowerCase()}</button>
        ))}
      </div>
      {shown.length === 0 ? <EmptyState>No alerts yet. Start the replay to see activity.</EmptyState>
        : shown.slice(0, 50).map((a) => <AlertCard key={a.event_id} alert={a} onOpen={() => navigate(`/mobile/alerts/${encodeURIComponent(a.event_id)}`)} />)}
    </div>
  )
}

export function IncidentsScreen() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let alive = true
    api.incidents({ limit: 100 }).then((reply) => { if (alive) { setItems(reply.items); setError('') } }).catch((reason) => { if (alive) setError(reason.message || 'Could not load incidents.') })
    return () => { alive = false }
  }, [revision])
  return <div className="m-screen m-incident-screen">
    <h1 className="m-title">Incident cases</h1>
    <p className="m-caption m-case-intro">Cases group each simulated replay session and its alerts, predictions, and response actions.</p>
    {items === null && !error && <LoadingState lines={3} />}
    {error && <div className="m-case-error" role="alert"><p>{error}</p><button type="button" className="m-btn" onClick={() => { setItems(null); setRevision((value) => value + 1) }}>Retry</button></div>}
    {items?.length === 0 && <EmptyState>No incident cases yet. Start a replay to create a simulated case.</EmptyState>}
    {items?.map((incident) => <Link className="m-card m-case-link" to={`/mobile/incidents/${encodeURIComponent(incident.incident_id)}`} key={incident.incident_id}>
      <div className="m-row"><span className={`m-case-status m-case-status-${incident.status}`}>{incident.status}</span><span className="m-case-severity">{incident.severity}</span></div>
      <b>{incident.title}</b>
      <span className="m-mono m-caption">{incident.incident_id}</span>
      <span>{incident.alert_count} alerts · {incident.hosts.length} hosts referenced</span>
      <span className="m-case-summary">{incident.summary}</span>
    </Link>)}
  </div>
}

export function IncidentDetailScreen() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [incident, setIncident] = useState(null)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let alive = true
    api.incident(id).then((record) => { if (alive) { setIncident(record); setError('') } }).catch((reason) => { if (alive) setError(reason.message || 'Could not load this case.') })
    return () => { alive = false }
  }, [id, revision])

  async function changeStatus(status) {
    setSaving(true)
    setError('')
    try {
      const record = await api.setIncidentStatus(id, status)
      setIncident(record)
    } catch (reason) { setError(reason.message || 'Could not update case status.') }
    finally { setSaving(false) }
  }

  async function addNote(event) {
    event.preventDefault()
    if (!note.trim()) return
    setSaving(true)
    setError('')
    try {
      await api.addIncidentNote(id, note.trim())
      setNote('')
      setRevision((value) => value + 1)
    } catch (reason) { setError(reason.message || 'Could not add the note.') }
    finally { setSaving(false) }
  }

  return <div className="m-screen m-incident-screen">
    <button type="button" className="m-back" onClick={() => navigate('/mobile/incidents')}>‹ Back to cases</button>
    {!incident && !error && <LoadingState lines={3} />}
    {error && <div className="m-case-error" role="alert"><p>{error}</p><button type="button" className="m-btn" onClick={() => { setIncident(null); setRevision((value) => value + 1) }}>Retry</button></div>}
    {incident && <>
      <div className="m-case-heading"><div className="m-row"><span className={`m-case-status m-case-status-${incident.status}`}>{incident.status}</span><span className="m-case-severity">{incident.severity}</span></div><h1 className="m-title">{incident.title}</h1><p className="m-case-summary">{incident.summary}</p><span className="m-mono m-caption">{incident.session_id} · {incident.incident_id}</span></div>
      <section className="m-card m-case-control"><h2>Case status</h2><label className="m-case-field"><span>Analyst status</span><select aria-label="Incident case status" value={incident.status} disabled={saving} onChange={(event) => changeStatus(event.target.value)}><option value="open">Open</option><option value="contained">Contained</option><option value="closed">Closed</option></select></label><p className="m-caption">Status changes are audit logged. Notes and status remain in this running demo.</p></section>
      <section className="m-card"><h2>Session timeline</h2>{incident.timeline.length ? <ol className="m-case-timeline">{incident.timeline.map((item, index) => <li key={`${item.ref_id}-${item.kind}-${index}`}><span className={`m-case-marker m-case-marker-${item.kind}`} aria-hidden="true" /><div><small>{item.kind} · {formatTime(item.ts)}</small><b>{item.label}</b><span className="m-mono m-caption">{item.ref_id}{item.host ? ` · ${item.host}` : ''}</span></div></li>)}</ol> : <EmptyState>No timeline events have been recorded.</EmptyState>}</section>
      <section className="m-card"><h2>Alerts</h2>{incident.alerts.length ? incident.alerts.map((alert) => <div className="m-case-evidence" key={alert.event_id}><div className="m-row"><SeverityBadge severity={alert.severity} /><span className="m-mono m-caption">{alert.host}</span></div><p>{alert.explanation}</p><span className="m-caption">{alert.technique_id ? `${alert.technique_id} · ${alert.technique_name} · ` : ''}{alert.source === 'scripted' ? 'Scripted scenario' : 'NIDS detector'}</span></div>) : <EmptyState>No alert evidence recorded.</EmptyState>}</section>
      <section className="m-card"><h2>Predictions and actions</h2>{incident.forecasts.length ? incident.forecasts.map((forecast) => <div className="m-case-evidence" key={forecast.forecast_id}><b>Forecast · {forecast.status}</b><p>{forecast.targets.map((target) => `${target.rank}. ${target.host_id} (${Math.round(target.confidence * 100)}%)`).join(' · ') || 'No candidates'}</p>{forecast.status === 'miss' && <strong>Precog missed this predicted target.</strong>}{forecast.status === 'hit' && <strong>Precog hit in this replay.</strong>}</div>) : <p className="m-caption">No forecasts yet.</p>}{incident.actions.map((action) => <div className="m-case-evidence" key={action.action_id}><b>Simulated containment · {action.status}</b><p>{action.target_host}</p><small>{action.result || action.proposed_at}</small></div>)}</section>
      <section className="m-card"><h2>Analyst notes</h2><form className="m-case-note-form" onSubmit={addNote}><label className="m-case-field"><span>Add a note</span><textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={2000} rows={4} placeholder="Record a review observation…" /></label><div className="m-row"><small>{note.length} / 2000</small><button type="submit" className="m-btn" disabled={saving || !note.trim()}>Add note</button></div></form>{incident.notes.length ? [...incident.notes].reverse().map((entry) => <article className="m-case-note" key={entry.note_id}><p>{entry.text}</p><small>{entry.author} · {formatTime(entry.created_at)}</small></article>) : <p className="m-caption">No analyst notes yet.</p>}</section>
    </>}
  </div>
}

export function AlertDetailScreen({ state }) {
  const { id } = useParams()
  const navigate = useNavigate()
  if (!state) return needsState(state)
  const alert = state.alerts.find((a) => a.event_id === id)
  if (!alert) return <div className="m-screen"><button type="button" className="m-back" onClick={() => navigate('/mobile/alerts')}>‹ Back</button><EmptyState>This alert is no longer in the list.</EmptyState></div>
  const link = mitreUrl(alert.technique_id)
  return (
    <div className="m-screen">
      <button type="button" className="m-back" onClick={() => navigate('/mobile/alerts')}>‹ Back</button>
      <div className="m-row"><SeverityBadge severity={alert.severity} /><span className="m-mono m-caption">{formatTime(alert.ts)}</span></div>
      <h1 className="m-title">{hostName(state, alert.host)}</h1>
      <p className="m-mono m-caption" style={{ margin: 0 }}>{alert.host} · <StateChip state={hostState(state, alert.host)} /></p>
      <section className="m-card"><h2>What happened</h2><p style={{ margin: 0 }}>{alert.explanation}</p></section>
      {alert.technique_id && (
        <section className="m-card"><h2>Attack technique</h2><p style={{ margin: 0 }}>{alert.technique_name} ({alert.technique_id})</p>
          <p style={{ margin: '8px 0 0' }}><a href={link} target="_blank" rel="noreferrer">Open MITRE page ↗</a></p></section>
      )}
      <section className="m-card"><h2>Where it is in the attack</h2><AttackPath2D state={state} /></section>
      <section className="m-card m-mono">Risk score {alert.risk_score} / 100<br />Source {alert.source === 'scripted' ? 'scripted' : 'NIDS detector'}</section>
    </div>
  )
}

export function ForecastScreen({ state, canOperate = true }) {
  const toast = useToast()
  if (!state) return needsState(state)
  return (
    <div className="m-screen">
      <h1 className="m-title">Forecast</h1>
      <section className="m-card">
        <ForecastBars state={state} />
        {state.forecast && (canOperate ? <ContainFlow state={state} onDone={toast.show} /> : <p className="m-caption">Viewer access is read-only. An analyst can propose and confirm simulated containment.</p>)}
        {canOperate && state.forecast && <Link className="m-btn" to={`/containment?host=${encodeURIComponent(state.forecast.targets[0]?.host_id || '')}&forecast=${encodeURIComponent(state.forecast.forecast_id)}`}>Open governed response</Link>}
      </section>
      <section className="m-card"><h2>Attack path</h2><AttackPath2D state={state} /></section>
      <LastOutcome />
    </div>
  )
}

function LastOutcome() {
  const [forecasts, setForecasts] = useState(null)
  const [state, setState] = useState(null)
  useEffect(() => {
    let alive = true
    Promise.all([api.forecasts(), api.state(null)]).then(([f, s]) => { if (alive) { setForecasts(f); setState(s) } }).catch(() => {})
    return () => { alive = false }
  }, [])
  if (!forecasts || !state) return null
  const last = [...forecasts].reverse().find((f) => f.status === 'hit' || f.status === 'miss')
  return last ? <OutcomeCard forecast={last} state={state} /> : null
}

export function HistoryScreen({ state }) {
  const [sessions, setSessions] = useState(null)
  const [report, setReport] = useState(undefined)
  useEffect(() => {
    let alive = true
    api.sessions().then((r) => alive && setSessions(r)).catch(() => alive && setSessions([]))
    fetch('/api/x/metrics/detection', { credentials: 'same-origin' }).then((r) => (r.ok ? r.json() : null)).then((r) => alive && setReport(r)).catch(() => alive && setReport(null))
    return () => { alive = false }
  }, [])
  if (!state) return needsState(state)
  return (
    <div className="m-screen">
      <h1 className="m-title">History</h1>
      <section className="m-card"><AccuracyCounter metrics={state.metrics} /><ForecastAccuracyChart metrics={state.metrics} /></section>
      <section className="m-card"><h2>Alert volume</h2><AlertVolumeChart alerts={state.alerts} /></section>
      <section className="m-card">
        <h2>Past sessions</h2>
        {sessions === null ? <LoadingState lines={2} /> : sessions.length === 0 ? <EmptyState>No past sessions yet.</EmptyState> : sessions.map((s) => (
          <p className="m-row" key={s.session_id} style={{ margin: '4px 0' }}><span>{s.scenario_id}</span><span className="m-mono m-caption">{s.forecasts.filter((f) => f.status === 'hit').length} / {s.forecasts.filter((f) => f.status === 'hit' || f.status === 'miss').length}</span></p>))}
      </section>
      <section className="m-card">
        <h2>Offline detection test</h2>
        {report === undefined ? <LoadingState lines={2} /> : report === null ? <EmptyState>No detection report yet.</EmptyState> : (
          <div>
            <p style={{ margin: 0 }}>{report.model}</p>
            <p className="m-mono">Precision {report.precision} · Recall {report.recall} · F1 {report.f1} · False-positive rate {report.false_positive_rate}</p>
            <p className="m-caption">{report.notes}</p>
          </div>)}
      </section>
      <section className="m-card"><h2>About this data</h2><p style={{ margin: 0 }} className="m-caption">All data in this app is simulated. To install the app, use your browser's Add to Home Screen.</p></section>
    </div>
  )
}

/** Shown once, before the browser's own permission box (UI/UX brief 8.8). VIZ provides usePushRegistration. */
export function PushPrimer() {
  const push = usePushRegistration()
  const [hidden, setHidden] = useState(() => { try { return window.localStorage.getItem('precog-push-primer') === 'no' } catch (e) { return false } })
  if (push.status !== 'prompt' || hidden) return null
  const dismiss = () => { try { window.localStorage.setItem('precog-push-primer', 'no') } catch (e) { /* storage may be blocked */ } setHidden(true) }
  return (
    <section className="m-card m-primer">
      <p style={{ margin: 0 }}>Get an alert when something serious happens. We only send high-risk alerts.</p>
      <div className="m-row"><button type="button" className="m-btn" onClick={() => push.enable && push.enable()}>Turn on alerts</button><button type="button" className="m-btn m-btn-text" onClick={dismiss}>Not now</button></div>
    </section>
  )
}


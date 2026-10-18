import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { EmptyState, LoadingState, useToast } from '../../shared/components.jsx'
import { AlertVolumeChart, ForecastAccuracyChart } from '../charts/index.jsx'
import { usePushRegistration } from '../push/index.jsx'
import { AccuracyCounter, AlertCard, AttackPath2D, ContainFlow, ForecastBars, OutcomeCard, SeverityBadge, StateChip, ThreatLevelCard, mitreUrl } from './components.jsx'
import { filterAlerts, formatTime, hostName, hostState } from './logic.js'

// The phone screens (owner: GRAPH). Each screen receives the live world state as "state".

const needsState = (state) => (state ? null : <LoadingState />)

export function HomeScreen({ state, stale }) {
  const toast = useToast()
  const navigate = useNavigate()
  if (!state) return needsState(state)
  const latest = state.alerts[0]
  return (
    <div className="m-screen">
      <ThreatLevelCard state={state} stale={stale} />
      <section className="m-card">
        <ForecastBars state={state} />
        {state.forecast && <ContainFlow state={state} onDone={toast.show} />}
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

export function ForecastScreen({ state }) {
  const toast = useToast()
  if (!state) return needsState(state)
  return (
    <div className="m-screen">
      <h1 className="m-title">Forecast</h1>
      <section className="m-card">
        <ForecastBars state={state} />
        {state.forecast && <ContainFlow state={state} onDone={toast.show} />}
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


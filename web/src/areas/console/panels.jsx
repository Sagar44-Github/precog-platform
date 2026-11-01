import { useEffect, useReducer, useState } from 'react'
import { api, apiGet } from '../../shared/api.js'
import { SimulationBadge } from '../../shared/components.jsx'
import { AccuracyCounter, AttackPath2D, ForecastBars, OutcomeCard, SeverityBadge, StateChip } from '../mobile/index.jsx'
import { AlertVolumeChart, ForecastAccuracyChart } from '../charts/index.jsx'
import { containReducer, formatTime, hostName, initialContain, replayButtons, replayWord, sceneSummary, SPEEDS, threatLevel, timelineMarks } from './logic.js'

// The console's panels (owner: VIZ). The phone components (SeverityBadge, StateChip, ForecastBars, OutcomeCard, AccuracyCounter,
// AttackPath2D) come from GRAPH's area through its entry file; VIZ never edits GRAPH's files.

export function ReplayControls({ replay, client = api }) {
  const [scenarios, setScenarios] = useState([])
  const [scenario, setScenario] = useState('golden-path')
  const [speed, setSpeed] = useState(1)
  const [problem, setProblem] = useState('')
  useEffect(() => { apiGet('/api/x/replay/scenarios').then(setScenarios).catch(() => setScenarios([])) }, [])
  const enabled = replayButtons(replay)
  const run = (call) => () => { setProblem(''); call().catch((e) => setProblem(e.message)) }
  const waiting = replay && replay.state === 'waiting_for_decision'
  return (
    <div className="c-replay" role="group" aria-label="Replay controls">
      <select aria-label="Scenario" value={scenario} onChange={(e) => setScenario(e.target.value)} disabled={!enabled.start}>
        {(scenarios.length ? scenarios : [{ scenario_id: 'golden-path' }]).map((s) => <option key={s.scenario_id} value={s.scenario_id}>{s.scenario_id}</option>)}
      </select>
      <button type="button" className="c-btn" disabled={!enabled.start} onClick={run(() => client.startReplay(scenario, speed))}>Start</button>
      <button type="button" className="c-btn" disabled={!enabled.pause} onClick={run(() => client.pauseReplay())}>Pause</button>
      <button type="button" className="c-btn" disabled={!enabled.resume} onClick={run(() => client.resumeReplay())}>Resume</button>
      <button type="button" className="c-btn" disabled={!enabled.restart} onClick={run(() => client.restartReplay())}>Restart</button>
      <select aria-label="Speed" value={speed} onChange={(e) => setSpeed(Number(e.target.value))} disabled={!enabled.start}>
        {SPEEDS.map((s) => <option key={s} value={s}>{s}×</option>)}
      </select>
      <span className={waiting ? 'c-replay-word c-waiting' : 'c-replay-word'}>{replayWord(replay)}</span>
      {problem && <span className="c-error" role="alert">{problem}</span>}
    </div>
  )
}

export function TopBar({ state, stale }) {
  const level = threatLevel(state)
  return (
    <header className="c-top">
      <strong>Precog SOC</strong>
      <SimulationBadge />
      {level && <span className="c-threat" style={{ color: level.color }} aria-live="polite"><span aria-hidden="true">{level.icon} </span>Threat: {level.word}</span>}
      <ReplayControls replay={state ? state.replay : null} />
      <span className="c-conn" role="status">{stale ? '◌ Offline: showing old data' : '● Connected'}</span>
    </header>
  )
}

export const RAIL = [['graph', 'Graph', '◉'], ['alerts', 'Alerts', '≡'], ['reports', 'Reports', '◔']]

export function LeftRail({ view, onChange }) {
  return (
    <nav className="c-rail" aria-label="Console views">
      {RAIL.map(([key, label, icon]) => (
        <button type="button" key={key} className="c-rail-btn" aria-pressed={view === key} aria-label={label} title={label} onClick={() => onChange(key)}>
          <span aria-hidden="true">{icon}</span><span className="c-rail-label">{label}</span>
        </button>
      ))}
    </nav>
  )
}

/** Contain button for the console: propose, then confirm in a dialog. It mirrors the phone's wording (UI/UX brief 6.7). */
export function ConsoleContain({ state, client = api, onDone }) {
  const [flow, dispatch] = useReducer(containReducer, initialContain)
  const forecast = state && state.forecast && state.forecast.status === 'pending' ? state.forecast : null
  const target = forecast ? forecast.targets[0] : null
  const name = target ? hostName(state, target.host_id) : ''

  useEffect(() => {
    if (flow.step !== 'proposing' || !target) return
    client.proposeContainment(target.host_id, forecast.forecast_id, 'console').then((action) => dispatch({ type: 'proposed', action })).catch((e) => dispatch({ type: 'error', message: e.message }))
  }, [flow.step])  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (flow.step !== 'confirming') return undefined
    const timer = setInterval(() => dispatch({ type: 'tick' }), 1000)
    return () => clearInterval(timer)
  }, [flow.step])

  if (!target) return null
  const open = flow.step === 'confirming' || flow.step === 'sending'
  const confirm = () => {
    dispatch({ type: 'confirm' })
    client.confirmContainment(flow.action.action_id).then((action) => { dispatch({ type: 'confirmed', action }); if (onDone) onDone(`${name} contained (simulated)`) }).catch((e) => dispatch({ type: 'error', message: e.message }))
  }
  const cancel = () => { if (flow.action) client.cancelContainment(flow.action.action_id).catch(() => {}); dispatch({ type: 'cancel' }) }
  return (
    <div>
      <button type="button" className="c-btn c-btn-contain" disabled={flow.step === 'proposing' || open} onClick={() => dispatch({ type: 'tap' })}>
        {flow.step === 'proposing' ? 'Asking…' : `Contain ${name}`}
      </button>
      <div className="c-error" role="alert">{flow.step === 'error' || flow.step === 'expired' ? flow.message : ''}</div>
      {open && (
        <div className="c-dialog" role="dialog" aria-modal="true" aria-label={`Contain ${name}?`}>
          <h3>Contain {name}?</h3>
          <p>This marks the host as contained. It is a SIMULATION: nothing on a real network changes.</p>
          <div className="c-row">
            <button type="button" className="c-btn c-btn-contain" onClick={confirm} disabled={flow.step === 'sending'}>Confirm</button>
            <button type="button" className="c-btn" onClick={cancel} disabled={flow.step === 'sending'}>Cancel</button>
            <span className="c-mono c-muted">{flow.secondsLeft} s left</span>
          </div>
        </div>
      )}
    </div>
  )
}

export function ForecastPanel({ state, resolved, onDone }) {
  return (
    <div className="c-panel-body">
      <ForecastBars state={state} />
      <ConsoleContain state={state} onDone={onDone} />
      <h3>Attack path</h3>
      <AttackPath2D state={state} />
      <OutcomeCard forecast={resolved} state={state} />
    </div>
  )
}

export function NodeDetailPanel({ state, hostId, onClose, onDone }) {
  const host = state.graph.hosts.find((h) => h.host_id === hostId)
  if (!host) return null
  const alerts = state.alerts.filter((a) => a.host === hostId).slice(0, 5)
  const predicted = state.forecast && state.forecast.status === 'pending' && state.forecast.targets.some((t) => t.host_id === hostId)
  return (
    <div className="c-panel-body">
      <button type="button" className="c-btn c-btn-text" onClick={onClose}>‹ Back to forecast</button>
      <h2>{host.name}</h2>
      <p className="c-mono c-muted">{host.host_id} · zone {host.zone}</p>
      <StateChip state={host.state} />
      <h3>Recent alerts</h3>
      {alerts.length === 0 ? <p className="c-muted">No alerts for this host.</p> : alerts.map((a) => (
        <p key={a.event_id} className="c-row"><SeverityBadge severity={a.severity} /><span>{a.explanation}</span></p>))}
      {predicted && <><ForecastBars state={state} /><ConsoleContain state={state} onDone={onDone} /></>}
    </div>
  )
}

export function AlertsPanel({ state }) {
  return (
    <div className="c-panel-body">
      <h2>Alerts</h2>
      {state.alerts.length === 0 ? <p className="c-muted">No alerts yet. Start the replay to see activity.</p> : state.alerts.slice(0, 50).map((a) => (
        <div key={a.event_id} className="c-alert">
          <div className="c-row"><SeverityBadge severity={a.severity} /><span className="c-mono c-muted">{formatTime(a.ts)}</span></div>
          <p>{a.explanation}</p>
        </div>))}
    </div>
  )
}

export function ReportsPanel({ state }) {
  return (
    <div className="c-panel-body">
      <h2>Reports</h2>
      <AccuracyCounter metrics={state.metrics} />
      <ForecastAccuracyChart metrics={state.metrics} />
      <h3>Alert volume</h3>
      <AlertVolumeChart alerts={state.alerts} />
    </div>
  )
}

export function TimelineStrip({ alerts, forecast }) {
  const marks = timelineMarks(alerts)
  return (
    <div className="c-timeline" role="img" aria-label={`${alerts.length} alerts on the timeline`}>
      {marks.length === 0 && <span className="c-muted">Alerts appear here as the replay runs.</span>}
      {marks.map((m) => <span key={m.id} className="c-mark" data-severity={m.severity} style={{ left: `${m.position * 100}%` }} title={m.severity} />)}
      {forecast && forecast.status === 'pending' && <span className="c-forecast-mark" title="A forecast was made" aria-hidden="true">◌</span>}
    </div>
  )
}

export function SceneSummary({ state }) {
  return <p className="c-summary" aria-live="polite">{sceneSummary(state)}</p>
}

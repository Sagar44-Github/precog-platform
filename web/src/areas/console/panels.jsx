import { useEffect, useReducer, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { api, apiGet } from '../../shared/api.js'
import { CollapsibleSection } from '../../shared/components.jsx'
import { AccuracyCounter, AttackPath2D, ForecastBars, OutcomeCard, SeverityBadge, StateChip } from '../../shared/operational-widgets.jsx'
import { AlertVolumeChart, ForecastAccuracyChart } from '../charts/index.jsx'
import { chooseReplayScenario, containReducer, formatTime, hostName, initialContain, replayButtons, replayWord, sceneSummary, SPEEDS, threatLevel, timelineMarks } from './logic.js'
import '../../shared/security-widgets.css'

// The operator panels reuse shared event and forecast facts while keeping the app shell's presentation consistent.

export function ReplayControls({ replay, client = api, canOperate = true, permissions }) {
  const mayOperate = permissions ? Boolean(permissions.can_run_replay) : canOperate
  const mayRestart = permissions ? Boolean(permissions.can_restart_replay) : mayOperate
  const [scenarios, setScenarios] = useState([])
  const [scenario, setScenario] = useState('')
  const [loadingScenarios, setLoadingScenarios] = useState(true)
  const [speed, setSpeed] = useState(1)
  const [problem, setProblem] = useState('')
  useEffect(() => {
    let active = true
    const loadScenarios = async () => {
      setLoadingScenarios(true)
      try {
        const items = await apiGet('/api/x/replay/scenarios')
        if (!active) return
        const available = Array.isArray(items) ? items : []
        setScenarios(available)
        setScenario((current) => chooseReplayScenario(available, current))
        setProblem('')
      } catch (error) {
        if (!active) return
        setScenarios([])
        setScenario('')
        setProblem(error.message || 'The active workspace scenarios could not be loaded.')
      } finally {
        if (active) setLoadingScenarios(false)
      }
    }
    loadScenarios()
    const onWorkspaceChanged = () => {
      setScenarios([])
      setScenario('')
      loadScenarios()
    }
    window.addEventListener('precog:workspace-changed', onWorkspaceChanged)
    return () => {
      active = false
      window.removeEventListener('precog:workspace-changed', onWorkspaceChanged)
    }
  }, [])
  useEffect(() => {
    setScenario((current) => chooseReplayScenario(scenarios, current, replay?.scenario_id))
  }, [replay?.scenario_id, scenarios])
  const enabled = replayButtons(replay)
  const run = (call) => () => { setProblem(''); call().catch((e) => setProblem(e.message || 'Replay control failed.')) }
  const waiting = replay && replay.state === 'waiting_for_decision'
  const canStart = mayOperate && enabled.start && Boolean(scenario) && !loadingScenarios
  return (
    <div className="c-replay" role="group" aria-label="Replay controls">
      <span className="c-control-label">REPLAY CONTROL</span>
      {mayOperate && <select className="c-select-scenario" aria-label="Scenario" value={scenario} onChange={(e) => setScenario(e.target.value)} disabled={!mayOperate || !enabled.start || loadingScenarios || !scenarios.length}>
        {scenarios.length
          ? scenarios.map((s) => <option key={s.scenario_id} value={s.scenario_id}>{s.scenario_id}</option>)
          : <option value="">{loadingScenarios ? 'Loading scenarios…' : 'No scenarios available'}</option>}
      </select>}
      {mayOperate && <button type="button" className="c-btn c-btn-start" disabled={!canStart} onClick={run(() => client.startReplay(scenario, speed))}>Start <span aria-hidden="true">▶</span></button>}
      <button type="button" className="c-btn c-btn-icon" aria-label="Pause replay" title="Pause replay" disabled={!mayOperate || !enabled.pause} onClick={run(() => client.pauseReplay())}>Ⅱ</button>
      <button type="button" className="c-btn c-btn-icon" aria-label="Resume replay" title="Resume replay" disabled={!mayOperate || !enabled.resume} onClick={run(() => client.resumeReplay())}>▶</button>
      {mayRestart && <button type="button" className="c-btn c-btn-icon" aria-label="Restart replay" title="Restart replay" disabled={!mayRestart || !enabled.restart} onClick={run(() => client.restartReplay())}>↺</button>}
      <select aria-label="Speed" value={speed} onChange={(e) => setSpeed(Number(e.target.value))} disabled={!mayOperate || !enabled.start}>
        {SPEEDS.map((s) => <option key={s} value={s}>{s}×</option>)}
      </select>
      <span className={waiting ? 'c-replay-word c-waiting' : 'c-replay-word'}><i aria-hidden="true" />{replayWord(replay)}</span>
      {problem && <span className="c-error" role="alert">{problem}</span>}
      {!mayOperate && <span className="c-replay-word">Viewer access &middot; read only</span>}
    </div>
  )
}

export function TopBar({ state, stale, canOperate = true }) {
  const level = threatLevel(state)
  return (
    <header className="c-top">
      <div className="c-top-state">{level && <span className={`c-threat c-threat-${level.key}`} aria-label={`Threat: ${level.word}`} aria-live="polite"><span aria-hidden="true">{level.icon}</span><span><small>THREAT LEVEL</small><b>{level.word}</b></span></span>}</div>
      <ReplayControls replay={state ? state.replay : null} canOperate={canOperate} />
      <div className="c-top-actions"><Link to="/containment" className="c-action-link">Response governance <span aria-hidden="true">↗</span></Link><span className="c-conn" role="status"><i aria-hidden="true" />{stale ? 'Offline · stale data' : 'Connected'}</span></div>
    </header>
  )
}

export const RAIL = [['graph', 'Network', '◉'], ['alerts', 'Events', '≡'], ['reports', 'Metrics', '◔']]

export function LeftRail({ view, onChange }) {
  return (
    <nav className="c-rail" aria-label="Console views">
      <span className="c-rail-caption">CONSOLE VIEW</span>
      {RAIL.map(([key, label, icon]) => (
        <button type="button" key={key} className="c-rail-btn" aria-pressed={view === key} aria-label={label} title={label} onClick={() => onChange(key)}>
          <span className="c-rail-icon" aria-hidden="true">{icon}</span><span className="c-rail-label">{label}</span>
        </button>
      ))}
      <span className="c-rail-spacer" />
      <span className="c-rail-footer" title="Simulation environment">SIM<br />LAB</span>
    </nav>
  )
}

/** Contain button for the console: propose, then confirm in a dialog. It mirrors the phone's wording (UI/UX brief 6.7). */
export function ConsoleContain({ state, client = api, onDone, allowed = true }) {
  const [flow, dispatch] = useReducer(containReducer, initialContain)
  const forecast = state && state.forecast && state.forecast.status === 'pending' ? state.forecast : null
  const target = forecast ? forecast.targets[0] : null
  const name = target ? hostName(state, target.host_id) : ''
  const targetHost = target ? state.graph.hosts.find((host) => host.host_id === target.host_id) : null
  const open = flow.step === 'confirming' || flow.step === 'sending'
  const trigger = useRef(null)
  const confirmButton = useRef(null)

  const cancel = () => {
    if (flow.action) client.cancelContainment(flow.action.action_id).catch(() => {})
    dispatch({ type: 'cancel' })
    window.requestAnimationFrame(() => trigger.current?.focus())
  }

  useEffect(() => {
    if (flow.step !== 'proposing' || !target || targetHost?.state === 'contained') return
    client.proposeContainment(target.host_id, forecast.forecast_id, 'console').then((action) => dispatch({ type: 'proposed', action })).catch((e) => dispatch({ type: 'error', message: e.message }))
  }, [flow.step])  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (flow.step !== 'confirming') return undefined
    const timer = setInterval(() => dispatch({ type: 'tick' }), 1000)
    return () => clearInterval(timer)
  }, [flow.step])

  useEffect(() => {
    if (!open) return undefined
    confirmButton.current?.focus()
    const onKeyDown = (event) => {
      if (event.key === 'Escape' && flow.step === 'confirming') cancel()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, flow.step])

  if (!target || !allowed) return null
  if (!targetHost) return <p className="c-containment-note" role="status">This forecast target is not part of the active workspace. Refresh the console before proposing a response.</p>
  if (targetHost.state === 'contained') return <p className="c-containment-note" role="status"><strong>Already contained</strong><span>{name} is already contained in this simulation. No additional action is available.</span></p>
  const confirm = () => {
    dispatch({ type: 'confirm' })
    client.confirmContainment(flow.action.action_id).then((action) => {
      dispatch({ type: 'confirmed', action })
      if (onDone) onDone({ kind: 'success', title: 'Containment completed', message: `${name} is contained in this simulation.`, status: 'SIMULATION' })
    }).catch((e) => dispatch({ type: 'error', message: e.message }))
  }
  return (
    <div>
      <button ref={trigger} type="button" className="c-btn c-btn-contain" disabled={flow.step === 'proposing' || open} onClick={() => dispatch({ type: 'tap' })}>
        {flow.step === 'proposing' ? 'Asking…' : `Contain ${name}`}
      </button>
      <div className="c-error" role="alert">{flow.step === 'error' || flow.step === 'expired' ? flow.message : ''}</div>
      {open && createPortal(
        <div className="c-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && flow.step === 'confirming') cancel() }}>
          <section className="c-dialog" role="dialog" aria-modal="true" aria-labelledby="contain-dialog-title" aria-describedby="contain-dialog-copy">
            <span className="c-dialog-kicker">SIMULATED RESPONSE · REVIEW REQUIRED</span>
            <h3 id="contain-dialog-title">Contain {name}?</h3>
            <p id="contain-dialog-copy">This marks the host as contained in the simulation. No real network or system changes.</p>
            <div className="c-dialog-actions">
              <button ref={confirmButton} type="button" className="c-btn c-btn-contain" onClick={confirm} disabled={flow.step === 'sending'}>{flow.step === 'sending' ? 'Applying…' : 'Confirm containment'}</button>
              <button type="button" className="c-btn" onClick={cancel} disabled={flow.step === 'sending'}>Cancel</button>
              <span className="c-mono c-muted">Expires in {flow.secondsLeft}s</span>
            </div>
          </section>
        </div>,
        document.body,
      )}
    </div>
  )
}

export function ForecastPanel({ state, resolved, onDone, canOperate = true }) {
  return (
    <div className="c-panel-body">
      <div className="c-panel-heading"><span className="c-eyebrow">PRECOG ENGINE / MODEL ESTIMATE</span><h2>Next likely targets</h2><p>Ranked from the current scripted attack path</p></div>
      {state.replay?.state === 'idle' && <div className="c-empty-callout c-console-ready"><strong>Workspace ready</strong><span>Select an available scenario from Replay controls when you want to start the simulation.</span><Link to="/replay">Open Replay Studio ↗</Link></div>}
      <ForecastBars state={state} />
      {canOperate ? <ConsoleContain state={state} onDone={onDone} /> : <p className="c-muted">Viewer access is read-only. An analyst can propose and confirm simulated containment.</p>}
      <CollapsibleSection className="c-module" title="Observed attack path" meta={`${state.graph.compromised_path.length} hosts`} open>
        <AttackPath2D state={state} />
      </CollapsibleSection>
      {resolved && <CollapsibleSection className="c-module" title="Latest forecast outcome" meta={resolved.status === 'hit' ? 'Hit' : 'Miss'}><OutcomeCard forecast={resolved} state={state} /></CollapsibleSection>}
    </div>
  )
}

export function NodeDetailPanel({ state, hostId, onClose, onDone, canOperate = true }) {
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
      {predicted && <><ForecastBars state={state} />{canOperate ? <ConsoleContain state={state} onDone={onDone} /> : <p className="c-muted">Viewer access is read-only. Ask an analyst to propose containment.</p>}</>}
    </div>
  )
}

export function AlertsPanel({ state }) {
  return (
    <div className="c-panel-body">
      <div className="c-panel-heading"><span className="c-eyebrow">DETECTION STREAM</span><h2>Security events</h2><p>{state.alerts.length} recent signals from the replay pipeline</p></div>
      <CollapsibleSection className="c-module" title="Recent events" meta={`${state.alerts.length} records`} open>
          {state.alerts.length === 0 ? <p className="c-muted">No alerts yet. Start the replay to see activity.</p> : state.alerts.slice(0, 50).map((a) => (
            <Link key={a.event_id} to={`/alerts/${encodeURIComponent(a.event_id)}`} className="c-alert c-alert-link">
              <div className="c-row"><SeverityBadge severity={a.severity} /><span className="c-mono c-muted">{formatTime(a.ts)}</span></div>
              <p>{a.explanation}</p><small className="c-mono c-muted">{hostName(state, a.host)} · {a.event_id} ↗</small>
            </Link>))}
          <Link to="/alerts" className="c-panel-link">Open alert explorer ↗</Link>
      </CollapsibleSection>
    </div>
  )
}

export function ReportsPanel({ state }) {
  return (
    <div className="c-panel-body">
      <div className="c-panel-heading"><span className="c-eyebrow">SESSION INTELLIGENCE</span><h2>Session metrics</h2><p>Replay counters and model calibration</p></div>
      <CollapsibleSection className="c-module" title="Forecast outcomes" meta={`${state.metrics.forecasts_resolved} resolved`} open><AccuracyCounter metrics={state.metrics} /><ForecastAccuracyChart metrics={state.metrics} /><p className="c-honesty-note">Session counters describe this replay. Precision@3 is trivial when three or fewer hosts are reachable.</p></CollapsibleSection>
      <CollapsibleSection className="c-module" title="Alert volume" meta={`${state.alerts.length} signals`}><AlertVolumeChart alerts={state.alerts} /></CollapsibleSection>
      <Link to="/reports" className="c-panel-link">Open session reports ↗</Link>
    </div>
  )
}

export function TimelineStrip({ alerts, forecast }) {
  const marks = timelineMarks(alerts)
  return (
    <div className="c-timeline" role="img" aria-label={`${alerts.length} alerts on the timeline`}>
      <div className="c-timeline-label"><span className="c-eyebrow">EVENT TIMELINE</span><small>{alerts.length ? `${alerts.length} signals` : 'Awaiting replay signals'}</small></div>
      <div className="c-timeline-track" aria-hidden="true">
        {marks.map((m) => <span key={m.id} className="c-mark" data-severity={m.severity} style={{ left: `${m.position * 100}%` }} title={m.severity} />)}
        {forecast && forecast.status === 'pending' && <span className="c-forecast-mark" title="A forecast was made">◌</span>}
      </div>
      {marks.length === 0 && <span className="c-timeline-empty">Timeline populates as the simulation runs.</span>}
    </div>
  )
}

export function SceneSummary({ state }) {
  return <p className="c-summary" aria-live="polite"><span>{sceneSummary(state)}</span><Link className="c-summary-host-link" to="/hosts">Browse hosts as a list ↗</Link></p>
}

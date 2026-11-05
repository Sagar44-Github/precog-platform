import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../shared/AuthContext.jsx'
import { api } from '../../shared/api.js'
import { Button, EmptyMessage, Field, PageFrame, PageHeader, ResourceNotice, formatTime, useResource } from './shared.jsx'
import './replay-studio.css'

function sessionLabel(session) {
  return `${session.scenario_id || 'Replay'} · ${session.session_id}`
}

function percent(value) {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(1)}%`
}

function EventTimeline({ events = [], position = 0, waiting = false }) {
  if (!events.length) return <EmptyMessage title="Scenario events load here">Choose a scenario to inspect its sequence.</EmptyMessage>
  return <ol className="studio-event-list" aria-label="Replay event timeline">
    {events.map((event, index) => {
      const completed = index < position
      const current = index === position && !completed
      const summary = event.kind === 'technique' ? `${event.host} · ${event.technique_id}` : event.kind === 'attempt' ? `${event.from_host} → ${event.to_host}` : `${event.packets.length} simulated packet flow(s)`
      return <li className={`studio-event-row${current ? ' studio-event-current' : ''}`} key={event.seq}>
        <span className="studio-event-number">{String(event.seq).padStart(2, '0')}</span>
        <span><strong>{event.kind} · {summary}</strong><small>offset {event.offset_ms} ms{event.pause_for_decision ? ' · analyst decision point' : ''}</small></span>
        <span className="studio-event-badge">{completed ? 'complete' : current && waiting ? 'awaiting' : current ? 'next' : ''}</span>
      </li>
    })}
  </ol>
}

function SessionMetrics({ summary }) {
  const rows = [
    ['Alerts', summary.alert_count],
    ['Resolved forecasts', summary.resolved_forecasts],
    ['Top-1 precision · session', percent(summary.precision_at_1)],
    ['Top-3 precision · session', percent(summary.precision_at_3)],
    ['Confirmed containments', `${summary.successful_containments}/${summary.containment_actions}`],
    ['High / medium / low alerts', `${summary.severity_counts.HIGH} / ${summary.severity_counts.MEDIUM} / ${summary.severity_counts.LOW}`],
  ]
  return <dl>{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
}

export default function ReplayStudioPage() {
  const { permissions } = useAuth()
  const canRun = Boolean(permissions?.can_run_replay)
  const canRestart = Boolean(permissions?.can_restart_replay)
  const loadScenarios = useCallback(() => api.replayScenarios(), [])
  const { data: scenarios, loading: loadingScenarios, error: scenarioError, refresh: refreshScenarios } = useResource(loadScenarios, 'replay-studio-scenarios')
  const [world, setWorld] = useState(null)
  const [status, setStatus] = useState(null)
  const [sessions, setSessions] = useState([])
  const [snapshots, setSnapshots] = useState([])
  const [snapshotIndex, setSnapshotIndex] = useState(-1)
  const [selectedScenario, setSelectedScenario] = useState('')
  const [scenarioDetail, setScenarioDetail] = useState(null)
  const [speed, setSpeed] = useState(1)
  const [busy, setBusy] = useState(false)
  const [errorText, setErrorText] = useState('')
  const [timeSession, setTimeSession] = useState('')
  const [compareLeft, setCompareLeft] = useState('')
  const [compareRight, setCompareRight] = useState('')
  const [comparison, setComparison] = useState(null)

  useEffect(() => {
    let active = true
    const refreshRuntime = async () => {
      try {
        const [nextStatus, nextWorld, nextSessions, nextSnapshots] = await Promise.all([
          api.replayStatus(), api.state(), api.sessions(), api.timeTravel({ limit: 200, ...(timeSession ? { session_id: timeSession } : {}) }),
        ])
        if (!active) return
        setStatus(nextStatus)
        setWorld(nextWorld)
        setSessions(nextSessions)
        setSnapshots(nextSnapshots)
        setSnapshotIndex((index) => index < 0 ? nextSnapshots.length - 1 : Math.min(index, nextSnapshots.length - 1))
        setErrorText('')
      } catch (reason) { if (active) setErrorText(reason.message || 'The replay status could not be refreshed.') }
    }
    refreshRuntime()
    const timer = window.setInterval(refreshRuntime, 2000)
    return () => { active = false; window.clearInterval(timer) }
  }, [timeSession])

  useEffect(() => {
    if (!scenarios?.length) return
    const activeId = status?.scenario_id
    const next = activeId && scenarios.some((item) => item.scenario_id === activeId) ? activeId : selectedScenario && scenarios.some((item) => item.scenario_id === selectedScenario) ? selectedScenario : scenarios[0].scenario_id
    if (next !== selectedScenario) setSelectedScenario(next)
  }, [scenarios, status?.scenario_id, selectedScenario])

  useEffect(() => {
    if (!selectedScenario) return
    let active = true
    api.replayScenario(selectedScenario).then((value) => { if (active) setScenarioDetail(value) }).catch((reason) => { if (active) setErrorText(reason.message || 'Scenario detail is unavailable.') })
    return () => { active = false }
  }, [selectedScenario])

  useEffect(() => {
    const finished = sessions.filter((session) => session.ended_at)
    if (!compareLeft && finished.length) setCompareLeft(finished.length > 1 ? finished[1].session_id : finished[0].session_id)
    if (!compareRight && finished.length > 1) setCompareRight(finished[0].session_id)
  }, [sessions, compareLeft, compareRight])

  const replayState = status?.state || world?.replay?.state || 'idle'
  const currentScenario = status?.scenario_id || selectedScenario
  const activeEvents = currentScenario === selectedScenario ? scenarioDetail?.events || [] : []
  const position = status?.position || world?.replay?.position || 0
  const displayPosition = activeEvents.length ? Math.min(position, activeEvents.length) : position
  const progress = activeEvents.length ? Math.min(100, Math.round((position / activeEvents.length) * 100)) : 0
  const selectedSnapshot = snapshots[snapshotIndex] || null
  const finishedSessions = useMemo(() => sessions.filter((session) => session.ended_at), [sessions])

  async function replayAction(action) {
    setBusy(true)
    setErrorText('')
    try {
      if (action === 'start') await api.startReplay(selectedScenario, speed)
      if (action === 'pause') await api.pauseReplay()
      if (action === 'resume') await api.resumeReplay()
      if (action === 'step') await api.stepReplay()
      if (action === 'restart') await api.restartReplay()
      setStatus(await api.replayStatus())
    } catch (reason) { setErrorText(reason.message || 'Replay control failed.') }
    finally { setBusy(false) }
  }

  async function runComparison(event) {
    event.preventDefault()
    setComparison(null)
    setErrorText('')
    try { setComparison(await api.compareSessions(compareLeft, compareRight)) }
    catch (reason) { setErrorText(reason.message || 'The sessions could not be compared.') }
  }

  return <PageFrame className="replay-studio-page">
    <PageHeader eyebrow="SIMULATION / REPLAY CONTROL" title="Replay Studio" description="Choose a scripted scenario, control its pace, step through events, inspect prior states, and compare completed sessions." actions={<Link className="ops-button ops-button-secondary" to="/scenarios">Build a scenario</Link>} />
    <div className="studio-simulation-note"><b>Simulation only.</b> Replay events are scripted data. Time travel is read-only, and session scores describe these runs rather than overall model accuracy.</div>
    <ResourceNotice loading={loadingScenarios} error={scenarioError} data={scenarios} onRetry={refreshScenarios} />
    <div className="studio-grid">
      <section className="ops-card studio-control-card">
        <div className="ops-card-header"><div><h3>Replay controls</h3><p>Speed is fixed when a replay starts. Pause is available during any event.</p></div><span className="studio-card-tag">CONTROL ROOM</span></div>
        <div className="studio-control-row">
          <Field label="Scenario"><select aria-label="Replay scenario" className="studio-scenario-select" value={selectedScenario} onChange={(event) => setSelectedScenario(event.target.value)} disabled={['running', 'paused', 'waiting_for_decision'].includes(replayState)}>
            {(scenarios || []).map((scenario) => <option key={scenario.scenario_id} value={scenario.scenario_id}>{scenario.scenario_id}{scenario.custom ? ' · custom' : ''}</option>)}
          </select></Field>
          <label className="studio-speed"><span>Replay speed <b>{speed}×</b></span><input aria-label="Replay speed" type="range" min="1" max="8" step="1" value={speed} disabled={['running', 'paused', 'waiting_for_decision'].includes(replayState)} onChange={(event) => setSpeed(Number(event.target.value))} /></label>
          <div className="studio-buttons">
            {['idle', 'finished'].includes(replayState) && <Button type="button" onClick={() => replayAction('start')} disabled={!canRun || busy || !selectedScenario}>Start replay</Button>}
            {replayState === 'running' && <Button type="button" onClick={() => replayAction('pause')} disabled={!canRun || busy}>Pause</Button>}
            {replayState === 'paused' && <><Button type="button" onClick={() => replayAction('resume')} disabled={!canRun || busy}>Resume replay</Button><Button type="button" className="ops-button-secondary" onClick={() => replayAction('step')} disabled={!canRun || busy}>Step one event</Button></>}
            {replayState === 'waiting_for_decision' && <Button type="button" className="ops-button-secondary" onClick={() => replayAction('resume')} disabled={!canRun || busy}>Continue without containment</Button>}
            {canRestart && ['running', 'paused', 'waiting_for_decision', 'finished'].includes(replayState) && <Button type="button" className="ops-button-secondary" onClick={() => replayAction('restart')} disabled={busy}>Restart scenario</Button>}
          </div>
        </div>
        <div className={`studio-status studio-status-${replayState}`} role="status"><i className="studio-status-mark" /><span className="studio-status-copy"><b>{replayState.replaceAll('_', ' ')}</b><small>{currentScenario || 'No replay selected'} · event {displayPosition}{activeEvents.length ? ` of ${activeEvents.length}` : ''}</small></span><span className="studio-status-meta">{speed}× · {status?.session_id || world?.session?.session_id || 'session pending'}</span></div>
        <div className="studio-progress" role="progressbar" aria-label="Replay event progress" aria-valuenow={progress} aria-valuemin="0" aria-valuemax="100"><span style={{ width: `${progress}%` }} /></div>
        {errorText && <p className="ops-error studio-error" role="alert">{errorText}</p>}
        {!canRun && <p className="studio-honesty-note">Viewer access is read-only. An analyst can start and control replays; only an admin can restart one.</p>}
      </section>

      <section className="ops-card studio-timeline-card">
        <div className="ops-card-header"><div><h3>Event sequence</h3><p>{scenarioDetail?.description || 'Select a scenario to inspect each event.'}</p></div><span className="studio-card-tag">SCRIPTED DATA</span></div>
        <EventTimeline events={activeEvents} position={position} waiting={replayState === 'waiting_for_decision'} />
      </section>

      <section className="ops-card studio-time-card studio-full">
        <div className="ops-card-header studio-history-header"><div><h3>Time travel</h3><p>Scrub read-only snapshots captured as the shared world changed. The live replay is not modified.</p></div><Field label="Session history"><select aria-label="Time travel session" value={timeSession} onChange={(event) => { setTimeSession(event.target.value); setSnapshotIndex(-1) }}><option value="">Recent snapshots · all sessions</option>{finishedSessions.map((session) => <option value={session.session_id} key={session.session_id}>{sessionLabel(session)}</option>)}</select></Field></div>
        {snapshots.length ? <>
          <div className="studio-time-control"><input aria-label="Time travel snapshot" type="range" min="0" max={Math.max(0, snapshots.length - 1)} value={Math.max(0, snapshotIndex)} onChange={(event) => setSnapshotIndex(Number(event.target.value))} />
            <div className="studio-time-meta"><span>{snapshots.length} snapshots · bounded in-memory history</span><span>{selectedSnapshot ? `v${selectedSnapshot.version} · ${formatTime(selectedSnapshot.captured_at)}` : 'Select a snapshot'}</span></div>
          </div>
          {selectedSnapshot && <div className="studio-time-view"><div className="studio-time-graph" aria-label="Historical network state">{(selectedSnapshot.graph?.hosts || []).map((host) => <span className={`studio-host-chip state-${host.state}`} key={host.host_id}><i />{host.name} · {host.state}</span>)}</div><div className="studio-time-summary"><b>{selectedSnapshot.replay?.scenario_id || 'No scenario'} · {selectedSnapshot.replay?.state?.replaceAll('_', ' ')}</b><span>{selectedSnapshot.alerts?.length || 0} alert(s) in this snapshot</span><span>Predicted target: {selectedSnapshot.forecast?.targets?.[0]?.host_id || 'none'}</span><span>Compromised path: {(selectedSnapshot.graph?.compromised_path || []).join(' → ') || 'none'}</span></div></div>}
        </> : <EmptyMessage title="No history snapshots yet">Start or replay a scenario to fill the bounded time-travel buffer.</EmptyMessage>}
      </section>

      <section className="ops-card studio-compare-card studio-full">
        <div className="ops-card-header"><div><h3>Compare finished sessions</h3><p>Compare alert volume, forecast outcomes, and confirmed simulated containment side by side.</p></div><span className="studio-card-tag">READ ONLY</span></div>
        <form className="studio-compare-selects" onSubmit={runComparison}>
          <Field label="Left session"><select aria-label="Left session" value={compareLeft} onChange={(event) => setCompareLeft(event.target.value)}><option value="">Select a finished session</option>{finishedSessions.map((session) => <option key={session.session_id} value={session.session_id}>{sessionLabel(session)}</option>)}</select></Field>
          <Field label="Right session"><select aria-label="Right session" value={compareRight} onChange={(event) => setCompareRight(event.target.value)}><option value="">Select a finished session</option>{finishedSessions.map((session) => <option key={session.session_id} value={session.session_id}>{sessionLabel(session)}</option>)}</select></Field>
          <Button type="submit" disabled={!compareLeft || !compareRight || compareLeft === compareRight}>Compare sessions</Button>
        </form>
        {comparison && <div className="studio-compare-result"><article className="studio-compare-column"><h4>{sessionLabel(comparison.left)}</h4><SessionMetrics summary={comparison.left} /></article><article className="studio-compare-column"><h4>{sessionLabel(comparison.right)}</h4><SessionMetrics summary={comparison.right} /></article></div>}
        <p className="studio-honesty-note">{comparison?.note || 'Session counters describe these runs; they are not the model’s overall accuracy. Forecast misses remain visible in the session record.'}</p>
      </section>
    </div>
  </PageFrame>
}

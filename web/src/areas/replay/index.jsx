import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { api, apiGet, apiPost } from '../../shared/api.js'
import { useAuth } from '../../shared/AuthContext.jsx'
import { Icon } from '../../shared/icons.jsx'
import { EmptyState } from '../../shared/components.jsx'
import { blankScenario, eventLabel, resequence, timelineLanes } from './logic.js'
import './replay.css'

const SIM_NOTE = 'SIMULATION · Scripted demo data only. No real traffic or systems are affected.'

function ErrorLine({ children }) {
  return children ? <p className="replay-error" role="alert">{children}</p> : null
}

function Metric({ label, value }) {
  return <div className="replay-metric"><span>{label}</span><strong>{value ?? '—'}</strong></div>
}

function StudioPage() {
  const { role } = useAuth()
  const location = useLocation()
  const canOperate = role !== 'viewer'
  const [scenarios, setScenarios] = useState([])
  const [scenarioId, setScenarioId] = useState(location.state?.scenarioId || '')
  const [scenarioRecord, setScenarioRecord] = useState(null)
  const [studio, setStudio] = useState(null)
  const [runs, setRuns] = useState([])
  const [snapshots, setSnapshots] = useState([])
  const [breakpoints, setBreakpoints] = useState([])
  const [speed, setSpeed] = useState(1)
  const [scrub, setScrub] = useState(0)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  const active = studio?.active_run
  const status = studio?.status || { state: 'idle', position: 0, speed: 1 }
  const selectedScenario = scenarios.find((item) => item.scenario_id === scenarioId)
  const running = ['running', 'paused', 'waiting_for_decision'].includes(status.state)

  const refresh = useCallback(async () => {
    try {
      const [catalog, state, history] = await Promise.all([api.scenarios(), api.studioStatus(), api.runs()])
      setScenarios(catalog.items || [])
      setStudio(state)
      setRuns(history)
      if (!scenarioId && catalog.items?.length) setScenarioId(catalog.items[0].scenario_id)
      if (state.active_run?.run_id) {
        const index = await api.runSnapshots(state.active_run.run_id)
        setSnapshots(index.items || [])
        setScrub(state.status.position)
      }
    } catch (issue) { setError(issue.message) }
  }, [scenarioId])

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => {
    let alive = true
    if (!scenarioId) { setScenarioRecord(null); return () => { alive = false } }
    api.scenario(scenarioId).then((record) => { if (alive) setScenarioRecord(record.scenario) }).catch((issue) => { if (alive) setError(issue.message) })
    return () => { alive = false }
  }, [scenarioId])
  useEffect(() => {
    const timer = window.setInterval(refresh, 1100)
    return () => window.clearInterval(timer)
  }, [refresh])

  async function act(action) {
    setBusy(true); setError('')
    try { await action(); await refresh() } catch (issue) { setError(issue.message) } finally { setBusy(false) }
  }

  const events = scenarioRecord?.events || []
  const eventCount = events.length
  const maxPosition = Math.max(eventCount, snapshots.at(-1)?.position || 0)
  const stateLabel = status.state.replaceAll('_', ' ')
  return (
    <main className="replay-page" aria-labelledby="studio-title">
      <div className="replay-page-head">
        <div><p className="replay-eyebrow">REPLAY CONTROL · DETERMINISTIC SIMULATION</p><h1 id="studio-title">Replay studio</h1><p className="replay-lede">Run a scenario at presentation speed, stop on events, and step through the reconstructed response.</p></div>
        <Link className="replay-secondary-button" to="/scenarios"><Icon name="layers" size={16} /> Scenario library</Link>
      </div>
      <p className="replay-simulation-note"><span />{SIM_NOTE}</p>
      <ErrorLine>{error}</ErrorLine>

      <section className="replay-workbench">
        <div className="replay-panel replay-controls">
          <div className="replay-panel-head"><div><p className="replay-eyebrow">CURRENT RUN</p><h2>Control room</h2></div><span className={`replay-state replay-state-${status.state}`}>{stateLabel}</span></div>
          <label className="replay-label" htmlFor="studio-scenario">Scenario</label>
          <select id="studio-scenario" value={scenarioId} onChange={(event) => setScenarioId(event.target.value)} disabled={running}>
            {scenarios.map((item) => <option key={item.scenario_id} value={item.scenario_id}>{item.description} · {item.scenario_id}</option>)}
          </select>
          <div className="replay-speed-row"><label htmlFor="studio-speed">Playback speed</label><output htmlFor="studio-speed">{speed.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')}×</output></div>
          <input id="studio-speed" type="range" min="0.25" max="8" step="0.25" value={speed} onChange={(event) => setSpeed(Number(event.target.value))} disabled={!canOperate} />
          <div className="replay-speed-labels"><span>0.25×</span><span>8×</span></div>
          {running && <button type="button" className="replay-text-button replay-apply-speed" disabled={!canOperate || busy} onClick={() => act(() => api.setReplaySpeed(speed))}>Apply {speed}× speed</button>}
          <div className="replay-control-grid">
            {!running && <button type="button" className="replay-primary-button" disabled={!canOperate || busy || !scenarioId} onClick={() => act(() => api.startStudio(scenarioId, speed))}><Icon name="play" size={15} /> Start paused</button>}
            {status.state === 'running' && <button type="button" className="replay-secondary-button" disabled={!canOperate || busy} onClick={() => act(() => api.pauseReplay())}>Pause</button>}
            {status.state === 'paused' && <button type="button" className="replay-primary-button" disabled={!canOperate || busy} onClick={() => act(() => api.resumeReplay())}><Icon name="play" size={15} /> Play</button>}
            {status.state === 'waiting_for_decision' && <button type="button" className="replay-primary-button" disabled={!canOperate || busy} onClick={() => act(() => api.resumeReplay())}>Continue without response</button>}
            {status.state === 'paused' && <button type="button" className="replay-secondary-button" disabled={!canOperate || busy || status.position === 0} onClick={() => act(() => api.stepBackReplay())}>← Step back</button>}
            {status.state === 'paused' && <button type="button" className="replay-secondary-button" disabled={!canOperate || busy} onClick={() => act(() => api.stepReplay())}>Step next →</button>}
          </div>
          {!canOperate && <p className="replay-role-note">Viewer access is read-only. An analyst or admin can control replays.</p>}
          <div className="replay-run-meta"><span>RUN ID</span><strong>{active?.run_id || runs[0]?.run_id || '—'}</strong><span>POSITION</span><strong>{status.position} / {maxPosition}</strong><span>EVENTS</span><strong>{selectedScenario?.events ?? '—'}</strong></div>
          {status.state === 'waiting_for_decision' && <div className="replay-decision-callout" role="status"><b>Decision point</b><span>Open the live console to propose and confirm simulated containment, then return here.</span><Link to="/console">Open console ↗</Link></div>}
        </div>

        <div className="replay-panel replay-timeline-panel">
          <div className="replay-panel-head"><div><p className="replay-eyebrow">EVENT TIMELINE</p><h2>{selectedScenario?.scenario_id || 'Choose a scenario'}</h2></div><Link to={selectedScenario?.source === 'user' ? `/scenarios/${encodeURIComponent(scenarioId)}/edit` : '/scenarios'}>Edit scenario ↗</Link></div>
          <div className="replay-timeline-toolbar"><span>{snapshots.length ? `${snapshots.length} recorded snapshots` : 'Start a run to record event snapshots'}</span><Link to="/runs">Run history</Link></div>
          <ol className="replay-event-list">
            {events.map((event, index) => (
              <li key={`${event.seq}-${index}`} className={index < status.position ? 'is-complete' : index === status.position ? 'is-current' : ''}>
                <span className="replay-event-number">{String(event.seq).padStart(2, '0')}</span><span className="replay-event-type">{event.kind}</span><span className="replay-event-description">{eventLabel(event)}</span><time>{(event.offset_ms / 1000).toFixed(1)}s</time>
                {event.pause_for_decision && <span className="replay-event-flag">DECISION</span>}
              </li>
            ))}
          </ol>
          {events.length === 0 && <EmptyState>Choose or build a scenario to see its event timeline.</EmptyState>}
          {selectedScenario && <fieldset className="replay-breakpoints" disabled={!canOperate || !running}>
            <legend>Breakpoints · stop after selected events</legend>
            {events.map((event) => <label key={event.seq}><input type="checkbox" checked={breakpoints.includes(event.seq)} onChange={(change) => {
              const next = change.target.checked ? [...breakpoints, event.seq] : breakpoints.filter((item) => item !== event.seq)
              setBreakpoints(next)
              api.setBreakpoints(next).catch((issue) => setError(issue.message))
            }} /> Event {event.seq}</label>)}
          </fieldset>}
          {active && snapshots.length > 1 && <div className="replay-scrubber">
            <label htmlFor="snapshot-scrubber">Recorded position <span>{scrub}</span></label>
            <input id="snapshot-scrubber" type="range" min="0" max={Math.max(0, snapshots.at(-1)?.position || 0)} step="1" value={Math.min(scrub, Math.max(0, snapshots.at(-1)?.position || 0))} onChange={(event) => setScrub(Number(event.target.value))} />
            <button type="button" className="replay-secondary-button" disabled={!canOperate || busy || !running} onClick={() => act(() => api.seekReplay(scrub))}>Restore this snapshot</button>
          </div>}
        </div>
      </section>

      <section className="replay-lower-grid">
        <div className="replay-panel"><div className="replay-panel-head"><div><p className="replay-eyebrow">LATEST RUN</p><h2>Run outcome</h2></div>{runs[0] && <Link to={`/runs/${runs[0].run_id}`}>Open report ↗</Link>}</div>
          {runs[0] ? <><div className="replay-metric-grid"><Metric label="Alerts" value={runs[0].alerts_count} /><Metric label="Incidents" value={runs[0].incidents_count} /><Metric label="Forecasts" value={runs[0].forecasts_count} /><Metric label="Actions" value={runs[0].actions_count} /></div><p className="replay-run-summary">{runs[0].scenario_id} · {runs[0].outcome} · {runs[0].speed}×</p></> : <EmptyState>Finished runs and their metrics appear here.</EmptyState>}
        </div>
        <div className="replay-panel"><div className="replay-panel-head"><div><p className="replay-eyebrow">SCENARIO DESIGN</p><h2>Build a repeatable story</h2></div><Icon name="layers" /></div><p className="replay-copy">Use host lanes and scripted event cards to compose, validate, dry-run, and save a rehearsal.</p><Link className="replay-primary-button" to="/scenarios/new">Open scenario builder <Icon name="chevron" size={15} /></Link></div>
      </section>
    </main>
  )
}

function ScenarioLibraryPage() {
  const { role } = useAuth()
  const canEdit = role !== 'viewer'
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const refresh = useCallback(async () => {
    try { const result = await api.scenarios(); setItems(result.items || []) } catch (issue) { setError(issue.message) } finally { setLoading(false) }
  }, [])
  useEffect(() => { refresh() }, [refresh])
  async function remove(id) {
    try { await api.deleteScenario(id); await refresh() } catch (issue) { setError(issue.message) }
  }
  return <main className="replay-page" aria-labelledby="scenario-library-title">
    <div className="replay-page-head"><div><p className="replay-eyebrow">REPLAY LIBRARY</p><h1 id="scenario-library-title">Scenarios</h1><p className="replay-lede">Four shipped rehearsals plus your saved scripts. Every event references a demo host id.</p></div>{canEdit ? <Link to="/scenarios/new" className="replay-primary-button"><Icon name="layers" size={15} /> Build scenario</Link> : <span className="replay-role-note">Viewer access · scenario library is read-only.</span>}</div>
    <p className="replay-simulation-note"><span />{SIM_NOTE}</p><ErrorLine>{error}</ErrorLine>
    {loading ? <p className="replay-copy">Loading scenario library…</p> : <div className="scenario-card-grid">{items.map((item) => <article className="replay-panel scenario-card" key={item.scenario_id}>
      <div className="scenario-card-top"><span className={`scenario-source source-${item.source}`}>{item.source === 'user' ? 'USER SCENARIO' : 'SHIPPED TEMPLATE'}</span><span>{item.events} events</span></div>
      <h2>{item.description}</h2><p className="scenario-card-id">{item.scenario_id}</p><p className="replay-copy">{item.has_decision_point ? 'Includes a pause for analyst response.' : 'Runs through without a decision pause.'}</p>
      <div className="scenario-card-actions"><button className="replay-primary-button" type="button" onClick={() => navigate('/replay', { state: { scenarioId: item.scenario_id } })}>Open in studio <Icon name="play" size={14} /></button>{canEdit && item.editable && <><Link className="replay-secondary-button" to={`/scenarios/${encodeURIComponent(item.scenario_id)}/edit`}>Edit</Link><button className="replay-text-button" type="button" onClick={() => remove(item.scenario_id)}>Delete</button></>}</div>
    </article>)}</div>}
  </main>
}

function EventEditor({ event, index, hosts, techniques, onChange, onDelete, disabled }) {
  const hostOptions = hosts.map((host) => <option value={host.host_id} key={host.host_id}>{host.name} · {host.host_id}</option>)
  const update = (key, value) => onChange(index, { ...event, [key]: value })
  const updatePacket = (key, value) => update('packets', [{ ...event.packets[0], [key]: value }])
  return <article className="scenario-event-editor">
    <header><span className="replay-event-number">{String(index + 1).padStart(2, '0')}</span><b>{event.kind} event</b>{!disabled && <button type="button" className="replay-text-button" aria-label={`Remove event ${index + 1}`} onClick={() => onDelete(index)}>Remove</button>}</header>
    <div className="scenario-event-fields">
      <label>Offset (ms)<input type="number" min="0" max="7200000" step="100" value={event.offset_ms} onChange={(e) => update('offset_ms', Number(e.target.value))} disabled={disabled} /></label>
      {event.kind === 'technique' && <>
        <label>Host<select value={event.host} onChange={(e) => update('host', e.target.value)} disabled={disabled}>{hostOptions}</select></label>
        <label>ATT&amp;CK technique<select value={event.technique_id} onChange={(e) => update('technique_id', e.target.value)} disabled={disabled}>{techniques.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.name}</option>)}</select></label>
        <label>Evidence note<input value={event.note || ''} maxLength="200" onChange={(e) => update('note', e.target.value)} disabled={disabled} /></label>
        <label className="scenario-checkbox"><input type="checkbox" checked={Boolean(event.compromise)} onChange={(e) => update('compromise', e.target.checked)} disabled={disabled} /> Marks host compromised</label>
      </>}
      {event.kind === 'attempt' && <>
        <label>From host<select value={event.from_host} onChange={(e) => update('from_host', e.target.value)} disabled={disabled}>{hostOptions}</select></label>
        <label>Target host<select value={event.to_host} onChange={(e) => update('to_host', e.target.value)} disabled={disabled}>{hostOptions}</select></label>
        <label>ATT&amp;CK technique<select value={event.technique_id} onChange={(e) => update('technique_id', e.target.value)} disabled={disabled}>{techniques.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.name}</option>)}</select></label>
        <label>Evidence note<input value={event.note || ''} maxLength="200" onChange={(e) => update('note', e.target.value)} disabled={disabled} /></label>
      </>}
      {event.kind === 'traffic' && <>
        <label>Source host<select value={event.packets[0].src_host} onChange={(e) => updatePacket('src_host', e.target.value)} disabled={disabled}>{hostOptions}</select></label>
        <label>Destination host<select value={event.packets[0].dst_host} onChange={(e) => updatePacket('dst_host', e.target.value)} disabled={disabled}>{hostOptions}</select></label>
        <label>Protocol<select value={event.packets[0].protocol} onChange={(e) => updatePacket('protocol', e.target.value)} disabled={disabled}>{['TCP', 'UDP', 'ICMP'].map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>Destination port<input type="number" min="0" max="65535" value={event.packets[0].dst_port} onChange={(e) => updatePacket('dst_port', Number(e.target.value))} disabled={disabled} /></label>
        <label>Packet size<input type="number" min="1" max="65535" value={event.packets[0].size} onChange={(e) => updatePacket('size', Number(e.target.value))} disabled={disabled} /></label>
        <label>Repeat count<input type="number" min="1" max="50" value={event.packets[0].repeat || 1} onChange={(e) => updatePacket('repeat', Number(e.target.value))} disabled={disabled} /></label>
      </>}
      <label className="scenario-checkbox"><input type="checkbox" checked={Boolean(event.pause_for_decision)} onChange={(e) => update('pause_for_decision', e.target.checked)} disabled={disabled} /> Pause for analyst decision</label>
    </div>
  </article>
}

function ScenarioBuilderPage({ scenarioId }) {
  const { role } = useAuth()
  const canEdit = role !== 'viewer'
  const navigate = useNavigate()
  const [scenario, setScenario] = useState(() => blankScenario())
  const [hosts, setHosts] = useState([])
  const [techniques, setTechniques] = useState([])
  const [templates, setTemplates] = useState([])
  const [validation, setValidation] = useState(null)
  const [dryRun, setDryRun] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const editing = Boolean(scenarioId && scenarioId !== 'new')
  const hostList = hosts.length ? hosts : [{ host_id: 'host-a', name: 'Workstation A' }]
  const techniqueList = techniques.length ? techniques : [{ id: 'T1046', name: 'Network Service Discovery' }]

  useEffect(() => {
    let alive = true
    Promise.all([api.scenarios(), api.graph(), apiGet('/api/x/scenarios/options')]).then(async ([catalog, graph, options]) => {
      if (!alive) return
      setTemplates(catalog.items || [])
      setHosts(options.hosts || graph.hosts || [])
      setTechniques(options.techniques || [])
      if (editing) {
        const draft = await api.scenario(scenarioId)
        if (!alive) return
        if (!draft.editable) throw new Error('Shipped templates are read-only. Create a user copy to edit one.')
        setScenario(draft.scenario)
      }
      setLoaded(true)
    }).catch((issue) => { if (alive) { setError(issue.message); setLoaded(true) } })
    return () => { alive = false }
  }, [editing, scenarioId])

  const lanes = useMemo(() => timelineLanes(scenario.events, hostList), [scenario.events, hostList])
  function updateEvent(index, event) { setScenario((current) => ({ ...current, events: resequence(current.events.map((item, i) => i === index ? event : item)) })); setValidation(null); setDryRun(null) }
  function deleteEvent(index) { setScenario((current) => ({ ...current, events: resequence(current.events.filter((_, i) => i !== index)) })); setValidation(null); setDryRun(null) }
  function addEvent(kind) {
    const seq = scenario.events.length + 1
    const hostA = hostList[0]?.host_id || 'host-a'
    const hostB = hostList.find((host) => host.host_id !== hostA)?.host_id || 'server-b'
    const event = kind === 'technique'
      ? { seq, offset_ms: (scenario.events.at(-1)?.offset_ms || 0) + 1000, kind, host: hostA, technique_id: techniqueList[0]?.id || 'T1046', compromise: false, note: '' }
      : kind === 'attempt'
        ? { seq, offset_ms: (scenario.events.at(-1)?.offset_ms || 0) + 1000, kind, from_host: hostA, to_host: hostB, technique_id: techniqueList.find((item) => item.id === 'T1021.004')?.id || techniqueList[0]?.id || 'T1046', note: '' }
        : { seq, offset_ms: (scenario.events.at(-1)?.offset_ms || 0) + 1000, kind, packets: [{ src_host: hostA, dst_host: hostB, protocol: 'TCP', dst_port: 445, size: 600, repeat: 1 }] }
    setScenario((current) => ({ ...current, events: [...current.events, event] })); setValidation(null); setDryRun(null)
  }
  async function validate() { setBusy(true); setError(''); try { setValidation(await api.validateScenario(scenario)) } catch (issue) { setError(issue.message) } finally { setBusy(false) } }
  async function runDry() { setBusy(true); setError(''); try { setDryRun(await api.dryRunScenario(scenario)) } catch (issue) { setError(issue.message) } finally { setBusy(false) } }
  async function save() {
    setBusy(true); setError('')
    try {
      const checked = await api.validateScenario(scenario); setValidation(checked)
      if (!checked.valid) return
      await api.saveScenario(scenario)
      navigate('/scenarios')
    } catch (issue) { setError(issue.message) } finally { setBusy(false) }
  }
  function loadTemplate(id) {
    api.scenario(id).then((result) => {
      const copy = { ...result.scenario, scenario_id: `user-${id.replace(/[^a-z0-9-]/g, '-')}` }
      setScenario(copy); setValidation(null); setDryRun(null)
    }).catch((issue) => setError(issue.message))
  }
  function importJson(file) {
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      try { setScenario(JSON.parse(String(reader.result))); setValidation(null); setDryRun(null); setError('') }
      catch { setError('Could not import the file: check that it contains valid scenario JSON.') }
    }
    reader.readAsText(file)
  }
  function exportJson() {
    const blob = new Blob([`${JSON.stringify(scenario, null, 2)}\n`], { type: 'application/json' })
    const href = URL.createObjectURL(blob)
    const anchor = document.createElement('a'); anchor.href = href; anchor.download = `${scenario.scenario_id || 'scenario'}.json`; anchor.click(); URL.revokeObjectURL(href)
  }

  return <main className="replay-page scenario-builder" aria-labelledby="scenario-builder-title">
    <div className="replay-page-head"><div><p className="replay-eyebrow">SCRIPT EDITOR · HOST LANES</p><h1 id="scenario-builder-title">{editing ? 'Edit scenario' : 'Scenario builder'}</h1><p className="replay-lede">Compose a timeline from scripted techniques, packet traffic, and movement attempts.</p></div><Link className="replay-secondary-button" to="/scenarios">Back to scenarios</Link></div>
    <p className="replay-simulation-note"><span />{SIM_NOTE}</p><ErrorLine>{error}</ErrorLine>
    {!loaded ? <p className="replay-copy">Loading hosts and ATT&amp;CK techniques…</p> : <>
      <section className="replay-panel scenario-meta-panel">
        <div className="scenario-meta-fields"><label>Scenario id<input value={scenario.scenario_id} maxLength="64" onChange={(e) => { setScenario((item) => ({ ...item, scenario_id: e.target.value })); setValidation(null) }} disabled={!canEdit} aria-describedby="scenario-id-hint" /></label><label>Description<input value={scenario.description} maxLength="500" onChange={(e) => setScenario((item) => ({ ...item, description: e.target.value }))} disabled={!canEdit} /></label><p id="scenario-id-hint">Saved ids must start with <code>user-</code>. They are identifiers and never treated as file paths.</p></div>
        <div className="scenario-tool-row"><label className="replay-file-button">Import JSON<input aria-label="Import scenario JSON" type="file" accept="application/json,.json" onChange={(e) => importJson(e.target.files?.[0])} disabled={!canEdit} /></label><button type="button" className="replay-secondary-button" onClick={exportJson}>Export JSON</button><label className="replay-label scenario-template-picker">Template<select defaultValue="" disabled={!canEdit} onChange={(e) => { if (e.target.value) loadTemplate(e.target.value); e.target.value = '' }}><option value="" disabled>Load a shipped template…</option>{templates.map((item) => <option key={item.scenario_id} value={item.scenario_id}>{item.scenario_id}</option>)}</select></label></div>
      </section>

      <section className="replay-panel scenario-timeline-panel"><div className="replay-panel-head"><div><p className="replay-eyebrow">VISUAL TIMELINE</p><h2>Host lanes <span>{scenario.events.length} / 200 events</span></h2></div>{canEdit && <div className="scenario-add-actions"><button type="button" onClick={() => addEvent('technique')}>＋ Technique</button><button type="button" onClick={() => addEvent('traffic')}>＋ Traffic</button><button type="button" onClick={() => addEvent('attempt')}>＋ Attempt</button></div>}</div>
        <div className="scenario-lanes" aria-label="Scenario timeline lanes" tabIndex={0}>{lanes.map((lane) => <div className="scenario-lane" key={lane.host_id}><b>{lane.name}</b><div>{lane.items.map((item) => <span key={`${item.seq}-${item.offset_ms}`} title={`Event ${item.seq} at ${item.offset_ms} milliseconds`} className={`lane-event lane-${item.kind}`}><small>{item.offset_ms}ms</small><strong>{item.label}</strong></span>)}</div></div>)}{!lanes.length && <p className="replay-copy">Add a scripted event to begin.</p>}</div>
        <div className="scenario-editor-list">{scenario.events.map((event, index) => <EventEditor key={`${event.seq}-${index}`} event={event} index={index} hosts={hostList} techniques={techniqueList} onChange={updateEvent} onDelete={deleteEvent} disabled={!canEdit} />)}</div>
      </section>

      <div className="scenario-validation-actions"><button className="replay-secondary-button" type="button" disabled={!canEdit || busy} onClick={validate}>Validate scenario</button><button className="replay-secondary-button" type="button" disabled={!canEdit || busy} onClick={runDry}>Dry-run estimate</button><button className="replay-primary-button" type="button" disabled={!canEdit || busy || validation?.valid === false} onClick={save}>Save scenario</button>{!canEdit && <span className="replay-role-note">Viewer access is read-only.</span>}</div>
      {validation && <section className={`replay-panel validation-panel ${validation.valid ? 'validation-valid' : 'validation-invalid'}`} aria-live="polite"><h2>{validation.valid ? 'Scenario valid' : 'Fix these validation errors'}</h2><p>{validation.event_count} events · {(validation.duration_ms / 1000).toFixed(1)} seconds maximum duration</p>{validation.errors.map((item, index) => <p className="validation-error-row" key={`${item.path}-${index}`}><code>{item.path}</code><span>{item.message}</span></p>)}</section>}
      {dryRun && <section className="replay-panel dryrun-panel"><p className="replay-eyebrow">MODEL-BASED ESTIMATE</p><h2>Dry-run projection</h2><p>{dryRun.basis}</p><div className="dryrun-hosts">{Object.entries(dryRun.host_states).map(([host, state]) => <span key={host}><b>{host}</b><i>{state}</i></span>)}</div>{dryRun.forecasts.map((forecast, index) => <div className="dryrun-forecast" key={`${forecast.from_host}-${index}`}><b>From {forecast.from_host}</b>{forecast.targets.map((target) => <span key={target.host_id}>#{target.rank} {target.host_id} · {(target.confidence * 100).toFixed(1)}%</span>)}{forecast.outcome && <small>{forecast.outcome.blocked ? 'blocked' : forecast.outcome.rank_hit ? `hit at rank ${forecast.outcome.rank_hit}` : 'miss'}</small>}</div>)}</section>}
    </>}
  </main>
}

function RunListPage() {
  const [runs, setRuns] = useState([])
  const [selected, setSelected] = useState([])
  const [error, setError] = useState('')
  const navigate = useNavigate()
  useEffect(() => { api.runs().then(setRuns).catch((issue) => setError(issue.message)) }, [])
  return <main className="replay-page" aria-labelledby="runs-title"><div className="replay-page-head"><div><p className="replay-eyebrow">RUN ARCHIVE · LAST 50 FINISHED</p><h1 id="runs-title">Run history</h1><p className="replay-lede">Compare outcomes from repeatable scenarios. Timestamps vary; scripted sequence identifiers restart for each run.</p></div><Link className="replay-secondary-button" to="/replay">Open replay studio</Link></div><p className="replay-simulation-note"><span />{SIM_NOTE}</p><ErrorLine>{error}</ErrorLine>
    {!runs.length ? <section className="replay-panel"><EmptyState>No finished runs yet. Start a replay in the studio to populate the archive.</EmptyState><Link to="/replay" className="replay-primary-button">Go to replay studio</Link></section> : <><div className="runs-toolbar"><span>Select two runs to compare</span><button className="replay-primary-button" type="button" disabled={selected.length !== 2} onClick={() => navigate(`/runs/compare?a=${encodeURIComponent(selected[0])}&b=${encodeURIComponent(selected[1])}`)}>Compare selected runs</button></div><div className="runs-table-wrap"><table className="runs-table"><thead><tr><th>Select</th><th>Run</th><th>Scenario</th><th>Outcome</th><th>Alerts</th><th>Incidents</th><th>Forecasts</th><th>Actions</th><th>Speed</th><th>Report</th></tr></thead><tbody>{runs.map((run) => <tr key={run.run_id}><td><input type="checkbox" aria-label={`Select ${run.run_id}`} checked={selected.includes(run.run_id)} onChange={(e) => setSelected((value) => e.target.checked ? [...value.filter((id) => id !== run.run_id).slice(-1), run.run_id] : value.filter((id) => id !== run.run_id))} /></td><td><code>{run.run_id}</code></td><td>{run.scenario_id}</td><td><span className="run-outcome">{run.outcome}</span></td><td>{run.alerts_count}</td><td>{run.incidents_count}</td><td>{run.forecasts_count}</td><td>{run.actions_count}</td><td>{run.speed}×</td><td><Link to={`/runs/${run.run_id}`}>Open ↗</Link></td></tr>)}</tbody></table></div></>}
  </main>
}

function RunDetailPage({ runId }) {
  const [detail, setDetail] = useState(null)
  const [index, setIndex] = useState([])
  const [snapshot, setSnapshot] = useState(null)
  const [version, setVersion] = useState(0)
  const [error, setError] = useState('')
  useEffect(() => {
    let alive = true
    Promise.all([api.run(runId), api.runSnapshots(runId)]).then(([run, snapshots]) => {
      if (!alive) return
      setDetail(run); setIndex(snapshots.items || [])
      setVersion(snapshots.items?.at(-1)?.version || 0)
    }).catch((issue) => { if (alive) setError(issue.message) })
    return () => { alive = false }
  }, [runId])
  useEffect(() => { if (index.length) api.runSnapshot(runId, version).then(setSnapshot).catch((issue) => setError(issue.message)) }, [index, runId, version])
  const state = snapshot?.state || detail?.final_state
  const summary = detail?.summary
  return <main className="replay-page" aria-labelledby="run-detail-title"><div className="replay-page-head"><div><p className="replay-eyebrow">RUN REPORT · {runId}</p><h1 id="run-detail-title">{summary?.scenario_id || 'Run details'}</h1><p className="replay-lede">{summary?.description || 'Loading saved run evidence…'}</p></div><Link className="replay-secondary-button" to="/runs">Back to run history</Link></div><p className="replay-simulation-note"><span />{SIM_NOTE}</p><ErrorLine>{error}</ErrorLine>
    {summary && <><div className="replay-metric-grid replay-report-metrics"><Metric label="Outcome" value={summary.outcome} /><Metric label="Alerts" value={summary.alerts_count} /><Metric label="Incidents" value={summary.incidents_count} /><Metric label="Actions" value={summary.actions_count} /></div><section className="replay-panel run-snapshot-panel"><div className="replay-panel-head"><div><p className="replay-eyebrow">TIME TRAVEL</p><h2>Recorded snapshots <span>{version} / {Math.max(0, index.at(-1)?.version || 0)}</span></h2></div></div><label className="replay-scrubber"><span>Scrub event history</span><input type="range" min="0" max={Math.max(0, index.at(-1)?.version || 0)} value={version} onChange={(e) => setVersion(Number(e.target.value))} /><b>Position {version}</b></label>{state && <div className="snapshot-state-grid"><Metric label="Graph hosts" value={state.graph?.hosts?.length || 0} /><Metric label="Alerts at this point" value={state.alerts?.length || 0} /><Metric label="Forecasts" value={state.forecasts?.length || 0} /><Metric label="Incidents" value={state.incidents?.length || 0} /><div className="snapshot-hosts">{(state.graph?.hosts || []).map((host) => <span key={host.host_id}><b>{host.name}</b><i>{host.state}</i></span>)}</div></div>}</section><section className="replay-panel run-data-panel"><h2>Precog metrics</h2><pre>{JSON.stringify(summary.metrics, null, 2)}</pre><h2>Forecasts and outcomes</h2>{(detail.final_state?.forecasts || []).map((forecast) => <article key={forecast.forecast_id}><b>{forecast.forecast_id}</b><span>{forecast.status}{forecast.outcome?.blocked ? ' · blocked hit' : ''}</span><p>{forecast.targets?.map((target) => `${target.rank}. ${target.host_id} ${(target.confidence * 100).toFixed(1)}%`).join(' · ')}</p></article>)}</section></>}
  </main>
}

function RunComparePage() {
  const [params] = useSearchParams()
  const [comparison, setComparison] = useState(null)
  const [error, setError] = useState('')
  const first = params.get('a') || ''
  const second = params.get('b') || ''
  useEffect(() => { if (first && second) api.compareRuns(first, second).then(setComparison).catch((issue) => setError(issue.message)) }, [first, second])
  return <main className="replay-page" aria-labelledby="run-compare-title"><div className="replay-page-head"><div><p className="replay-eyebrow">SIDE-BY-SIDE · SCRIPTED RUNS</p><h1 id="run-compare-title">Run comparison</h1><p className="replay-lede">Wall-clock fields are excluded; alert, incident, forecast, action, outcome and metric differences remain visible.</p></div><Link className="replay-secondary-button" to="/runs">Run history</Link></div><p className="replay-simulation-note"><span />{SIM_NOTE}</p><ErrorLine>{error}</ErrorLine>
    {comparison && <><div className="compare-identity"><span>{comparison.left_run_id}</span><b aria-hidden="true">↔</b><span>{comparison.right_run_id}</span><strong>{comparison.identical ? 'IDENTICAL SCRIPTED RESULT' : 'DIFFERENCES FOUND'}</strong></div><p className="replay-copy">{comparison.simulation_note}</p><div className="compare-grid">{['outcome', 'alerts', 'incidents', 'forecasts', 'actions', 'metrics'].map((key) => <section className="replay-panel compare-card" key={key}><p className="replay-eyebrow">{key.toUpperCase()}</p><h2>{key === 'metrics' ? 'Metrics' : key === 'outcome' ? `${comparison.changes.outcome.left} → ${comparison.changes.outcome.right}` : `${comparison.changes[key].left_count} → ${comparison.changes[key].right_count}`}</h2>{key === 'metrics' ? <div className="compare-metrics"><pre>{JSON.stringify(comparison.changes.metrics.left, null, 2)}</pre><pre>{JSON.stringify(comparison.changes.metrics.right, null, 2)}</pre></div> : key === 'outcome' ? <p>Run outcome comparison, including completion and error state.</p> : <><p>{comparison.changes[key].added.length} added · {comparison.changes[key].removed.length} removed</p>{comparison.changes[key].added.slice(0, 5).map((item, index) => <pre className="compare-diff-added" key={`added-${index}`}>+ {JSON.stringify(item, null, 2)}</pre>)}{comparison.changes[key].removed.slice(0, 5).map((item, index) => <pre className="compare-diff-removed" key={`removed-${index}`}>− {JSON.stringify(item, null, 2)}</pre>)}</>}</section>)}</div></>}
  </main>
}

export default function ReplayStudioApp() {
  const { pathname } = useLocation()
  if (pathname === '/replay' || pathname === '/replay/') return <StudioPage />
  if (pathname === '/scenarios/new') return <ScenarioBuilderPage scenarioId="new" />
  const edit = pathname.match(/^\/scenarios\/([^/]+)\/edit\/?$/)
  if (edit) return <ScenarioBuilderPage scenarioId={decodeURIComponent(edit[1])} />
  if (pathname === '/scenarios' || pathname === '/scenarios/') return <ScenarioLibraryPage />
  if (pathname === '/runs/compare') return <RunComparePage />
  const run = pathname.match(/^\/runs\/([^/]+)\/?$/)
  if (run) return <RunDetailPage runId={decodeURIComponent(run[1])} />
  return <RunListPage />
}

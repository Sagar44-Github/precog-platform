import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../shared/AuthContext.jsx'
import { api } from '../../shared/api.js'
import { Button, EmptyMessage, Field, PageFrame, PageHeader, ResourceNotice, useResource } from './shared.jsx'
import './replay-studio.css'

function eventTemplate(kind, seq, hosts) {
  const first = hosts[0]?.host_id || 'host-a'
  const second = hosts.find((host) => host.host_id !== first)?.host_id || 'server-b'
  const common = { seq, offset_ms: (seq - 1) * 1000, pause_for_decision: false }
  if (kind === 'attempt') return { ...common, kind, from_host: first, to_host: second, technique_id: 'T1021', note: '' }
  if (kind === 'traffic') return { ...common, kind, packets: [{ src_host: first, dst_host: second, protocol: 'TCP', dst_port: 80, size: 512, repeat: 1 }] }
  return { ...common, kind: 'technique', host: first, technique_id: 'T1046', compromise: false, note: '' }
}

function HostSelect({ label, value, hosts, onChange }) {
  return <Field label={label}><select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
    {hosts.map((host) => <option key={host.host_id} value={host.host_id}>{host.name} · {host.host_id}</option>)}
  </select></Field>
}

export default function ScenarioBuilderPage() {
  const { permissions } = useAuth()
  const [revision, setRevision] = useState(0)
  const [selected, setSelected] = useState('')
  const [detail, setDetail] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [errorText, setErrorText] = useState('')
  const [draft, setDraft] = useState({ scenario_id: 'custom-replay', description: 'A student-authored simulated event sequence.', events: [] })
  const loadScenarios = useCallback(() => api.replayScenarios(), [revision])
  const loadHosts = useCallback(() => api.assets(), [])
  const { data: scenarios, loading, error, refresh } = useResource(loadScenarios, `scenario-library:${revision}`)
  const { data: inventory } = useResource(loadHosts, 'scenario-builder-hosts')
  const hosts = inventory?.items || []
  const editable = Boolean(permissions?.can_run_replay)

  function setEvent(index, patch) {
    setDraft((current) => ({ ...current, events: current.events.map((event, eventIndex) => eventIndex === index ? { ...event, ...patch } : event) }))
  }

  function addEvent(kind) {
    setDraft((current) => ({ ...current, events: [...current.events, eventTemplate(kind, current.events.length + 1, hosts)] }))
    setMessage('')
    setErrorText('')
  }

  function removeEvent(index) {
    setDraft((current) => ({ ...current, events: current.events.filter((_, eventIndex) => eventIndex !== index).map((event, eventIndex) => ({ ...event, seq: eventIndex + 1 })) }))
  }

  async function saveScenario(event) {
    event.preventDefault()
    setBusy(true)
    setMessage('')
    setErrorText('')
    try {
      const saved = await api.saveReplayScenario(draft)
      setMessage(`Saved ${saved.scenario_id}. It is available in Replay Studio.`)
      setRevision((value) => value + 1)
      setSelected(saved.scenario_id)
      setDetail(saved)
    } catch (reason) {
      setErrorText(reason.message || 'The scenario did not pass server validation.')
    } finally { setBusy(false) }
  }

  async function inspectScenario(scenarioId) {
    setSelected(scenarioId)
    try { setDetail(await api.replayScenario(scenarioId)) }
    catch (reason) { setDetail(null); setErrorText(reason.message || 'Could not load this scenario.') }
  }

  return <PageFrame className="replay-studio-page scenario-builder-page">
    <PageHeader eyebrow="REPLAY / SCENARIO LIBRARY" title="Scenario builder" description="Compose a bounded sequence of simulated events, validate it against the replay schema and demo hosts, then save it for later rehearsals." actions={<Link className="ops-button ops-button-secondary" to="/replay">Open Replay Studio</Link>} />
    <div className="studio-simulation-note"><b>Simulation only.</b> Scenarios write scripted packet and technique events into this demo pipeline. They do not generate real traffic or contact other systems.</div>
    <div className="scenario-builder-grid">
      <section className="ops-card scenario-library-card">
        <div className="ops-card-header"><div><h3>Scenario library</h3><p>{scenarios?.length || 0} available sequences · shipped and locally saved</p></div><Button type="button" className="ops-button-secondary" onClick={() => { refresh(); setRevision((value) => value + 1) }}>Refresh</Button></div>
        <ResourceNotice loading={loading} error={error} data={scenarios} onRetry={refresh} />
        {scenarios?.length ? <div className="scenario-library-list">{scenarios.map((scenario) => <button key={scenario.scenario_id} type="button" className={`scenario-library-item${selected === scenario.scenario_id ? ' is-selected' : ''}`} onClick={() => inspectScenario(scenario.scenario_id)}>
          <span className="scenario-library-top"><b>{scenario.scenario_id}</b><span>{scenario.custom ? 'CUSTOM' : 'SHIPPED'}</span></span>
          <span>{scenario.description}</span><small>{scenario.events} events {scenario.has_decision_point ? '· decision point' : '· no decision point'}</small>
        </button>)}</div> : scenarios && <EmptyMessage title="No scenarios are loaded">Check replay module health and retry.</EmptyMessage>}
        {detail && <div className="scenario-detail-preview"><p className="ops-eyebrow">SEQUENCE PREVIEW · {detail.events.length} EVENTS</p><ol>{detail.events.map((event) => <li key={event.seq}><b>{String(event.seq).padStart(2, '0')}</b><span><strong>{event.kind}</strong><small>{event.kind === 'technique' ? `${event.host} · ${event.technique_id}` : event.kind === 'attempt' ? `${event.from_host} → ${event.to_host}` : `${event.packets.length} packet flow(s)`}</small></span></li>)}</ol></div>}
      </section>

      <section className="ops-card scenario-editor-card">
        <div className="ops-card-header"><div><h3>Build a scenario</h3><p>Each event uses an existing simulated host and a bounded event format.</p></div><span className="studio-card-tag">SERVER VALIDATED</span></div>
        {!editable ? <div className="scenario-readonly"><b>Read-only role</b><p>Viewer accounts can browse scenarios but cannot save or run a replay.</p></div> : <form className="scenario-editor" onSubmit={saveScenario}>
          <div className="scenario-meta-grid">
            <Field label="Scenario ID"><input value={draft.scenario_id} maxLength={64} onChange={(event) => setDraft((current) => ({ ...current, scenario_id: event.target.value }))} aria-label="Scenario ID" /></Field>
            <Field label="Description"><input value={draft.description} maxLength={300} onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))} aria-label="Scenario description" /></Field>
          </div>
          <div className="scenario-event-list">
            {draft.events.map((item, index) => <article className="scenario-event-card" key={`${item.seq}-${item.kind}`}>
              <header><span className="scenario-event-index">{String(item.seq).padStart(2, '0')}</span><strong>{item.kind} event</strong><Button type="button" className="ops-button-danger" onClick={() => removeEvent(index)}>Remove</Button></header>
              <div className="scenario-event-fields">
                <Field label="Offset (ms)"><input type="number" min="0" value={item.offset_ms} onChange={(event) => setEvent(index, { offset_ms: Number(event.target.value) })} aria-label={`Event ${item.seq} offset`} /></Field>
                {item.kind === 'technique' && <>
                  <HostSelect label={`Event ${item.seq} host`} value={item.host} hosts={hosts} onChange={(host) => setEvent(index, { host })} />
                  <Field label="ATT&CK technique ID"><input value={item.technique_id} maxLength={12} onChange={(event) => setEvent(index, { technique_id: event.target.value })} aria-label={`Event ${item.seq} technique`} /></Field>
                  <Field label="Analyst note"><input value={item.note || ''} maxLength={300} onChange={(event) => setEvent(index, { note: event.target.value })} aria-label={`Event ${item.seq} note`} /></Field>
                  <label className="scenario-check"><input type="checkbox" checked={Boolean(item.compromise)} onChange={(event) => setEvent(index, { compromise: event.target.checked })} /> Mark host compromised in the simulation</label>
                </>}
                {item.kind === 'attempt' && <>
                  <HostSelect label={`Event ${item.seq} from host`} value={item.from_host} hosts={hosts} onChange={(from_host) => setEvent(index, { from_host })} />
                  <HostSelect label={`Event ${item.seq} to host`} value={item.to_host} hosts={hosts} onChange={(to_host) => setEvent(index, { to_host })} />
                  <Field label="ATT&CK technique ID"><input value={item.technique_id} maxLength={12} onChange={(event) => setEvent(index, { technique_id: event.target.value })} aria-label={`Event ${item.seq} technique`} /></Field>
                  <Field label="Analyst note"><input value={item.note || ''} maxLength={300} onChange={(event) => setEvent(index, { note: event.target.value })} aria-label={`Event ${item.seq} note`} /></Field>
                </>}
                {item.kind === 'traffic' && <>
                  <HostSelect label={`Event ${item.seq} source host`} value={item.packets[0].src_host} hosts={hosts} onChange={(src_host) => setEvent(index, { packets: [{ ...item.packets[0], src_host }] })} />
                  <HostSelect label={`Event ${item.seq} destination host`} value={item.packets[0].dst_host} hosts={hosts} onChange={(dst_host) => setEvent(index, { packets: [{ ...item.packets[0], dst_host }] })} />
                  <Field label="Protocol"><select value={item.packets[0].protocol} onChange={(event) => setEvent(index, { packets: [{ ...item.packets[0], protocol: event.target.value }] })} aria-label={`Event ${item.seq} protocol`}><option>TCP</option><option>UDP</option><option>ICMP</option></select></Field>
                  <Field label="Destination port"><input type="number" min="0" max="65535" value={item.packets[0].dst_port} onChange={(event) => setEvent(index, { packets: [{ ...item.packets[0], dst_port: Number(event.target.value) }] })} aria-label={`Event ${item.seq} destination port`} /></Field>
                  <Field label="Packet size"><input type="number" min="1" max="65535" value={item.packets[0].size} onChange={(event) => setEvent(index, { packets: [{ ...item.packets[0], size: Number(event.target.value) }] })} aria-label={`Event ${item.seq} packet size`} /></Field>
                </>}
                <label className="scenario-check"><input type="checkbox" checked={Boolean(item.pause_for_decision)} onChange={(event) => setEvent(index, { pause_for_decision: event.target.checked })} /> Pause before this event for an analyst decision</label>
              </div>
            </article>)}
          </div>
          <div className="scenario-add-actions"><Button type="button" className="ops-button-secondary" onClick={() => addEvent('technique')} disabled={!hosts.length}>+ Technique</Button><Button type="button" className="ops-button-secondary" onClick={() => addEvent('attempt')} disabled={!hosts.length}>+ Host attempt</Button><Button type="button" className="ops-button-secondary" onClick={() => addEvent('traffic')} disabled={!hosts.length}>+ Traffic</Button></div>
          <details className="scenario-json-preview"><summary>Inspect scenario JSON</summary><pre>{JSON.stringify(draft, null, 2)}</pre></details>
          {errorText && <p className="ops-error" role="alert">{errorText}</p>}{message && <p className="scenario-saved-message" role="status">{message}</p>}
          <Button type="submit" disabled={busy || !draft.events.length}>{busy ? 'Validating and saving…' : 'Validate and save scenario'}</Button>
        </form>}
      </section>
    </div>
  </PageFrame>
}

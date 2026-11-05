import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { LoadingState } from '../../shared/components.jsx'
import { useWorldState } from '../../shared/usePolling.js'
import Scene3D from '../console/Scene3D.jsx'
import { buildTwinScene } from '../console/sceneModel.js'
import './twin.css'

function supportsWebGL() {
  if (typeof document === 'undefined') return false
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'))
  } catch { return false }
}

function TwinLiteMap({ model, onSelect }) {
  const x = (value) => 86 + ((value + 150) / 300) * 520
  const locations = new Map()
  model.zones.forEach((zone) => {
    const hosts = model.nodes.filter((node) => node.zone === zone.zone)
    hosts.forEach((node, index) => locations.set(node.id, { x: x(zone.x), y: 170 + (index - (hosts.length - 1) / 2) * 65 }))
  })
  const nodes = new Map(model.nodes.map((node) => [node.id, node]))
  return <div className="twin-lite-wrap"><svg className="twin-lite-map" viewBox="0 0 700 360" role="img" aria-label="Lite network topology view">
    {model.zones.map((zone) => <g key={zone.zone}>
      <rect x={x(zone.x) - 64} y="42" width="128" height="270" rx="14" className="twin-lite-zone" />
      <text x={x(zone.x)} y="68" textAnchor="middle">{zone.label}</text>
    </g>)}
    {model.links.map((link) => {
      const a = locations.get(link.source); const b = locations.get(link.target)
      if (!a || !b) return null
      return <line key={link.key} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={link.onPath ? 'twin-lite-edge is-path' : 'twin-lite-edge'} />
    })}
    {model.nodes.map((node) => <g key={node.id} role="button" tabIndex="0" aria-label={`Inspect ${node.name}, ${node.state}`} onClick={() => onSelect(node.id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(node.id) } }}>
      <circle cx={locations.get(node.id)?.x} cy={locations.get(node.id)?.y} r={Math.max(node.radius * 1.7, 8)} className={`twin-lite-host state-${node.state}`} />
      <text x={locations.get(node.id)?.x} y={(locations.get(node.id)?.y || 0) + Math.max(node.radius * 1.7, 8) + 15} textAnchor="middle">{node.name}</text>
    </g>)}
  </svg><div className="twin-lite-compact" aria-label="Host list topology">
    {model.zones.map((zone) => <section key={zone.zone}><h3>{zone.label}</h3>{model.nodes.filter((node) => node.zone === zone.zone).map((node) => <button type="button" key={node.id} onClick={() => onSelect(node.id)}><span><b>{node.name}</b><small>{node.services.length} services · estimated risk {node.risk}/10</small></span><i className={`state-${node.state}`} /> <em>{node.state}</em></button>)}</section>)}
  </div></div>
}

function HostInspector({ detail, history, onClose }) {
  if (!detail) return <aside className="twin-inspector twin-card"><p className="twin-kicker">ASSET INSPECTOR</p><h2>Select a host</h2><p className="twin-muted">Choose any node or use the host list to inspect services, simulated weaknesses and related investigation records.</p></aside>
  const host = detail.host
  return <aside className="twin-inspector twin-card" aria-label={`${host.name} inspector`}>
    <div className="twin-inspector-head"><div><p className="twin-kicker">{host.zone.replaceAll('-', ' ').toUpperCase()} · {host.host_id}</p><h2>{host.name}</h2></div><button type="button" className="twin-icon-button" onClick={onClose} aria-label="Close host inspector">×</button></div>
    <span className={`twin-state-pill state-${host.state}`}>{host.state}</span>
    <p className="twin-muted">{host.role} · {host.address || 'Demo address'}</p>
    <div className="twin-stat-grid"><div><b>{host.risk}/10</b><span>Estimated risk</span></div><div><b>{Math.round(host.criticality * 100)}%</b><span>Criticality</span></div><div><b>{host.exposure}</b><span>Exposure</span></div></div>
    <section><h3>Services</h3><div className="twin-chip-row">{host.services.length ? host.services.map((service) => <span key={service} className="twin-chip">{service}</span>) : <span className="twin-muted">No exposed services</span>}</div></section>
    <section><h3>Simulated weaknesses</h3>{host.weaknesses.length ? host.weaknesses.map((weakness) => <article className="twin-weakness" key={weakness.weakness_id}><b>{weakness.weakness_id} · {weakness.service}</b><p>{weakness.description}</p><small>SIMULATED · CVSS {weakness.cvss}</small></article>) : <p className="twin-muted">No simulated weakness listed.</p>}</section>
    <section><h3>Related records</h3><div className="twin-related-links">
      <span>{detail.alerts.length} alerts</span><span>{detail.forecasts.length} forecasts</span><span>{detail.actions.length} simulated actions</span>
      {detail.incidents.map((incident) => <Link key={incident.incident_id} to={`/incidents/${encodeURIComponent(incident.incident_id)}`}>{incident.title} ↗</Link>)}
      <Link to={`/hosts/${encodeURIComponent(host.host_id)}`}>Open asset history ↗</Link>
      <Link to={`/incidents?host=${encodeURIComponent(host.host_id)}`}>Related incidents ↗</Link>
    </div></section>
    {history?.events?.length > 0 && <section><h3>Recent host history</h3><ol className="twin-history">{history.events.slice(-4).reverse().map((event) => <li key={event.event_id}><b>{event.kind}</b><span>{event.summary}</span></li>)}</ol></section>}
    <p className="twin-basis">{detail.basis}</p>
  </aside>
}

export default function TwinPage() {
  const { state } = useWorldState()
  const [searchParams, setSearchParams] = useSearchParams()
  const [webglAvailable] = useState(supportsWebGL)
  const compactViewport = typeof window !== 'undefined' && window.innerWidth < 760
  const [topology, setTopology] = useState(null)
  const [runs, setRuns] = useState([])
  const [snapshotIndex, setSnapshotIndex] = useState([])
  const [snapshot, setSnapshot] = useState(null)
  const [selectedHost, setSelectedHost] = useState(searchParams.get('host') || '')
  const [detail, setDetail] = useState(null)
  const [history, setHistory] = useState(null)
  const [overlay, setOverlay] = useState('state')
  const [cameraPreset, setCameraPreset] = useState('isometric')
  const [displayMode, setDisplayMode] = useState(() => webglAvailable && !compactViewport ? '3d' : 'lite')
  const [runId, setRunId] = useState('')
  const [snapshotVersion, setSnapshotVersion] = useState('')
  const [pathFrom, setPathFrom] = useState('host-a')
  const [pathTo, setPathTo] = useState('db-server')
  const [paths, setPaths] = useState(null)
  const [pathIndex, setPathIndex] = useState(0)
  const [segSource, setSegSource] = useState('host-a')
  const [segFrom, setSegFrom] = useState('host-a')
  const [segTo, setSegTo] = useState('host-b')
  const [segmentation, setSegmentation] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { setSelectedHost(searchParams.get('host') || '') }, [searchParams])
  useEffect(() => {
    let alive = true
    Promise.all([api.topology(), api.runs()]).then(([map, recorded]) => {
      if (!alive) return
      setTopology(map); setRuns(recorded)
      if (recorded.length) setRunId(recorded[0].run_id)
    }).catch((reason) => { if (alive) setError(reason.message || 'Could not load the network twin.') })
    return () => { alive = false }
  }, [])
  useEffect(() => {
    if (!state?.version) return
    api.topology().then(setTopology).catch(() => {})
  }, [state?.version])
  useEffect(() => {
    if (!runId) { setSnapshotIndex([]); setSnapshot(null); return }
    let alive = true
    api.runSnapshots(runId).then((result) => {
      if (!alive) return
      setSnapshotIndex(result.items || [])
      const latest = result.items?.at(-1)
      setSnapshotVersion(latest ? String(latest.version) : '')
    }).catch(() => { if (alive) { setSnapshotIndex([]); setSnapshot(null) } })
    return () => { alive = false }
  }, [runId])
  useEffect(() => {
    if (!runId || !snapshotVersion) { setSnapshot(null); return }
    let alive = true
    api.runSnapshot(runId, snapshotVersion).then((item) => { if (alive) setSnapshot(item) }).catch(() => { if (alive) setSnapshot(null) })
    return () => { alive = false }
  }, [runId, snapshotVersion])
  useEffect(() => {
    if (!selectedHost) { setDetail(null); setHistory(null); return }
    let alive = true
    Promise.all([api.host(selectedHost), api.hostHistory(selectedHost, 100)]).then(([asset, events]) => {
      if (alive) { setDetail(asset); setHistory(events) }
    }).catch((reason) => { if (alive) { setDetail(null); setError(reason.message || 'Could not load host details.') } })
    return () => { alive = false }
  }, [selectedHost, state?.version])

  const selectedRun = runs.find((run) => run.run_id === runId)
  const viewState = snapshot?.state || state
  const activePath = paths?.paths?.[pathIndex]?.hosts || []
  const model = useMemo(() => buildTwinScene(topology, viewState, { overlay, highlightedPath: activePath }), [topology, viewState, overlay, activePath])
  const hostById = Object.fromEntries((topology?.hosts || []).map((host) => [host.host_id, host]))
  const edges = topology?.feasible_edges || []

  async function tracePath() {
    setError(''); setPaths(null)
    try { const result = await api.topologyPaths(pathFrom, pathTo, 10); setPaths(result); setPathIndex(0) }
    catch (reason) { setError(reason.message || 'Could not calculate routes.') }
  }
  async function previewSegmentation() {
    setError(''); setSegmentation(null)
    try { setSegmentation(await api.segmentationPreview(segSource, segFrom, segTo)) }
    catch (reason) { setError(reason.message || 'Could not calculate reachability.') }
  }
  function chooseHost(id) {
    setSelectedHost(id)
    const next = new URLSearchParams(searchParams)
    if (id) next.set('host', id); else next.delete('host')
    setSearchParams(next, { replace: true })
  }

  if (!topology && !error) return <div className="twin-loading"><LoadingState /></div>
  if (error && !topology) return <div className="twin-page"><div className="twin-error" role="alert">{error}</div></div>
  if (!topology) return null

  return <div className="twin-page">
    <header className="twin-page-head"><div><p className="twin-kicker">ASSET &amp; TOPOLOGY EXPLORER · READ ONLY</p><h1>Network digital twin</h1><p>Explore the six-host simulated network, trace feasible paths and inspect recorded state over time.</p></div><Link className="twin-secondary-link" to="/hosts">Asset directory <span aria-hidden="true">↗</span></Link></header>
    {error && <p className="twin-error" role="status">{error}</p>}
    <div className="twin-overview"><span><b>{topology.hosts.length.toString().padStart(2, '0')}</b> demo assets</span><span><b>{topology.zones.length.toString().padStart(2, '0')}</b> zones</span><span><b>{topology.feasible_edges.length.toString().padStart(2, '0')}</b> feasible links</span><span className="twin-estimate">Model estimates · scripted demo topology</span></div>
    <div className="twin-workbench">
      <section className="twin-map-card" aria-label="Network topology workbench">
        <div className="twin-map-toolbar">
          <div className="twin-segmented" role="group" aria-label="Network view">
            <button type="button" aria-pressed={displayMode === '3d'} onClick={() => setDisplayMode(webglAvailable && !compactViewport ? '3d' : 'lite')} disabled={!webglAvailable || compactViewport} title={compactViewport ? '3D view is available on larger screens; Lite view keeps the complete topology visible here.' : undefined}>3D view</button>
            <button type="button" aria-pressed={displayMode === 'lite'} onClick={() => setDisplayMode('lite')}>Lite view</button>
          </div>
          <label className="twin-select-label">Overlay<select aria-label="Topology overlay" value={overlay} onChange={(event) => setOverlay(event.target.value)}><option value="state">Host state</option><option value="risk">Estimated risk · size</option><option value="forecast">Forecast probability · size</option><option value="exposure">Exposure · size</option></select></label>
          {displayMode === '3d' && <label className="twin-select-label">Camera<select aria-label="Camera preset" value={cameraPreset} onChange={(event) => setCameraPreset(event.target.value)}><option value="isometric">Isometric</option><option value="top">Top</option><option value="side">Side</option></select></label>}
          <label className="twin-select-label">Focus host<select aria-label="Fly to host" value={selectedHost} onChange={(event) => chooseHost(event.target.value)}><option value="">All hosts</option>{topology.hosts.map((host) => <option key={host.host_id} value={host.host_id}>{host.name}</option>)}</select></label>
        </div>
        <div className="twin-map-viewport">
          {displayMode === '3d' ? <Scene3D model={model} mode="twin" cameraPreset={cameraPreset} focusHostId={selectedHost} onSelect={chooseHost} /> : <TwinLiteMap model={model} onSelect={chooseHost} />}
          <div className="twin-map-legend" aria-label="Map legend"><span><i className="legend-normal" />Normal</span><span><i className="legend-compromised" />Compromised</span><span><i className="legend-contained" />Contained</span><span><i className="legend-path" />Observed path</span></div>
          {displayMode === 'lite' && <p className="twin-lite-note">Accessible 2D topology view · same assets and routes</p>}
        </div>
        <div className="twin-timebar"><div><b>Time travel</b><span>{selectedRun ? `${selectedRun.scenario_id} · ${selectedRun.run_id}` : 'No recorded run selected'}</span></div>
          <select aria-label="Recorded run" value={runId} onChange={(event) => setRunId(event.target.value)}><option value="">Choose a run</option>{runs.map((run) => <option key={run.run_id} value={run.run_id}>{run.scenario_id} · {run.run_id}</option>)}</select>
          <input aria-label="Recorded snapshot" type="range" min="0" max={Math.max(snapshotIndex.length - 1, 0)} value={Math.max(snapshotIndex.findIndex((item) => String(item.version) === snapshotVersion), 0)} disabled={!snapshotIndex.length} onChange={(event) => { const item = snapshotIndex[Number(event.target.value)]; if (item) setSnapshotVersion(String(item.version)) }} />
          <span className="twin-time-value">{snapshotIndex.length ? `${snapshotIndex.findIndex((item) => String(item.version) === snapshotVersion) + 1} / ${snapshotIndex.length}` : 'No snapshots'}</span>
        </div>
        {snapshotIndex.length > 0 && <p className="twin-snapshot-caption">{snapshotIndex.find((item) => String(item.version) === snapshotVersion)?.event_kind || 'Recorded state'} · {snapshotIndex.find((item) => String(item.version) === snapshotVersion)?.captured_at || ''}</p>}
      </section>
      <HostInspector detail={detail} history={history} onClose={() => chooseHost('')} />
    </div>
    <div className="twin-tools-grid">
      <section className="twin-card"><div className="twin-card-heading"><div><p className="twin-kicker">PATH TRACER</p><h2>How can the attacker reach a host?</h2></div><span className="twin-readonly">FEASIBLE ROUTES</span></div>
        <div className="twin-form-row"><label>From<select value={pathFrom} onChange={(event) => setPathFrom(event.target.value)}>{topology.hosts.map((host) => <option key={host.host_id} value={host.host_id}>{host.name}</option>)}</select></label><label>To<select value={pathTo} onChange={(event) => setPathTo(event.target.value)}>{topology.hosts.map((host) => <option key={host.host_id} value={host.host_id}>{host.name}</option>)}</select></label><button type="button" className="twin-primary-button" onClick={tracePath}>Trace routes</button></div>
        {paths && <div className="twin-results" aria-live="polite">{paths.paths.length ? paths.paths.map((path, index) => <button type="button" key={path.hosts.join('>')} className="twin-route" aria-pressed={pathIndex === index} onClick={() => setPathIndex(index)}><span>Route {index + 1}</span><b>{path.hosts.map((id) => hostById[id]?.name || id).join(' → ')}</b><small>Model-based likelihood estimate {Math.round(path.likelihood * 100)}%</small></button>) : <p>No feasible route connects these hosts.</p>}<p className="twin-basis">{paths.basis}</p></div>}
        {!paths && <p className="twin-muted">Routes and likelihoods use the demo topology and simulated weaknesses.</p>}
      </section>
      <section className="twin-card"><div className="twin-card-heading"><div><p className="twin-kicker">SEGMENTATION PREVIEW</p><h2>Project an edge removal</h2></div><span className="twin-readonly">READ ONLY</span></div>
        <div className="twin-form-row"><label>Start from<select value={segSource} onChange={(event) => setSegSource(event.target.value)}>{topology.hosts.map((host) => <option key={host.host_id} value={host.host_id}>{host.name}</option>)}</select></label><label>Remove link<select value={`${segFrom}>${segTo}`} onChange={(event) => { const [from, to] = event.target.value.split('>'); setSegFrom(from); setSegTo(to) }}>{edges.map((edge) => <option key={`${edge.from_host}>${edge.to_host}`} value={`${edge.from_host}>${edge.to_host}`}>{hostById[edge.from_host]?.name} → {hostById[edge.to_host]?.name}</option>)}</select></label><button type="button" className="twin-primary-button" onClick={previewSegmentation}>Preview</button></div>
        {segmentation ? <div className="twin-results" aria-live="polite"><p><b>{segmentation.newly_unreachable.length}</b> hosts become unreachable in this projection.</p><div className="twin-chip-row">{segmentation.newly_unreachable.length ? segmentation.newly_unreachable.map((id) => <span className="twin-chip" key={id}>{hostById[id]?.name || id}</span>) : <span className="twin-muted">No reachability change for this source.</span>}</div><p className="twin-basis">{segmentation.basis}</p></div> : <p className="twin-muted">Try removing a feasible link to see the projected reachability change. No live topology is modified.</p>}
      </section>
    </div>
    <section className="twin-card twin-host-index"><div className="twin-card-heading"><div><p className="twin-kicker">ASSET INDEX</p><h2>Hosts in this topology</h2></div><Link to="/hosts">Full directory ↗</Link></div><div className="twin-host-list">{topology.hosts.map((host) => <button type="button" key={host.host_id} onClick={() => chooseHost(host.host_id)} className="twin-host-row"><span><b>{host.name}</b><small>{host.zone.toUpperCase()} · {host.services.length} services · {host.exposure} links</small></span><span className={`twin-state-pill state-${(viewState?.graph?.hosts?.find((item) => item.host_id === host.host_id)?.state || host.state)}`}>{viewState?.graph?.hosts?.find((item) => item.host_id === host.host_id)?.state || host.state}</span><span className="twin-risk">Risk est. {host.risk}/10</span></button>)}</div></section>
    <p className="twin-honesty">All assets, weaknesses, paths and outcomes are simulated. Risk, likelihood and forecast overlays are model-based estimates from the scripted six-host demo network; they do not indicate real-world protection.</p>
  </div>
}

export function HostsPage() {
  const [hosts, setHosts] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.topology().then((result) => setHosts(result.hosts)).catch((reason) => setError(reason.message || 'Could not load assets.')) }, [])
  return <div className="twin-page twin-directory"><header className="twin-page-head"><div><p className="twin-kicker">SIMULATED ASSET INVENTORY</p><h1>Asset directory</h1><p>Hosts, services and model-based exposure estimates from the demo topology.</p></div><Link className="twin-secondary-link" to="/twin">Open network twin ↗</Link></header>{error && <p role="alert" className="twin-error">{error}</p>}{!hosts && !error ? <LoadingState /> : <div className="twin-directory-grid">{hosts?.map((host) => <Link className="twin-directory-card" key={host.host_id} to={`/hosts/${encodeURIComponent(host.host_id)}`}><div className="twin-directory-glyph" aria-hidden="true">◇</div><p className="twin-kicker">{host.zone.toUpperCase()} · {host.host_id}</p><h2>{host.name}</h2><p>{host.role}</p><div className="twin-chip-row">{host.services.map((service) => <span className="twin-chip" key={service}>{service}</span>)}</div><footer><span>Risk estimate <b>{host.risk}/10</b></span><span>Exposure <b>{host.exposure}</b></span></footer></Link>)}</div>}<p className="twin-honesty">Demo values are simulated estimates. No real vulnerability scanning is performed.</p></div>
}

export function HostDetailPage() {
  const { id: hostId } = useParams()
  const [detail, setDetail] = useState(null)
  const [history, setHistory] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { Promise.all([api.host(hostId), api.hostHistory(hostId, 200)]).then(([asset, events]) => { setDetail(asset); setHistory(events) }).catch((reason) => setError(reason.message || 'Could not load host.')) }, [hostId])
  if (error) return <div className="twin-page"><p className="twin-error" role="alert">{error}</p><Link to="/hosts">Back to assets</Link></div>
  if (!detail) return <div className="twin-page"><LoadingState /></div>
  const host = detail.host
  return <div className="twin-page twin-host-detail"><Link className="twin-back-link" to="/hosts">← Asset directory</Link><header className="twin-page-head"><div><p className="twin-kicker">{host.zone.toUpperCase()} · {host.host_id}</p><h1>{host.name}</h1><p>{host.role} · {host.address || 'Demo asset address'}</p></div><Link className="twin-primary-link" to={`/twin?host=${encodeURIComponent(host.host_id)}`}>View in network twin ↗</Link></header>
    <div className="twin-stat-grid twin-detail-stats"><div><b>{host.state}</b><span>Simulation state</span></div><div><b>{host.risk}/10</b><span>Estimated risk</span></div><div><b>{Math.round(host.criticality * 100)}%</b><span>Criticality</span></div><div><b>{host.exposure}</b><span>Exposure count</span></div></div>
    <div className="twin-tools-grid"><section className="twin-card"><h2>Services</h2><div className="twin-chip-row">{host.services.map((service) => <span className="twin-chip" key={service}>{service}</span>)}</div><h2 className="twin-section-gap">Simulated weaknesses</h2>{host.weaknesses.map((weakness) => <article className="twin-weakness" key={weakness.weakness_id}><b>{weakness.weakness_id} · {weakness.service}</b><p>{weakness.description}</p><small>SIMULATED · CVSS {weakness.cvss}</small></article>)}</section>
      <section className="twin-card"><h2>Related work</h2><p>{detail.alerts.length} alerts · {detail.forecasts.length} forecasts · {detail.actions.length} simulated actions</p>{detail.incidents.map((incident) => <p key={incident.incident_id}><Link to={`/incidents/${encodeURIComponent(incident.incident_id)}`}>{incident.title} · {incident.status} ↗</Link></p>)}{!detail.incidents.length && <p className="twin-muted">No related incident currently recorded.</p>}<p className="twin-basis">{detail.basis}</p></section></div>
    <section className="twin-card"><div className="twin-card-heading"><div><p className="twin-kicker">RECORDED ACTIVITY</p><h2>Host history</h2></div><span>{history?.total || 0} events</span></div>{history?.events?.length ? <ol className="twin-full-history">{[...history.events].reverse().map((event) => <li key={event.event_id}><time>{event.occurred_at || 'Recorded'}</time><b>{event.kind}</b><span>{event.summary}</span>{event.run_id && <Link to={`/runs/${encodeURIComponent(event.run_id)}`}>{event.run_id} ↗</Link>}</li>)}</ol> : <p className="twin-muted">No recorded history yet.</p>}</section>
    <p className="twin-honesty">Host history and state reflect this simulated SOC session and its saved replay snapshots.</p></div>
}

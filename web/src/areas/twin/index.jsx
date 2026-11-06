import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../../shared/api.js'
import HostSearch from '../../shared/HostSearch.jsx'
import VirtualizedTable from '../../shared/VirtualizedTable.jsx'
import { LoadingState } from '../../shared/components.jsx'
import { useWorldState } from '../../shared/usePolling.js'
import Scene3D from '../console/Scene3D.jsx'
import { buildTwinScene } from '../console/sceneModel.js'
import { buildLiteLayout } from '../../shared/network3d/lite-layout.js'
import './twin.css'

function supportsWebGL() {
  if (typeof document === 'undefined') return false
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'))
  } catch { return false }
}

function TwinLiteMap({ model, onSelect }) {
  const layout = buildLiteLayout(model, 700, 360)
  return <div className="twin-lite-wrap"><svg className="twin-lite-map" viewBox="0 0 700 360" role="img" aria-label="Lite network topology view">
    {layout.zones.map((zone) => <g key={zone.zone}>
      <rect x={zone.x - zone.width / 2} y={zone.y - zone.height / 2} width={zone.width} height={zone.height} rx="12" className="twin-lite-zone" />
      <text x={zone.x} y={zone.y - zone.height / 2 + 20} textAnchor="middle">{zone.label}</text>
    </g>)}
    {layout.links.map((link) => {
      const a = link.from; const b = link.to
      if (!a || !b) return null
      return <line key={link.key} x1={a.px} y1={a.py} x2={b.px} y2={b.py} className={link.onPath ? 'twin-lite-edge is-path' : 'twin-lite-edge'} />
    })}
    {layout.nodes.map((node) => {
      const showLabel = node.isCluster || node.selected || node.state !== 'normal' || node.predicted !== null
      const radius = node.isCluster ? 18 : node.selected ? 9 : 5
      return <g key={node.id} role="button" tabIndex="0" aria-label={`Inspect ${node.name}, ${node.isCluster ? `${node.nodeCount} host zone cluster` : node.state}`}
        onClick={() => onSelect(node.id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(node.id) } }}>
        <circle cx={node.px} cy={node.py} r={radius} className={`twin-lite-host state-${node.state}`} />
        {node.isCluster && <text x={node.px} y={node.py + 4} textAnchor="middle" className="twin-cluster-count">{node.nodeCount}</text>}
        {showLabel && <text x={node.px} y={node.py + radius + 13} textAnchor="middle">{node.name}</text>}
      </g>
    })}
  </svg><div className="twin-lite-compact" aria-label="Host list topology">
    {model.zones.map((zone) => <section key={zone.zone}><h3>{zone.label}</h3>{model.nodes.filter((node) => node.zone === zone.zone).map((node) => <button type="button" key={node.id} onClick={() => onSelect(node.id)}><span><b>{node.name}</b><small>{node.isCluster ? `${node.nodeCount} hosts · tap to expand` : `${node.services.length} services · estimated risk ${node.risk}/10`}</small></span><i className={`state-${node.state}`} /> <em>{node.state}</em></button>)}</section>)}
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
      <Link to={`/containment?host=${encodeURIComponent(host.host_id)}`}>Open response playbooks ↗</Link>
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
  const [expandedZones, setExpandedZones] = useState([])
  const [showConnections, setShowConnections] = useState(false)
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
  const model = useMemo(() => buildTwinScene(topology, viewState, { overlay, highlightedPath: activePath, expandedZones, showLinks: showConnections }),
    [topology, viewState, overlay, activePath, expandedZones, showConnections])
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
    if (id?.startsWith('cluster:')) {
      const zone = decodeURIComponent(id.slice('cluster:'.length))
      setExpandedZones((zones) => zones.includes(zone) ? zones.filter((item) => item !== zone) : [...zones, zone])
      return
    }
    setSelectedHost(id)
    const next = new URLSearchParams(searchParams)
    if (id) next.set('host', id); else next.delete('host')
    setSearchParams(next, { replace: true })
  }
  function focusHost(host) {
    setExpandedZones((zones) => zones.includes(host.zone) ? zones : [...zones, host.zone])
    chooseHost(host.host_id)
  }

  useEffect(() => {
    if (!topology?.hosts?.length) return
    const ids = new Set(topology.hosts.map((host) => host.host_id))
    const fallback = topology.hosts[0].host_id
    if (!ids.has(pathFrom)) setPathFrom(fallback)
    if (!ids.has(pathTo)) setPathTo(topology.hosts.at(-1).host_id)
    if (!ids.has(segSource)) setSegSource(fallback)
    const validSegment = (from, to) => topology.feasible_edges.some((edge) => edge.from_host === from && edge.to_host === to)
    if (!validSegment(segFrom, segTo)) {
      const firstEdge = topology.feasible_edges[0]
      if (firstEdge) { setSegFrom(firstEdge.from_host); setSegTo(firstEdge.to_host) }
      else { setSegFrom(fallback); setSegTo(fallback) }
    }
  }, [topology])

  if (!topology && !error) return <div className="twin-loading"><LoadingState /></div>
  if (error && !topology) return <div className="twin-page"><div className="twin-error" role="alert">{error}</div></div>
  if (!topology) return null

  return <div className="twin-page">
    <header className="twin-page-head"><div><p className="twin-kicker">ASSET &amp; TOPOLOGY EXPLORER · READ ONLY</p><h1>Network digital twin</h1><p>Explore the active workspace topology, trace feasible paths and inspect recorded state over time.</p></div><Link className="twin-secondary-link" to="/hosts">Asset directory <span aria-hidden="true">↗</span></Link></header>
    {error && <p className="twin-error" role="status">{error}</p>}
    <div className="twin-overview"><span><b>{topology.hosts.length.toLocaleString()}</b> hosts</span><span><b>{topology.zones.length.toLocaleString()}</b> zones</span><span><b>{topology.feasible_edges.length.toLocaleString()}</b> feasible links</span><span className="twin-estimate">Model estimates · active workspace</span></div>
    <div className="twin-workbench">
      <section className="twin-map-card" aria-label="Network topology workbench">
        <div className="twin-map-toolbar">
          <div className="twin-segmented" role="group" aria-label="Network view">
            <button type="button" aria-pressed={displayMode === '3d'} onClick={() => setDisplayMode(webglAvailable && !compactViewport ? '3d' : 'lite')} disabled={!webglAvailable || compactViewport} title={compactViewport ? '3D view is available on larger screens; Lite view keeps the complete topology visible here.' : undefined}>3D view</button>
            <button type="button" aria-pressed={displayMode === 'lite'} onClick={() => setDisplayMode('lite')}>Lite view</button>
          </div>
          <label className="twin-select-label">Overlay<select aria-label="Topology overlay" value={overlay} onChange={(event) => setOverlay(event.target.value)}><option value="state">Host state</option><option value="risk">Estimated risk · size</option><option value="forecast">Forecast probability · size</option><option value="exposure">Exposure · size</option></select></label>
          {displayMode === '3d' && <label className="twin-select-label">Camera<select aria-label="Camera preset" value={cameraPreset} onChange={(event) => setCameraPreset(event.target.value)}><option value="isometric">Isometric</option><option value="top">Top</option><option value="side">Side</option></select></label>}
          <HostSearch label="Find and focus host" selectedHost={selectedHost} selectedName={detail?.host?.name || ''} onSelect={focusHost} />
          {model.lowDetail && <label className="twin-connections-toggle"><input type="checkbox" checked={showConnections} onChange={(event) => setShowConnections(event.target.checked)} /> Show individual connections</label>}
        </div>
        {model.lowDetail && <div className="twin-scale-message" role="status"><b>Clustered scale view</b><span>{model.nodes.length} visible groups · {topology.hosts.length} hosts · {topology.feasible_edges.length} feasible links</span><span>Select a zone cluster to expand it. Dense connections remain bundled until enabled.</span>{expandedZones.map((zone) => <button type="button" key={zone} onClick={() => setExpandedZones((items) => items.filter((item) => item !== zone))}>Collapse {zone}</button>)}</div>}
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
        {!paths && <p className="twin-muted">Routes and likelihoods use the active workspace topology and simulated weaknesses.</p>}
      </section>
      <section className="twin-card"><div className="twin-card-heading"><div><p className="twin-kicker">SEGMENTATION PREVIEW</p><h2>Project an edge removal</h2></div><span className="twin-readonly">READ ONLY</span></div>
        <div className="twin-form-row"><label>Start from<select value={segSource} onChange={(event) => setSegSource(event.target.value)}>{topology.hosts.map((host) => <option key={host.host_id} value={host.host_id}>{host.name}</option>)}</select></label><label>Remove link<select value={`${segFrom}>${segTo}`} onChange={(event) => { const [from, to] = event.target.value.split('>'); setSegFrom(from); setSegTo(to) }}>{edges.map((edge) => <option key={`${edge.from_host}>${edge.to_host}`} value={`${edge.from_host}>${edge.to_host}`}>{hostById[edge.from_host]?.name} → {hostById[edge.to_host]?.name}</option>)}</select></label><button type="button" className="twin-primary-button" onClick={previewSegmentation}>Preview</button></div>
        {segmentation ? <div className="twin-results" aria-live="polite"><p><b>{segmentation.newly_unreachable.length}</b> hosts become unreachable in this projection.</p><div className="twin-chip-row">{segmentation.newly_unreachable.length ? segmentation.newly_unreachable.map((id) => <span className="twin-chip" key={id}>{hostById[id]?.name || id}</span>) : <span className="twin-muted">No reachability change for this source.</span>}</div><p className="twin-basis">{segmentation.basis}</p></div> : <p className="twin-muted">Try removing a feasible link to see the projected reachability change. No live topology is modified.</p>}
      </section>
    </div>
    <section className="twin-card twin-host-index"><div className="twin-card-heading"><div><p className="twin-kicker">ASSET INDEX</p><h2>Hosts in this topology</h2></div><Link to="/hosts">Open searchable inventory ↗</Link></div><VirtualizedTable label="Active workspace hosts" headers={['Host', 'Zone', 'State', 'Risk estimate']} items={topology.hosts} totalCount={topology.hosts.length} rowHeight={58} height={Math.min(420, Math.max(174, topology.hosts.length * 58))} columns="minmax(210px, 2fr) minmax(90px, 1fr) minmax(100px, 1fr) minmax(120px, 1fr)" renderRow={(host, index, grid, rowHeight) => <div className="virtual-table-row twin-virtual-host" role="row" aria-rowindex={index + 2} key={host.host_id} style={{ gridTemplateColumns: grid, height: rowHeight }}><div role="cell"><button type="button" onClick={() => focusHost(host)}>{host.name}<small>{host.host_id}</small></button></div><div role="cell">{host.zone}</div><div role="cell"><span className={`twin-state-pill state-${viewState?.graph?.hosts?.find((item) => item.host_id === host.host_id)?.state || host.state}`}>{viewState?.graph?.hosts?.find((item) => item.host_id === host.host_id)?.state || host.state}</span></div><div role="cell">{host.risk}/10 · {host.exposure} links</div></div>} /></section>
    <p className="twin-honesty">Assets, weaknesses, paths and outcomes are simulated. Risk, likelihood and forecast overlays are model-based estimates from the active workspace; they do not indicate real-world protection.</p>
  </div>
}

export function HostsPage() {
  const [page, setPage] = useState(null)
  const [offset, setOffset] = useState(0)
  const [search, setSearch] = useState('')
  const [zone, setZone] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    let alive = true
    const timer = window.setTimeout(() => {
      api.topologySummary({ offset, limit: 60, q: search, zone }).then((result) => {
        if (alive) { setPage(result); setError('') }
      }).catch((reason) => { if (alive) setError(reason.message || 'Could not load the host inventory.') })
    }, search ? 160 : 0)
    return () => { alive = false; window.clearTimeout(timer) }
  }, [offset, search, zone])
  const zones = page?.zones || []
  return <div className="twin-page twin-directory"><header className="twin-page-head"><div><p className="twin-kicker">ACTIVE WORKSPACE INVENTORY</p><h1>Asset directory</h1><p>Search and page through hosts, services and model-based exposure estimates.</p></div><Link className="twin-secondary-link" to="/twin">Open network twin ↗</Link></header>
    {error && <p role="alert" className="twin-error">{error}</p>}
    <section className="twin-directory-tools" aria-label="Host filters"><label>Search hosts<input type="search" value={search} onChange={(event) => { setSearch(event.target.value); setOffset(0) }} placeholder="Name, host ID, zone, role or service" /></label><label>Zone<select value={zone} onChange={(event) => { setZone(event.target.value); setOffset(0) }}><option value="">All zones</option>{zones.map((item) => <option key={item.zone} value={item.zone}>{item.zone} · {item.host_count}</option>)}</select></label></section>
    {!page && !error ? <LoadingState /> : page && <><div className="twin-inventory-summary" role="status"><b>{page.total_matches.toLocaleString()}</b> matches · {page.total_hosts.toLocaleString()} hosts · {page.total_edges.toLocaleString()} feasible links</div>
      <VirtualizedTable label="Paginated host inventory" headers={['Host', 'Zone and role', 'State', 'Risk and exposure']} items={page.items} totalCount={page.total_matches} rowHeight={68} height={Math.min(544, Math.max(204, page.items.length * 68))} columns="minmax(210px, 2fr) minmax(150px, 1.5fr) minmax(110px, 1fr) minmax(140px, 1fr)" renderRow={(host, index, grid, rowHeight) => <div className="virtual-table-row twin-directory-row" role="row" aria-rowindex={page.offset + index + 2} key={host.host_id} style={{ gridTemplateColumns: grid, height: rowHeight }}><div role="cell"><Link to={`/hosts/${encodeURIComponent(host.host_id)}`}><b>{host.name}</b><small>{host.host_id} · {host.services.length} services</small></Link></div><div role="cell"><b>{host.zone}</b><small>{host.role}</small></div><div role="cell"><span className={`twin-state-pill state-${host.state}`}>{host.state}</span></div><div role="cell">{host.risk}/10 · {host.exposure} links</div></div>} />
      <nav className="twin-page-controls" aria-label="Host inventory pages"><button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - page.limit))}>Previous page</button><span>Rows {page.total_matches ? offset + 1 : 0}–{Math.min(offset + page.items.length, page.total_matches)} of {page.total_matches}</span><button type="button" disabled={page.next_offset === null} onClick={() => page.next_offset !== null && setOffset(page.next_offset)}>Next page</button></nav>
      <section className="twin-aggregate-summary"><h2>Connectivity by zone</h2><div>{page.edge_bundles.map((edge) => <span key={`${edge.from_zone}>${edge.to_zone}`}><b>{edge.from_zone} → {edge.to_zone}</b> {edge.count} links</span>)}</div></section>
    </>}
    <p className="twin-honesty">Risk and exposure are simulated estimates. No real vulnerability scan is performed.</p></div>
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

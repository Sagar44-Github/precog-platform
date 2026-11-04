import { lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Navigate, Link } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { useWorldState } from '../../shared/usePolling.js'
import { LoadingState, StaleBanner } from '../../shared/components.jsx'
import LiteNetworkScene from '../../shared/network3d/LiteNetworkScene.jsx'
import { autoViewMode, supportsWebGL } from '../../shared/network3d/camera-presets.js'
import { buildLiteLayout } from '../../shared/network3d/lite-layout.js'
import { downloadLitePng } from '../../shared/network3d/lite-export.js'
import { buildScene } from './sceneModel.js'
import './topology-explorer.css'

const Scene3D = lazy(() => import('../../shared/network3d/Scene3D.jsx'))

const prefersReducedMotion = () => typeof window !== 'undefined' && (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || false)

function MiniMap({ model, selectedHostId, onSelect }) {
  const layout = buildLiteLayout(model, 260, 160)
  return <svg className="topology-minimap" viewBox="0 0 260 160" role="img" aria-label="Topology minimap">
    {layout.zones.map((zone) => <line key={zone.zone} className="topology-minimap-zone" x1={zone.x} y1="14" x2={zone.x} y2="146" />)}
    {layout.links.map((edge, index) => <line key={edge.key || index} className={`topology-minimap-edge${edge.onPath ? ' is-on-path' : ''}`} x1={edge.from.px} y1={edge.from.py} x2={edge.to.px} y2={edge.to.py} />)}
    {layout.nodes.map((node) => <circle key={node.id} className={`topology-minimap-host state-${node.state}${selectedHostId === node.id ? ' is-selected' : ''}`} cx={node.px} cy={node.py} r="5" role="button" tabIndex="0" aria-label={`Select ${node.name}`} onClick={() => onSelect(node.id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(node.id) } }} />)}
  </svg>
}

export default function TopologyExplorerPage() {
  const { state, stale, loggedOut, error } = useWorldState()
  const [assets, setAssets] = useState([])
  const [snapshots, setSnapshots] = useState([])
  const [snapshotIndex, setSnapshotIndex] = useState(-1)
  const [selectedHostId, setSelectedHostId] = useState(null)
  const [focusHostId, setFocusHostId] = useState(null)
  const [overlay, setOverlay] = useState('risk')
  const [cameraPreset, setCameraPreset] = useState('isometric')
  const [viewMode, setViewMode] = useState('auto')
  const [viewportWidth, setViewportWidth] = useState(() => typeof window === 'undefined' ? 1440 : window.innerWidth)
  const [webglAvailable, setWebglAvailable] = useState(() => supportsWebGL())
  const [quality, setQuality] = useState('standard')
  const [loadError, setLoadError] = useState('')
  const graphRef = useRef(null)

  useEffect(() => {
    let alive = true
    const refresh = () => {
      Promise.all([api.assets(), api.timeTravel({ limit: 200 })]).then(([inventory, history]) => {
        if (!alive) return
        setAssets(inventory.items || [])
        setSnapshots(Array.isArray(history) ? history : history.snapshots || [])
        setLoadError('')
      }).catch((reason) => { if (alive) setLoadError(reason.message || 'Topology data could not be refreshed.') })
    }
    refresh()
    const timer = window.setInterval(refresh, 2500)
    const onResize = () => setViewportWidth(window.innerWidth)
    window.addEventListener('resize', onResize)
    return () => { alive = false; window.clearInterval(timer); window.removeEventListener('resize', onResize) }
  }, [])

  useEffect(() => {
    if (!state?.graph?.hosts?.length) return
    if (!selectedHostId || !state.graph.hosts.some((host) => host.host_id === selectedHostId)) setSelectedHostId(state.graph.hosts[0].host_id)
  }, [state?.version])

  const selectedSnapshot = snapshotIndex >= 0 ? snapshots[snapshotIndex] || null : null
  const viewState = selectedSnapshot || state
  const model = useMemo(() => buildScene(viewState, assets, { selectedHostId, overlay }), [viewState?.version, selectedSnapshot?.version, assets, selectedHostId, overlay])
  const pendingForecast = viewState?.forecast?.status === 'pending'
  const autoMode = autoViewMode({ width: viewportWidth, reducedMotion: prefersReducedMotion(), webgl: webglAvailable })
  const actualMode = viewMode === 'auto' ? autoMode : viewMode === '3d' && webglAvailable && viewportWidth >= 1024 ? '3d' : 'lite'
  const selectedNode = model.nodes.find((node) => node.id === selectedHostId)
  const selectedAsset = assets.find((asset) => asset.host_id === selectedHostId)

  const handleQuality = useCallback((next) => setQuality(next), [])
  const handleGraph = useCallback((graph) => { graphRef.current = graph }, [])
  const selectHost = useCallback((hostId) => { setSelectedHostId(hostId); setFocusHostId(hostId) }, [])

  if (loggedOut) return <Navigate to="/login" replace />
  const pageHeading = <header className="topology-page-heading">
    <div><p className="ops-eyebrow">NETWORK / TOPOLOGY EXPLORER</p><h2>Topology explorer</h2><p className="topology-description">Inspect the simulated attack surface, forecast field, and host state across time.</p></div>
    <div className="topology-heading-meta"><span className="topology-sim-label">SIMULATION ONLY</span><Link className="ops-button ops-button-secondary" to="/console">Live console</Link></div>
  </header>
  if (!state) return <main className="topology-page"><StaleBanner stale={stale} />{pageHeading}{error ? <div className="topology-error" role="alert"><b>Topology unavailable</b><span>{error}</span><Link to="/console">Return to live console</Link></div> : <div className="topology-loading"><LoadingState /></div>}</main>

  function downloadSnapshot() {
    if (actualMode === '3d') {
      const canvas = graphRef.current?.renderer?.()?.domElement
      if (!canvas) { setLoadError('The 3D scene is still preparing. Try the export again in a moment.'); return }
      const anchor = document.createElement('a')
      anchor.download = 'precog-topology.png'
      anchor.href = canvas.toDataURL('image/png')
      anchor.click()
      return
    }
    try { downloadLitePng(model) } catch (reason) { setLoadError(reason.message || 'PNG export failed.') }
  }

  return <main className="topology-page">
    <StaleBanner stale={stale} />
    {pageHeading}
    {loadError && <p className="topology-inline-error" role="status">{loadError}</p>}
    <div className="topology-toolbar" aria-label="Topology view controls">
      <div className="topology-control-group" aria-label="View mode">
        {['auto', '3d', 'lite'].map((mode) => <button type="button" key={mode} className={viewMode === mode ? 'is-active' : ''} aria-pressed={viewMode === mode} onClick={() => setViewMode(mode)}>{mode === 'auto' ? 'Auto' : mode === '3d' ? '3D' : 'Lite'}</button>)}
      </div>
      <label className="topology-select-label"><span>Heat overlay</span><select value={overlay} onChange={(event) => setOverlay(event.target.value)}><option value="risk">Simulated risk</option><option value="forecast">Forecast probability</option><option value="weakness">Simulated weaknesses</option></select></label>
      <div className="topology-control-group topology-camera-controls" aria-label="Camera preset">
        {['isometric', 'top', 'side'].map((preset) => <button type="button" key={preset} className={cameraPreset === preset ? 'is-active' : ''} aria-pressed={cameraPreset === preset} onClick={() => { setFocusHostId(null); setCameraPreset(preset) }}>{preset}</button>)}
      </div>
      <button type="button" className="ops-button ops-button-secondary topology-export" onClick={downloadSnapshot}>Export PNG</button>
      <span className="topology-quality" role="status">{actualMode === 'lite' ? `${autoMode === 'lite' ? 'Auto' : 'Selected'} · Lite view` : `3D · ${quality === 'reduced' ? 'quality reduced below 40 fps' : 'quality standard'}`}</span>
    </div>

    <div className="topology-workspace">
      <section className={`topology-stage topology-stage-${actualMode}`} aria-label="Network topology">
        <div className="topology-stage-heading"><div><b>{selectedSnapshot ? 'Historical topology' : 'Live topology'}</b><span>{model.nodes.length} hosts · {model.links.length} connections · {Object.keys(viewState?.graph?.hosts?.reduce((zones, host) => ({ ...zones, [host.zone]: true }), {}) || {}).length} zones</span></div><span>{viewState?.replay?.scenario_id || 'No active scenario'} · {viewState?.replay?.state || 'idle'}</span></div>
        <div className="topology-canvas-wrap">
          {actualMode === '3d' ? <Scene3D model={model} pendingForecast={pendingForecast} selectedHostId={selectedHostId} focusHostId={focusHostId} cameraPreset={cameraPreset} onSelect={selectHost} onReady={handleGraph} onQualityChange={handleQuality} autoRotate={false} /> : <LiteNetworkScene model={model} selectedHostId={selectedHostId} onSelect={selectHost} />}
          {actualMode === '3d' && <div className="topology-view-cube" aria-label="Camera view cube">{['isometric', 'top', 'side'].map((preset) => <button type="button" key={preset} aria-label={`${preset} camera view`} aria-pressed={cameraPreset === preset} onClick={() => { setFocusHostId(null); setCameraPreset(preset) }}>{preset.slice(0, 1).toUpperCase()}</button>)}</div>}
          {actualMode === '3d' && <div className="topology-minimap-wrap"><span>MINIMAP</span><MiniMap model={model} selectedHostId={selectedHostId} onSelect={selectHost} /></div>}
          <div className="topology-legend" aria-label="Topology legend"><span><i className="state-normal" /> Normal</span><span><i className="state-compromised" /> Compromised</span><span><i className="state-contained" /> Contained</span><span><i className="legend-forecast" /> Forecast</span></div>
        </div>
      </section>

      <aside className="topology-inspector">
        <section className="topology-inspector-card"><p className="ops-eyebrow">SELECTED ASSET</p>{selectedNode ? <>
          <h3>{selectedNode.name}</h3><p className="topology-host-role">{selectedAsset?.role || 'Demo network host'} · {selectedNode.zone} zone</p>
          <div className="topology-state-line"><span className={`topology-state-square state-${selectedNode.state}`} />{selectedNode.state}</div>
          <dl className="topology-asset-stats"><div><dt>Risk score</dt><dd>{Math.round(selectedNode.risk)}/100</dd></div><div><dt>Simulated weaknesses</dt><dd>{selectedNode.weaknessCount}</dd></div><div><dt>Forecast confidence</dt><dd>{selectedNode.predicted === null ? '—' : `${selectedNode.predicted}%`}</dd></div><div><dt>Criticality</dt><dd>{selectedAsset ? `${Math.round(selectedAsset.criticality * 100)}%` : '—'}</dd></div></dl>
          {selectedAsset?.weaknesses?.length > 0 && <p className="topology-synthetic-note">{selectedAsset.weaknesses.length} synthetic DEMO record(s); no real vulnerability scan was performed.</p>}
        </> : <p className="topology-empty">Select a host in the map or minimap.</p>}</section>
        <section className="topology-inspector-card"><div className="topology-inspector-title"><div><p className="ops-eyebrow">NETWORK OVERVIEW</p><h3>Mini-map</h3></div></div><MiniMap model={model} selectedHostId={selectedHostId} onSelect={selectHost} /><p className="topology-help">Select a marker to focus it in the scene. Dashed rings indicate forecast candidates.</p></section>
      </aside>
    </div>

    <section className="topology-history"><div className="topology-history-heading"><div><p className="ops-eyebrow">REPLAY HISTORY</p><h3>Time travel</h3><p>Move through read-only world snapshots. This does not change or resume the replay.</p></div><button type="button" className="ops-button ops-button-secondary" aria-pressed={snapshotIndex < 0} onClick={() => setSnapshotIndex(-1)}>Live state</button></div>
      {snapshots.length ? <><input aria-label="Topology time travel" className="topology-history-range" type="range" min="0" max={Math.max(0, snapshots.length - 1)} value={snapshotIndex < 0 ? Math.max(0, snapshots.length - 1) : Math.min(snapshotIndex, snapshots.length - 1)} onChange={(event) => setSnapshotIndex(Number(event.target.value))} /><div className="topology-history-meta"><span>{snapshots.length} captured snapshots</span><span>{selectedSnapshot ? `v${selectedSnapshot.version} · ${selectedSnapshot.captured_at}` : 'Live state'}</span></div></> : <p className="topology-help">Snapshots appear when the shared world state changes.</p>}
    </section>
  </main>
}

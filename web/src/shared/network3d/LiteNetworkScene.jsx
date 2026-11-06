import { buildLiteLayout } from './lite-layout.js'

function nodeShape(node, point) {
  if (node.isCluster) return <circle className={`lite-host-body state-${node.state}`} cx={point.px} cy={point.py} r="18" />
  if (node.state === 'compromised') {
    return <polygon className="lite-host-body state-compromised" points={`${point.px},${point.py - 13} ${point.px + 13},${point.py} ${point.px},${point.py + 13} ${point.px - 13},${point.py}`} />
  }
  if (node.state === 'contained') {
    return <rect className="lite-host-body state-contained" x={point.px - 11} y={point.py - 11} width="22" height="22" />
  }
  return <circle className="lite-host-body state-normal" cx={point.px} cy={point.py} r="10" />
}

export default function LiteNetworkScene({ model, onSelect, selectedHostId }) {
  const layout = buildLiteLayout(model)
  return <div className="lite-network-wrap">
    <svg className="lite-network-svg" viewBox="0 0 1000 620" role="img" aria-labelledby="lite-topology-title lite-topology-desc">
      <title id="lite-topology-title">Simulated network topology</title>
      <desc id="lite-topology-desc">A two-dimensional, keyboard-accessible map of hosts, connections, state, and forecast confidence.</desc>
      <rect className="lite-map-frame" x="18" y="20" width="964" height="580" />
      {layout.zones.map((zone) => <g key={zone.zone}>
        <rect className="lite-zone" x={zone.x - zone.width / 2} y={zone.y - zone.height / 2} width={zone.width} height={zone.height} rx="9" />
        <text className="lite-zone-label" x={zone.x} y={zone.y - zone.height / 2 + 18} textAnchor="middle">{zone.label || zone.zone.toUpperCase()}</text>
      </g>)}
      {layout.links.map((link, index) => <line key={link.key || index} className={`lite-edge${link.onPath ? ' is-on-path' : ''}`} x1={link.from.px} y1={link.from.py} x2={link.to.px} y2={link.to.py} />)}
      {layout.nodes.map((point) => <g key={point.id} className={`lite-host${selectedHostId === point.id ? ' is-selected' : ''}`} role="button" tabIndex="0" aria-label={`${point.name}, ${point.isCluster ? `${point.nodeCount} host cluster` : point.state}, ${point.risk || 0} risk out of 100${point.predicted === null ? '' : `, forecast ${point.predicted} percent`}`} onClick={() => onSelect?.(point.id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect?.(point.id) } }}>
        {!model.lowDetail && !point.isCluster && (point.overlay === 'risk' || point.overlay === 'weakness') && <circle className={`lite-heat-ring overlay-${point.overlay}`} cx={point.px} cy={point.py} r="18" style={{ opacity: point.overlay === 'risk' ? Math.max(0.16, Math.min(0.8, (point.risk || 0) / 100)) : Math.max(0.16, Math.min(0.8, (point.weaknessCount || 0) / 4)) }} />}
        {point.predicted !== null && <circle className="lite-forecast-ring" cx={point.px} cy={point.py} r="21" />}
        {nodeShape(point, point)}
        {point.isCluster && <text className="lite-cluster-count" x={point.px} y={point.py + 4} textAnchor="middle">{point.nodeCount}</text>}
        {point.predicted !== null && <text className="lite-forecast-label" x={point.px + 18} y={point.py - 16}>{point.predicted}%</text>}
        {(point.isCluster || point.id === selectedHostId || point.state !== 'normal' || point.predicted !== null) && <text className="lite-host-name" x={point.px} y={point.py + (point.isCluster ? 32 : 25)} textAnchor="middle">{point.name}</text>}
        {!point.isCluster && point.id === selectedHostId && <text className={`lite-host-state state-${point.state}`} x={point.px} y={point.py + 40} textAnchor="middle">{point.state.toUpperCase()}</text>}
      </g>)}
    </svg>
    <div className="lite-host-list" aria-label="Network host list">
      {layout.nodes.map((node) => <button type="button" key={node.id} className={`lite-host-list-item state-${node.state}${selectedHostId === node.id ? ' is-selected' : ''}`} onClick={() => onSelect?.(node.id)}>
        <span>{node.name}</span><small>{node.isCluster ? `${node.nodeCount} hosts · select to expand` : `${node.state} · risk ${Math.round(node.risk || 0)}${node.predicted === null ? '' : ` · forecast ${node.predicted}%`}`}</small>
      </button>)}
    </div>
  </div>
}

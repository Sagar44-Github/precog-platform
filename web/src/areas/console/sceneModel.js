// The 3D scene as plain data (owner: VIZ). Scene3D.jsx draws it; everything decided here can be tested without a graphics card.
// Shapes and sizes follow the UI/UX brief, Section 9.2.

export const ZONE_X = { user: -120, dmz: 0, internal: 120 }
export const NODE_STYLE = {
  normal: { shape: 'sphere', radius: 4, colorVar: '--state-normal' },
  compromised: { shape: 'octahedron', radius: 6, colorVar: '--state-compromised' },
  contained: { shape: 'cube', radius: 8, colorVar: '--state-contained' },
}

/** A fixed, calm layout: zones side by side, hosts of one zone spread up and back. No physics, so nothing jitters. */
export function layoutFor(zone, indexInZone, countInZone) {
  const spread = (indexInZone - (countInZone - 1) / 2)
  return { x: ZONE_X[zone] ?? 0, y: spread * 48, z: spread * -30 }
}

export function pulseScale(elapsedMs) {
  if (elapsedMs <= 0 || elapsedMs >= 600) return 1
  const half = 300
  return elapsedMs < half ? 1 + 0.6 * (elapsedMs / half) : 1.6 - 0.6 * ((elapsedMs - half) / half)
}

export const coneWidth = (confidence) => 0.6 + confidence * 2.4
export const coneOpacity = (confidence) => 0.05 + confidence * 0.18

export function buildScene(state, assets = [], options = {}) {
  if (!state || !state.graph) return { nodes: [], links: [], cones: [], zones: [] }
  const hosts = state.graph.hosts
  const assetList = Array.isArray(assets) ? assets : (assets?.items || [])
  const assetById = Object.fromEntries(assetList.map((asset) => [asset.host_id, asset]))
  const perZone = {}
  hosts.forEach((h) => { perZone[h.zone] = (perZone[h.zone] || 0) + 1 })
  const seen = {}
  const forecast = state.forecast && state.forecast.status === 'pending' ? state.forecast : null
  const predicted = {}
  if (forecast) forecast.targets.forEach((t) => { predicted[t.host_id] = Math.round(t.confidence * 100) })
  const path = state.graph.compromised_path
  const onPath = (a, b) => path.some((p, i) => p === a && path[i + 1] === b)

  const nodes = hosts.map((h) => {
    const index = seen[h.zone] || 0
    seen[h.zone] = index + 1
    const style = NODE_STYLE[h.state] || NODE_STYLE.normal
    const asset = assetById[h.host_id] || {}
    return { id: h.host_id, name: h.name, zone: h.zone, state: h.state, ...style, ...layoutFor(h.zone, index, perZone[h.zone]),
             role: asset.role || '', risk: Number(asset.risk_score) || 0,
             weaknessCount: Array.isArray(asset.weaknesses) ? asset.weaknesses.length : 0,
             predicted: predicted[h.host_id] ?? null, selected: h.host_id === options.selectedHostId,
             overlay: options.overlay || 'risk' }
  })
  const links = state.graph.edges.map((e) => ({ key: `${e.from_host}>${e.to_host}`, source: e.from_host, target: e.to_host, onPath: onPath(e.from_host, e.to_host) }))
  const cones = forecast ? forecast.targets.map((t) => ({ from: forecast.from_host, to: t.host_id, confidence: t.confidence,
                                                         width: coneWidth(t.confidence), opacity: coneOpacity(t.confidence) })) : []
  const zones = Object.keys(perZone).map((zone) => ({ zone, hostIds: hosts.filter((h) => h.zone === zone).map((h) => h.host_id) }))
  return { nodes, links, cones, zones }
}

const ZONE_ORDER = ['user', 'dmz', 'internal']
const ZONE_X_TWIN = { user: -150, dmz: 0, internal: 150 }

export function riskScale(risk) {
  const value = Number.isFinite(Number(risk)) ? Number(risk) : 0
  return 4 + Math.max(0, Math.min(10, value)) * 0.45
}

export function exposureScale(exposure) {
  const value = Number.isFinite(Number(exposure)) ? Number(exposure) : 0
  return 4 + Math.max(0, Math.min(10, value)) * 0.45
}

export function forecastScale(probability) {
  const value = Number.isFinite(Number(probability)) ? Number(probability) : 0
  return 4 + Math.max(0, Math.min(1, value)) * 5
}

/** Build the twin from static topology plus either live state or a recorded snapshot. */
export function buildTwinScene(topology, state, { overlay = 'state', highlightedPath = [] } = {}) {
  if (!topology || !Array.isArray(topology.hosts)) return { nodes: [], links: [], cones: [], zones: [] }
  const snapshotHosts = new Map((state?.graph?.hosts || []).map((host) => [host.host_id, host]))
  const forecasts = state?.forecast?.targets || state?.forecasts?.at?.(-1)?.targets || []
  const predicted = new Map(forecasts.map((item) => [item.host_id, Number(item.confidence) || 0]))
  const zones = topology.zones || []
  const perZone = new Map(zones.map((zone) => [zone.zone, topology.hosts.filter((host) => host.zone === zone.zone)]))
  const nodes = topology.hosts.map((asset) => {
    const zoneHosts = perZone.get(asset.zone) || []
    const index = zoneHosts.findIndex((host) => host.host_id === asset.host_id)
    const spread = index - (zoneHosts.length - 1) / 2
    const liveHost = snapshotHosts.get(asset.host_id)
    const hostState = liveHost?.state || asset.state || 'normal'
    const probability = predicted.get(asset.host_id) ?? null
    const base = NODE_STYLE[hostState] || NODE_STYLE.normal
    const radius = overlay === 'risk' ? riskScale(asset.risk)
      : overlay === 'exposure' ? exposureScale(asset.exposure)
        : overlay === 'forecast' && probability !== null ? forecastScale(probability) : base.radius * 1.6
    return {
      id: asset.host_id, name: asset.name, zone: asset.zone, state: hostState, ...base,
      radius, x: ZONE_X_TWIN[asset.zone] ?? (ZONE_ORDER.indexOf(asset.zone) * 150),
      y: spread * 32 + 12, z: spread * -28,
      risk: asset.risk, exposure: asset.exposure, criticality: asset.criticality,
      services: asset.services || [], weaknesses: asset.weaknesses || [], twin: true,
      predicted: probability === null ? null : Math.round(probability * 100), overlay,
    }
  })
  const path = highlightedPath.length ? highlightedPath : topology.compromised_path || []
  const onPath = (a, b) => path.some((host, index) => host === a && path[index + 1] === b)
  const links = (topology.feasible_edges || []).map((edge) => ({
    key: `${edge.from_host}>${edge.to_host}`, source: edge.from_host, target: edge.to_host,
    onPath: onPath(edge.from_host, edge.to_host), likelihood: edge.likelihood,
  }))
  const zoneModels = zones.map((zone, index) => ({
    zone: zone.zone, label: zone.zone.replaceAll('-', ' ').toUpperCase(),
    hostIds: zone.host_ids || [], x: ZONE_X_TWIN[zone.zone] ?? ((index - 1) * 150),
  }))
  return { nodes, links, cones: [], zones: zoneModels }
}

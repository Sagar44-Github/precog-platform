// Scene transforms are plain data so large-network layout and LOD stay testable without WebGL.

export const ZONE_X = { user: -120, dmz: 0, internal: 120 }
export const NODE_STYLE = {
  normal: { shape: 'sphere', radius: 4, colorVar: '--state-normal' },
  compromised: { shape: 'octahedron', radius: 6, colorVar: '--state-compromised' },
  contained: { shape: 'cube', radius: 8, colorVar: '--state-contained' },
}

export const CLUSTER_THRESHOLD = 100

export function layoutFor(zone, indexInZone, countInZone, zoneIndex = null, zoneCount = 3) {
  const columns = Math.max(1, Math.ceil(Math.sqrt(countInZone)))
  const rows = Math.max(1, Math.ceil(countInZone / columns))
  const column = indexInZone % columns
  const row = Math.floor(indexInZone / columns)
  const spacing = countInZone > 40 ? 22 : 34
  const x = zoneIndex === null
    ? (ZONE_X[zone] ?? 0)
    : (zoneIndex - (zoneCount - 1) / 2) * Math.max(280, columns * spacing + 80)
  return {
    x: x + (column - (columns - 1) / 2) * spacing,
    y: countInZone > 1 ? ((indexInZone * 17) % 3 - 1) * 5 : 0,
    z: (row - (rows - 1) / 2) * spacing,
  }
}

export function pulseScale(elapsedMs) {
  if (elapsedMs <= 0 || elapsedMs >= 600) return 1
  const half = 300
  return elapsedMs < half ? 1 + 0.6 * (elapsedMs / half) : 1.6 - 0.6 * ((elapsedMs - half) / half)
}

export const coneWidth = (confidence) => 0.6 + confidence * 2.4
export const coneOpacity = (confidence) => 0.05 + confidence * 0.18

function lowerDetail(nodes, links, zones, { expandedZones = [], showLinks = false, forceClusters = false } = {}) {
  if (!nodes.length) return { nodes, links, zones, lowDetail: false }
  const large = forceClusters || nodes.length >= CLUSTER_THRESHOLD
  const expanded = new Set(expandedZones)
  const perZone = new Map()
  nodes.forEach((node) => {
    if (!perZone.has(node.zone)) perZone.set(node.zone, [])
    perZone.get(node.zone).push(node)
  })
  const preferredOrder = ['user', 'dmz', 'internal']
  const zoneNames = [...perZone.keys()].sort((left, right) => {
    const leftIndex = preferredOrder.indexOf(left)
    const rightIndex = preferredOrder.indexOf(right)
    if (leftIndex >= 0 || rightIndex >= 0) return (leftIndex < 0 ? 99 : leftIndex) - (rightIndex < 0 ? 99 : rightIndex)
    return left.localeCompare(right)
  })
  const zoneByHost = new Map()
  const displayNodes = []
  for (const [zoneIndex, zone] of zoneNames.entries()) {
    const hosts = perZone.get(zone)
    if (large && !expanded.has(zone)) {
      const counts = { normal: 0, compromised: 0, contained: 0 }
      hosts.forEach((host) => { counts[host.state] = (counts[host.state] || 0) + 1 })
      const state = counts.compromised ? 'compromised' : counts.contained ? 'contained' : 'normal'
      const id = `cluster:${encodeURIComponent(zone)}`
      displayNodes.push({
        ...NODE_STYLE[state], id, name: `${zone.replaceAll('-', ' ')} · ${hosts.length}`,
        zone, state, isCluster: true, nodeCount: hosts.length, stateCounts: counts,
        role: `${hosts.length} hosts · select to expand`, risk: hosts.reduce((sum, host) => sum + (Number(host.risk) || 0), 0) / hosts.length,
        weaknessCount: hosts.reduce((sum, host) => sum + (Number(host.weaknessCount) || 0), 0),
        selected: false, predicted: null, radius: 12 + Math.min(12, Math.log2(hosts.length + 1) * 2),
        ...layoutFor(zone, 0, 1, zoneIndex, zoneNames.length),
      })
      hosts.forEach((host) => zoneByHost.set(host.id, id))
    } else {
      hosts.forEach((host, index) => {
        displayNodes.push({ ...host, ...layoutFor(zone, index, hosts.length, zoneIndex, zoneNames.length) })
        zoneByHost.set(host.id, host.id)
      })
    }
  }
  const bundled = new Map()
  for (const link of links) {
    const sourceId = zoneByHost.get(link.source)
    const targetId = zoneByHost.get(link.target)
    if (!sourceId || !targetId || sourceId === targetId) continue
    if (large && !showLinks) {
      const sourceIsCluster = sourceId.startsWith('cluster:')
      const targetIsCluster = targetId.startsWith('cluster:')
      if (!(sourceIsCluster && targetIsCluster) && !link.onPath) continue
    }
    const key = `${sourceId}>${targetId}`
    const current = bundled.get(key)
    if (current) {
      current.count += Number(link.count) || 1
      current.onPath ||= Boolean(link.onPath)
      current.visible ||= link.visible !== false
    } else bundled.set(key, { ...link, key, source: sourceId, target: targetId, count: Number(link.count) || 1 })
  }
  return {
    nodes: displayNodes,
    links: [...bundled.values()],
    zones: zoneNames.map((zone) => ({ zone, hostIds: perZone.get(zone).map((host) => host.id) })),
    lowDetail: large,
  }
}

export function buildScene(state, assets = [], options = {}) {
  if (!state || !state.graph) return { nodes: [], links: [], cones: [], zones: [], lowDetail: false }
  const hosts = state.graph.hosts
  const assetList = Array.isArray(assets) ? assets : (assets?.items || [])
  const assetById = Object.fromEntries(assetList.map((asset) => [asset.host_id, asset]))
  const forecast = state.forecast && state.forecast.status === 'pending' ? state.forecast : null
  const predicted = {}
  if (forecast) forecast.targets.forEach((target) => { predicted[target.host_id] = Math.round(target.confidence * 100) })
  const path = state.graph.compromised_path
  const onPath = (source, target) => path.some((host, index) => host === source && path[index + 1] === target)
  const nodes = hosts.map((host) => {
    const style = NODE_STYLE[host.state] || NODE_STYLE.normal
    const asset = assetById[host.host_id] || {}
    return { id: host.host_id, name: host.name, zone: host.zone, state: host.state, ...style,
      role: asset.role || '', risk: Number(asset.risk_score) || 0,
      weaknessCount: Array.isArray(asset.weaknesses) ? asset.weaknesses.length : 0,
      predicted: predicted[host.host_id] ?? null, selected: host.host_id === options.selectedHostId,
      overlay: options.overlay || 'risk' }
  })
  const links = state.graph.edges.map((edge) => ({ key: `${edge.from_host}>${edge.to_host}`, source: edge.from_host,
    target: edge.to_host, onPath: onPath(edge.from_host, edge.to_host), visible: options.showLinks || hosts.length < CLUSTER_THRESHOLD }))
  const scaled = lowerDetail(nodes, links, [], options)
  const cones = forecast ? forecast.targets.map((target) => ({ from: forecast.from_host, to: target.host_id,
    confidence: target.confidence, width: coneWidth(target.confidence), opacity: coneOpacity(target.confidence) })) : []
  return { ...scaled, cones }
}

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
export function buildTwinScene(topology, state, { overlay = 'state', highlightedPath = [], ...options } = {}) {
  if (!topology || !Array.isArray(topology.hosts)) return { nodes: [], links: [], cones: [], zones: [], lowDetail: false }
  const snapshotHosts = new Map((state?.graph?.hosts || []).map((host) => [host.host_id, host]))
  const forecasts = state?.forecast?.targets || state?.forecasts?.at?.(-1)?.targets || []
  const predicted = new Map(forecasts.map((item) => [item.host_id, Number(item.confidence) || 0]))
  const hostIdsByZone = new Map()
  for (const host of topology.hosts) {
    if (!hostIdsByZone.has(host.zone)) hostIdsByZone.set(host.zone, [])
    hostIdsByZone.get(host.zone).push(host.host_id)
  }
  const zones = topology.zones || []
  const nodes = topology.hosts.map((asset) => {
    const liveHost = snapshotHosts.get(asset.host_id)
    const hostState = liveHost?.state || asset.state || 'normal'
    const probability = predicted.get(asset.host_id) ?? null
    const base = NODE_STYLE[hostState] || NODE_STYLE.normal
    const radius = overlay === 'risk' ? riskScale(asset.risk)
      : overlay === 'exposure' ? exposureScale(asset.exposure)
        : overlay === 'forecast' && probability !== null ? forecastScale(probability) : base.radius * 1.6
    return { id: asset.host_id, name: asset.name, zone: asset.zone, state: hostState, ...base,
      radius, risk: asset.risk, exposure: asset.exposure, criticality: asset.criticality,
      services: asset.services || [], weaknesses: asset.weaknesses || [], twin: true,
      predicted: probability === null ? null : Math.round(probability * 100), overlay,
      role: asset.role || '', weaknessCount: (asset.weaknesses || []).length }
  })
  const path = highlightedPath.length ? highlightedPath : topology.compromised_path || []
  const onPath = (source, target) => path.some((host, index) => host === source && path[index + 1] === target)
  const links = (topology.feasible_edges || []).map((edge) => ({
    key: `${edge.from_host}>${edge.to_host}`, source: edge.from_host, target: edge.to_host,
    onPath: onPath(edge.from_host, edge.to_host), likelihood: edge.likelihood,
  }))
  const scaled = lowerDetail(nodes, links, zones, options)
  const zoneModels = scaled.zones.map((zone, index) => ({
    zone: zone.zone, label: zone.zone.replaceAll('-', ' ').toUpperCase(), hostIds: hostIdsByZone.get(zone.zone) || [],
    x: (index - (scaled.zones.length - 1) / 2) * Math.max(280, (hostIdsByZone.get(zone.zone)?.length || 1) * 2.8),
  }))
  return { ...scaled, zones: zoneModels, cones: [] }
}

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

export const coneWidth = (confidence) => 0.6 + confidence * 5
export const coneOpacity = (confidence) => 0.15 + confidence * 0.65

export function buildScene(state) {
  if (!state || !state.graph) return { nodes: [], links: [], cones: [], zones: [] }
  const hosts = state.graph.hosts
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
    return { id: h.host_id, name: h.name, zone: h.zone, state: h.state, ...style, ...layoutFor(h.zone, index, perZone[h.zone]),
             predicted: predicted[h.host_id] ?? null }
  })
  const links = state.graph.edges.map((e) => ({ key: `${e.from_host}>${e.to_host}`, source: e.from_host, target: e.to_host, onPath: onPath(e.from_host, e.to_host) }))
  const cones = forecast ? forecast.targets.map((t) => ({ from: forecast.from_host, to: t.host_id, confidence: t.confidence,
                                                         width: coneWidth(t.confidence), opacity: coneOpacity(t.confidence) })) : []
  const zones = Object.keys(perZone).map((zone) => ({ zone, hostIds: hosts.filter((h) => h.zone === zone).map((h) => h.host_id) }))
  return { nodes, links, cones, zones }
}

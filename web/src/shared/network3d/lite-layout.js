const ZONES = ['user', 'dmz', 'internal']
const ZONE_X = { user: 170, dmz: 500, internal: 830 }
const ZONE_Y = { user: 346, dmz: 260, internal: 346 }

export function buildLiteLayout(model, width = 1000, height = 620) {
  const counts = {}
  for (const node of model?.nodes || []) counts[node.zone] = (counts[node.zone] || 0) + 1
  const placed = {}
  const nodes = (model?.nodes || []).map((node) => {
    const index = placed[node.zone] || 0
    placed[node.zone] = index + 1
    const count = counts[node.zone] || 1
    const step = Math.min(150, (height - 190) / Math.max(count, 1))
    return { ...node, px: (ZONE_X[node.zone] || width / 2) * (width / 1000), py: ((ZONE_Y[node.zone] || 310) + (index - (count - 1) / 2) * step) * (height / 620) }
  })
  const byId = Object.fromEntries(nodes.map((node) => [node.id, node]))
  const links = (model?.links || []).map((link) => ({ ...link, from: byId[typeof link.source === 'object' ? link.source.id : link.source], to: byId[typeof link.target === 'object' ? link.target.id : link.target] })).filter((link) => link.from && link.to)
  return { nodes, links, zones: ZONES.map((zone) => ({ zone, x: ZONE_X[zone] * (width / 1000) })) }
}

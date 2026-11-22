/** Stable route defaults derived only from the active workspace graph. */
export function hasFeasibleRoute(source, target, edges) {
  if (!source || !target) return false
  if (source === target) return true
  const adjacency = new Map()
  for (const edge of edges || []) {
    if (!adjacency.has(edge.from_host)) adjacency.set(edge.from_host, [])
    adjacency.get(edge.from_host).push(edge.to_host)
  }
  const pending = [source]
  const visited = new Set(pending)
  for (let index = 0; index < pending.length; index += 1) {
    for (const next of adjacency.get(pending[index]) || []) {
      if (next === target) return true
      if (!visited.has(next)) { visited.add(next); pending.push(next) }
    }
  }
  return false
}

/** Choose the longest shortest reachable pair; retain stable host ordering for ties. */
export function defaultReachablePair(hosts = [], edges = []) {
  const ids = hosts.map((host) => host.host_id).filter(Boolean)
  const adjacency = new Map()
  for (const edge of edges) {
    if (!adjacency.has(edge.from_host)) adjacency.set(edge.from_host, [])
    adjacency.get(edge.from_host).push(edge.to_host)
  }
  let best = null
  for (const source of ids) {
    const pending = [[source, 0]]
    const distance = new Map([[source, 0]])
    for (let index = 0; index < pending.length; index += 1) {
      const [current, depth] = pending[index]
      for (const next of adjacency.get(current) || []) {
        if (distance.has(next)) continue
        distance.set(next, depth + 1)
        pending.push([next, depth + 1])
        if (depth + 1 > 0 && (!best || depth + 1 > best.distance)) best = { from: source, to: next, distance: depth + 1 }
      }
    }
  }
  return best ? { from: best.from, to: best.to } : { from: ids[0] || '', to: ids[0] || '' }
}

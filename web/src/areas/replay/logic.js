export const blankScenario = (id = 'user-new-scenario') => ({
  scenario_id: id,
  description: 'A scripted replay for the demo network.',
  events: [{ seq: 1, offset_ms: 0, kind: 'technique', host: 'host-a', technique_id: 'T1046', note: 'Begin reconnaissance.' }],
})

export function resequence(events) {
  return events.map((event, index) => ({ ...event, seq: index + 1 }))
}

export function eventHosts(event) {
  if (event.kind === 'technique') return [event.host]
  if (event.kind === 'attempt') return [event.from_host, event.to_host]
  return [...new Set((event.packets || []).flatMap((packet) => [packet.src_host, packet.dst_host]))]
}

export function eventLabel(event) {
  if (event.kind === 'technique') return `${event.technique_id} · ${event.compromise ? 'compromise' : 'technique'}`
  if (event.kind === 'attempt') return `${event.from_host} → ${event.to_host}`
  return `${event.packets?.length || 0} traffic link${event.packets?.length === 1 ? '' : 's'}`
}

export function timelineLanes(events, hosts) {
  const names = new Map(hosts.map((host) => [host.host_id, host.name]))
  const lanes = new Map()
  for (const event of events) {
    for (const hostId of eventHosts(event)) {
      if (!hostId) continue
      if (!lanes.has(hostId)) lanes.set(hostId, [])
      lanes.get(hostId).push({ seq: event.seq, offset_ms: event.offset_ms, kind: event.kind, label: eventLabel(event) })
    }
  }
  return [...lanes].map(([hostId, items]) => ({ host_id: hostId, name: names.get(hostId) || hostId, items }))
}

export function normalizeForComparison(value) {
  const volatile = new Set(['ts', 'timestamp', 'first_seen', 'first_alert_at', 'last_alert_at', 'started_at', 'ended_at', 'created_at', 'updated_at', 'captured_at', 'proposed_at', 'confirmed_at', 'session_id', 'duration_seconds'])
  if (Array.isArray(value)) return value.map(normalizeForComparison)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(Object.entries(value).filter(([key]) => !volatile.has(key)).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, normalizeForComparison(item)]))
}

export function safeScenarioFilename(id) {
  return `${String(id || 'scenario').replace(/[^a-z0-9-]/gi, '-')}.json`
}

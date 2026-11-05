export function severityTone(severity) {
  if (severity === 'HIGH') return 'high'
  if (severity === 'MEDIUM') return 'medium'
  return 'low'
}

export function durationLabel(seconds) {
  const value = Number.isFinite(Number(seconds)) ? Math.max(0, Math.floor(Number(seconds))) : 0
  if (value < 60) return `${value}s`
  if (value < 3600) return `${Math.floor(value / 60)}m ${value % 60}s`
  return `${Math.floor(value / 3600)}h ${Math.floor((value % 3600) / 60)}m`
}

export function incidentStats(items = []) {
  return items.reduce((summary, item) => {
    if (item.severity === 'HIGH') summary.high += 1
    if (item.status === 'open' || item.status === 'reopened') summary.open += 1
    if (item.forecasts?.length) summary.forecasted += 1
    return summary
  }, { high: 0, open: 0, forecasted: 0 })
}

export function savedFilterList(raw) {
  try {
    const parsed = JSON.parse(raw || '[]')
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item?.label === 'string' && item.filters && typeof item.filters === 'object').slice(-8) : []
  } catch {
    return []
  }
}

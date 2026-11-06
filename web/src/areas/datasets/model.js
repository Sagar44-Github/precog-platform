export function capabilityLabel(value) {
  if (value === 'native') return 'Included in source pack'
  if (value === 'derived') return 'Derived for this simulation'
  return 'Not provided'
}

export function comparisonRows(left = {}, right = {}) {
  const keys = new Set([...Object.keys(left.capabilities || {}), ...Object.keys(right.capabilities || {})])
  const labels = { detection_labels: 'Detection labels', host_compromise: 'Host compromise mapping', lateral_movement_routes: 'Lateral movement routes', topology: 'Topology' }
  return [...keys].sort().map((key) => ({
    key,
    label: labels[key] || key.replaceAll('_', ' '),
    left: capabilityLabel(left.capabilities?.[key]),
    right: capabilityLabel(right.capabilities?.[key]),
  }))
}

export function isSwitchable(workspace) {
  return Boolean(workspace && workspace.status !== 'unavailable')
}

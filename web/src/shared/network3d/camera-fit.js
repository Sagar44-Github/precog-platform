const radians = (degrees) => degrees * Math.PI / 180

/** Return a perspective-camera distance that keeps the full node bounds in view. */
export function fitDistance(nodes, width, height, verticalFov = 60, padding = 1.2) {
  const points = (nodes || []).filter((node) =>
    Number.isFinite(node.x) && Number.isFinite(node.y) && Number.isFinite(node.z))
  if (!points.length) return null

  const bounds = points.reduce((result, node) => ({
    minX: Math.min(result.minX, node.x), maxX: Math.max(result.maxX, node.x),
    minY: Math.min(result.minY, node.y), maxY: Math.max(result.maxY, node.y),
    minZ: Math.min(result.minZ, node.z), maxZ: Math.max(result.maxZ, node.z),
  }), { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity, minZ: Infinity, maxZ: -Infinity })
  const center = {
    x: (bounds.minX + bounds.maxX) / 2,
    y: (bounds.minY + bounds.maxY) / 2,
    z: (bounds.minZ + bounds.maxZ) / 2,
  }
  // Include the host model, state rings and the labels placed around each host.
  const radius = Math.max(...points.map((node) => Math.hypot(node.x - center.x, node.y - center.y, node.z - center.z) + Math.max(0, Number(node.radius) || 0) * 4), 12)
  const safeWidth = Math.max(1, Number(width) || 1)
  const safeHeight = Math.max(1, Number(height) || 1)
  const halfVerticalFov = radians(Math.max(1, Math.min(179, verticalFov))) / 2
  const halfHorizontalFov = Math.atan(Math.tan(halfVerticalFov) * safeWidth / safeHeight)
  const limitingHalfFov = Math.min(halfVerticalFov, halfHorizontalFov)
  const distance = radius * Math.max(1, padding) / Math.sin(limitingHalfFov)
  return { center, radius, distance, limitingHalfFov }
}

export function nodeGeometryKey(nodes) {
  return (nodes || []).map((node) => [node.id, node.x, node.y, node.z, node.radius].join(':')).join('|')
}

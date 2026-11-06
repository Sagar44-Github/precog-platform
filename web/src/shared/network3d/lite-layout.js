const preferredOrder = ['user', 'dmz', 'internal']

function orderedZones(nodes) {
  const zones = [...new Set((nodes || []).map((node) => node.zone || 'other'))]
  return zones.sort((left, right) => {
    const a = preferredOrder.indexOf(left)
    const b = preferredOrder.indexOf(right)
    if (a >= 0 || b >= 0) return (a < 0 ? 99 : a) - (b < 0 ? 99 : b)
    return left.localeCompare(right)
  })
}

/** Stable 2D grid layout; nodes keep space inside their zone instead of stacking vertically. */
export function buildLiteLayout(model, width = 1000, height = 620) {
  const sourceNodes = model?.nodes || []
  const zoneNames = orderedZones(sourceNodes)
  const zoneColumns = Math.min(4, Math.max(1, Math.ceil(Math.sqrt(zoneNames.length))))
  const zoneRows = Math.max(1, Math.ceil(zoneNames.length / zoneColumns))
  const cellWidth = width / zoneColumns
  const cellHeight = height / zoneRows
  const nodesByZone = new Map(zoneNames.map((zone) => [zone, sourceNodes.filter((node) => node.zone === zone)]))
  const zones = zoneNames.map((zone, index) => {
    const column = index % zoneColumns
    const row = Math.floor(index / zoneColumns)
    const x = column * cellWidth + cellWidth / 2
    const y = row * cellHeight + cellHeight / 2
    return { zone, x, y, width: cellWidth - 12, height: cellHeight - 12, label: zone.replaceAll('-', ' ').toUpperCase() }
  })
  const nodes = []
  for (const zone of zones) {
    const list = nodesByZone.get(zone.zone) || []
    const columns = Math.max(1, Math.ceil(Math.sqrt(list.length)))
    const rows = Math.max(1, Math.ceil(list.length / columns))
    const spacingX = Math.min(31, (zone.width - 34) / columns)
    const spacingY = Math.min(38, (zone.height - 58) / rows)
    list.forEach((node, index) => {
      const column = index % columns
      const row = Math.floor(index / columns)
      nodes.push({ ...node,
        px: zone.x + (column - (columns - 1) / 2) * spacingX,
        py: zone.y + 13 + (row - (rows - 1) / 2) * spacingY,
      })
    })
  }
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const links = (model?.links || []).map((link) => ({ ...link,
    from: byId.get(typeof link.source === 'object' ? link.source.id : link.source),
    to: byId.get(typeof link.target === 'object' ? link.target.id : link.target),
  })).filter((link) => link.from && link.to)
  return { nodes, links, zones }
}

export function virtualWindow(itemCount, scrollTop, rowHeight, viewportHeight, overscan = 5) {
  if (![itemCount, rowHeight, viewportHeight].every(Number.isFinite) || itemCount < 0 || rowHeight <= 0 || viewportHeight < 0) {
    return { start: 0, end: 0, offset: 0, totalHeight: 0 }
  }
  const maxScroll = Math.max(0, itemCount * rowHeight - viewportHeight)
  const safeScroll = Math.max(0, Math.min(Number(scrollTop) || 0, maxScroll))
  const visible = Math.ceil(viewportHeight / rowHeight)
  const start = Math.max(0, Math.floor(safeScroll / rowHeight) - Math.max(0, overscan))
  const end = Math.min(itemCount, start + visible + Math.max(0, overscan) * 2)
  return { start, end, offset: start * rowHeight, totalHeight: itemCount * rowHeight }
}

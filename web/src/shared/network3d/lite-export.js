import { buildLiteLayout } from './lite-layout.js'

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim()

export function downloadLitePng(model, label = 'precog-topology') {
  const width = 1600
  const height = 992
  const layout = buildLiteLayout(model, 1000, 620)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) throw new Error('PNG export is not available in this browser.')
  const sx = width / 1000
  const sy = height / 620
  const color = (token) => cssVar(token) || 'white'
  context.fillStyle = color('--bg')
  context.fillRect(0, 0, width, height)
  context.strokeStyle = color('--border')
  context.lineWidth = 2
  context.strokeRect(18 * sx, 20 * sy, 964 * sx, 580 * sy)
  for (const zone of layout.zones) {
    context.fillStyle = color('--surface-raised')
    context.globalAlpha = 0.58
    context.fillRect((zone.x - 145) * sx, 54 * sy, 290 * sx, 520 * sy)
    context.globalAlpha = 1
    context.fillStyle = color('--text-muted')
    context.font = '600 15px sans-serif'
    context.textAlign = 'center'
    context.fillText(`${zone.zone.toUpperCase()} ZONE`, zone.x * sx, 84 * sy)
  }
  for (const edge of layout.links) {
    context.beginPath()
    context.moveTo(edge.from.px * sx, edge.from.py * sy)
    context.lineTo(edge.to.px * sx, edge.to.py * sy)
    context.strokeStyle = color(edge.onPath ? '--state-compromised' : '--border-strong')
    context.globalAlpha = edge.onPath ? 0.92 : 0.58
    context.lineWidth = edge.onPath ? 3 : 1.5
    context.stroke()
    context.globalAlpha = 1
  }
  for (const node of layout.nodes) {
    const x = node.px * sx
    const y = node.py * sy
    const radius = 14 * sx
    const token = node.state === 'compromised' ? '--state-compromised' : node.state === 'contained' ? '--state-contained' : '--state-normal'
    context.fillStyle = color(token)
    context.strokeStyle = node.predicted === null ? color('--border-strong') : color('--forecast')
    context.lineWidth = node.predicted === null ? 2 : 3
    context.beginPath()
    if (node.state === 'contained') context.rect(x - radius, y - radius, radius * 2, radius * 2)
    else if (node.state === 'compromised') {
      for (let point = 0; point < 8; point += 1) {
        const angle = (Math.PI / 4) * point - Math.PI / 2
        const px = x + Math.cos(angle) * radius
        const py = y + Math.sin(angle) * radius
        if (point === 0) context.moveTo(px, py); else context.lineTo(px, py)
      }
      context.closePath()
    } else context.arc(x, y, radius * 0.78, 0, Math.PI * 2)
    context.fill()
    context.stroke()
    context.fillStyle = color('--text')
    context.textAlign = 'center'
    context.font = '600 17px sans-serif'
    context.fillText(node.name, x, y + 44 * sy)
    context.fillStyle = color(token)
    context.font = '12px monospace'
    context.fillText(node.state.toUpperCase(), x, y + 60 * sy)
    if (node.predicted !== null) {
      context.fillStyle = color('--forecast')
      context.fillText(`${node.predicted}% forecast`, x, y - 24 * sy)
    }
  }
  const anchor = document.createElement('a')
  anchor.download = `${label}.png`
  anchor.href = canvas.toDataURL('image/png')
  anchor.click()
}

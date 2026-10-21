import { useEffect, useRef } from 'react'
import { BarController, BarElement, CategoryScale, Chart, Legend, LineController, LineElement, LinearScale, PointElement, Tooltip } from 'chart.js'
import { EmptyState } from '../../shared/components.jsx'
import { CALIBRATION_CAPTION, PATTERNS, alertVolume, calibrationPoints, calibrationSummary, referenceLine, volumeSummary } from './chartData.js'

Chart.register(BarController, BarElement, CategoryScale, Legend, LineController, LineElement, LinearScale, PointElement, Tooltip)

// The two charts (owner: VIZ). GRAPH imports these two names with these properties, so they must never change.

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim()
const reducedMotion = () => typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** A fill pattern for a stacked column: solid, diagonal lines or dots. */
function pattern(kind, color) {
  if (kind === 'solid') return color
  const tile = document.createElement('canvas')
  tile.width = tile.height = 8
  const g = tile.getContext('2d')
  g.fillStyle = cssVar('--surface')
  g.fillRect(0, 0, 8, 8)
  g.strokeStyle = g.fillStyle = color
  if (kind === 'diagonal') { g.lineWidth = 2; g.beginPath(); g.moveTo(0, 8); g.lineTo(8, 0); g.stroke() } else { g.beginPath(); g.arc(4, 4, 2, 0, Math.PI * 2); g.fill() }
  return g.createPattern(tile, 'repeat')
}

function useChart(build, deps) {
  const canvas = useRef(null)
  useEffect(() => {
    if (!canvas.current) return undefined
    const chart = new Chart(canvas.current, build())
    return () => chart.destroy()
  }, deps)  // eslint-disable-line react-hooks/exhaustive-deps
  return canvas
}

const axis = (title) => ({ title: { display: true, text: title, color: cssVar('--text-muted') }, ticks: { color: cssVar('--text-muted'), maxTicksLimit: 5 }, grid: { color: cssVar('--border') } })

export function ForecastAccuracyChart({ metrics }) {
  const points = calibrationPoints(metrics)
  const canvas = useChart(() => ({
    type: 'line',
    data: { datasets: [
      { label: 'Observed', data: points, borderColor: cssVar('--forecast'), backgroundColor: cssVar('--forecast'), pointStyle: 'circle', pointRadius: 5, showLine: true },
      { label: 'Perfect', data: referenceLine(), borderColor: cssVar('--text-muted'), borderDash: [6, 4], pointRadius: 0 },
    ] },
    options: { parsing: false, animation: reducedMotion() ? false : { duration: 300 }, maintainAspectRatio: false, scales: { x: { type: 'linear', min: 0, max: 100, ...axis('Stated confidence (%)') }, y: { type: 'linear', min: 0, max: 100, ...axis('Observed hit rate (%)') } }, plugins: { legend: { labels: { color: cssVar('--text-muted') } } } },
  }), [JSON.stringify(points)])
  if (!points.length) return <EmptyState>No forecasts resolved yet.</EmptyState>
  return (
    <figure style={{ margin: 0 }}>
      <div style={{ height: 180 }}><canvas ref={canvas} role="img" aria-label={calibrationSummary(metrics)} /></div>
      <figcaption className="muted">{CALIBRATION_CAPTION}</figcaption>
    </figure>
  )
}

export function AlertVolumeChart({ alerts }) {
  const volume = alertVolume(alerts)
  const canvas = useChart(() => {
    const dataset = (label, key, variable) => ({ label, data: volume[key], backgroundColor: pattern(PATTERNS[key], cssVar(variable)), borderColor: cssVar(variable), borderWidth: 1 })
    return {
      type: 'bar',
      data: { labels: volume.labels, datasets: [dataset('High', 'high', '--severity-high'), dataset('Medium', 'medium', '--severity-medium'), dataset('Low', 'low', '--severity-low')] },
      options: { animation: reducedMotion() ? false : { duration: 300 }, maintainAspectRatio: false, scales: { x: { stacked: true, ...axis('Time') }, y: { stacked: true, beginAtZero: true, ...axis('Alerts') } }, plugins: { legend: { labels: { color: cssVar('--text-muted') } } } },
    }
  }, [JSON.stringify(volume)])
  if (!alerts.length) return <EmptyState>No alerts yet.</EmptyState>
  return <div style={{ height: 180 }}><canvas ref={canvas} role="img" aria-label={volumeSummary(alerts)} /></div>
}

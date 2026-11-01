// Chart data as plain functions (owner: VIZ), so it can be tested without a canvas.

/** The calibration view: stated confidence against the observed hit rate, in percent. Bins with no forecasts are left out. */
export function calibrationPoints(metrics) {
  const bins = metrics && metrics.calibration_bins ? metrics.calibration_bins : []
  return bins.filter((b) => b.count > 0).map((b) => ({ x: Math.round(b.mean_confidence * 100), y: Math.round(b.observed_rate * 100), count: b.count }))
}

/** The dashed reference line: confidence equals reality. */
export const referenceLine = () => [{ x: 0, y: 0 }, { x: 100, y: 100 }]

export const CALIBRATION_CAPTION = 'Closer to the dashed line means the stated confidence matches reality.'

export function calibrationSummary(metrics) {
  const points = calibrationPoints(metrics)
  if (!points.length) return 'No forecasts resolved yet.'
  return 'Calibration: ' + points.map((p) => `stated ${p.x} %, observed ${p.y} % (${p.count} forecast${p.count === 1 ? '' : 's'})`).join('; ') + '.'
}

const minuteKey = (ts) => String(ts).replace(' ', 'T').slice(0, 16)

/** Alerts counted per minute and per severity, oldest minute first. */
export function alertVolume(alerts) {
  const minutes = new Map()
  for (const alert of alerts) {
    const key = minuteKey(alert.ts)
    if (!minutes.has(key)) minutes.set(key, { HIGH: 0, MEDIUM: 0, LOW: 0 })
    if (minutes.get(key)[alert.severity] !== undefined) minutes.get(key)[alert.severity] += 1
  }
  const labels = [...minutes.keys()].sort()
  const series = (severity) => labels.map((k) => minutes.get(k)[severity])
  return { labels: labels.map((k) => k.slice(11)), high: series('HIGH'), medium: series('MEDIUM'), low: series('LOW') }
}

export function volumeSummary(alerts) {
  if (!alerts.length) return 'No alerts yet.'
  const v = alertVolume(alerts)
  const sum = (a) => a.reduce((x, y) => x + y, 0)
  return `${alerts.length} alerts over ${v.labels.length} minute${v.labels.length === 1 ? '' : 's'}: ${sum(v.high)} high, ${sum(v.medium)} medium, ${sum(v.low)} low.`
}

/** Each severity also gets its own fill pattern, so the chart does not rely on colour alone. */
export const PATTERNS = { high: 'solid', medium: 'diagonal', low: 'dots' }

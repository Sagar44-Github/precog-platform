// PLACEHOLDER created by LEAD-CORE. VIZ replaces the contents of this file with real Chart.js charts.
// GRAPH imports these two components on the phone screens, so KEEP THESE NAMES AND PROPERTIES:
//   <ForecastAccuracyChart metrics={...} />   metrics = the session_metrics object (contracts/schemas/session_metrics.schema.json)
//   <AlertVolumeChart alerts={...} />         alerts  = the list of security_event objects

export function ForecastAccuracyChart({ metrics }) {
  const rate = metrics && typeof metrics.hit_rate === 'number' ? Math.round(metrics.hit_rate * 100) + '%' : 'no data yet'
  return <div className="card muted">Forecast accuracy chart (VIZ placeholder). Hit rate: {rate}</div>
}

export function AlertVolumeChart({ alerts }) {
  return <div className="card muted">Alert volume chart (VIZ placeholder). Alerts: {alerts ? alerts.length : 0}</div>
}

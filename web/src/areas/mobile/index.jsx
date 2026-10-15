import { Navigate } from 'react-router-dom'
import { useWorldState } from '../../shared/usePolling.js'

// PLACEHOLDER created by LEAD-CORE. GRAPH replaces everything in this file and adds files in this folder only.
// Keep the default export: App.jsx imports it. Inside it you may use your own <Routes> for the phone screens.
export default function MobileApp() {
  const { state, stale, loggedOut } = useWorldState()
  if (loggedOut) return <Navigate to="/login" replace />
  return (
    <div className="center-page">
      <div className="card" style={{ width: 'min(420px, 100%)' }}>
        {stale && <div className="stale-banner">Connection lost: showing old data</div>}
        <h2 style={{ marginTop: 0 }}>Mobile app (GRAPH placeholder)</h2>
        <p className="muted">The wiring works. Live version from the backend:</p>
        <p className="mono">{state ? 'version ' + state.version : 'waiting for the first reply...'}</p>
        <p className="muted">Alerts held: {state ? state.alerts.length : '-'}</p>
      </div>
    </div>
  )
}

// ---- Named placeholder components (UI/UX brief Section 14). VIZ's console imports these names, so they must exist from the start.
// GRAPH replaces this whole file; the real components keep the same names and properties.
export const SeverityBadge = ({ severity }) => <span>{severity}</span>
export const StateChip = ({ state }) => <span>{state}</span>
export const ForecastBars = ({ state }) => <div>{state && state.forecast ? state.forecast.targets.map((t) => `${t.host_id} ${Math.round(t.confidence * 100)} %`).join(', ') : 'No forecast right now.'}</div>
export const OutcomeCard = () => null
export const AccuracyCounter = ({ metrics }) => <div>{metrics && metrics.forecasts_resolved ? `${metrics.hits} / ${metrics.forecasts_resolved}` : 'No forecasts resolved yet'}</div>
export const AttackPath2D = ({ state }) => <div>{state && state.graph ? state.graph.compromised_path.join(' -> ') : ''}</div>

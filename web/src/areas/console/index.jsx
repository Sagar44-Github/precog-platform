import { Navigate } from 'react-router-dom'
import { useWorldState } from '../../shared/usePolling.js'

// PLACEHOLDER created by LEAD-CORE. VIZ replaces everything in this file and adds files in this folder only.
// Keep the default export: App.jsx imports it.
export default function ConsoleApp() {
  const { state, stale, loggedOut } = useWorldState()
  if (loggedOut) return <Navigate to="/login" replace />
  return (
    <div className="center-page">
      <div className="card" style={{ width: 'min(520px, 100%)' }}>
        {stale && <div className="stale-banner">Connection lost: showing old data</div>}
        <h2 style={{ marginTop: 0 }}>3D console (VIZ placeholder)</h2>
        <p className="muted">The wiring works. Hosts in the graph: {state ? state.graph.hosts.length : '-'}</p>
      </div>
    </div>
  )
}

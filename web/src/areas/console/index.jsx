import { useEffect, useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { LoadingState, StaleBanner, ToastProvider, useToast } from '../../shared/components.jsx'
import { useWorldState } from '../../shared/usePolling.js'
import { AlertsPanel, ForecastPanel, LeftRail, NodeDetailPanel, ReportsPanel, SceneSummary, TimelineStrip, TopBar } from './panels.jsx'
import Scene3D from './Scene3D.jsx'
import { buildScene } from './sceneModel.js'
import './console.css'

// The 3D console (owner: VIZ). App.jsx imports the default export.

function Console({ state, stale }) {
  const toast = useToast()
  const [view, setView] = useState('graph')
  const [selected, setSelected] = useState(null)
  const [resolved, setResolved] = useState(null)
  const model = useMemo(() => buildScene(state), [state && state.version])  // eslint-disable-line react-hooks/exhaustive-deps

  // the newest forecast that has an outcome, for the outcome card
  useEffect(() => {
    let alive = true
    api.forecasts().then((list) => { if (alive) setResolved([...list].reverse().find((f) => f.status === 'hit' || f.status === 'miss') || null) }).catch(() => {})
    return () => { alive = false }
  }, [state && state.metrics ? state.metrics.forecasts_resolved : 0])  // eslint-disable-line react-hooks/exhaustive-deps

  const pending = Boolean(state && state.forecast && state.forecast.status === 'pending')
  let panel
  if (!state) panel = <LoadingState />
  else if (view === 'alerts') panel = <AlertsPanel state={state} />
  else if (view === 'reports') panel = <ReportsPanel state={state} />
  else if (selected) panel = <NodeDetailPanel state={state} hostId={selected} onClose={() => setSelected(null)} onDone={toast.show} />
  else panel = <ForecastPanel state={state} resolved={resolved} onDone={toast.show} />

  return (
    <div className="c-app" data-waiting={pending ? 'true' : 'false'}>
      <TopBar state={state} stale={stale} />
      <StaleBanner stale={stale} />
      <LeftRail view={view} onChange={(v) => { setView(v); setSelected(null) }} />
      <main className="c-centre">
        <Scene3D model={model} pendingForecast={pending} onSelect={(id) => { setSelected(id); if (id) setView('graph') }} />
        {state && <SceneSummary state={state} />}
        {state && state.replay.state === 'idle' && <p className="c-hint">Start the replay to see an attack.</p>}
      </main>
      <aside className="c-right" data-focus={pending ? 'true' : 'false'}>{panel}</aside>
      <TimelineStrip alerts={state ? state.alerts : []} forecast={state ? state.forecast : null} />
    </div>
  )
}

export default function ConsoleApp() {
  const { state, stale, loggedOut } = useWorldState()
  if (loggedOut) return <Navigate to="/login" replace />
  return <ToastProvider><Console state={state} stale={stale} /></ToastProvider>
}

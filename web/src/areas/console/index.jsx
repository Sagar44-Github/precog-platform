import { useEffect, useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { useAuth } from '../../shared/AuthContext.jsx'
import { LoadingState, StaleBanner, ToastProvider, useToast } from '../../shared/components.jsx'
import { useWorldState } from '../../shared/usePolling.js'
import DemoStart from '../../shared/DemoStart.jsx'
import { AlertsPanel, ForecastPanel, LeftRail, NodeDetailPanel, ReportsPanel, SceneSummary, TimelineStrip, TopBar } from './panels.jsx'
import Scene3D from '../../shared/network3d/Scene3D.jsx'
import { buildScene } from './sceneModel.js'
import './console.css'

// The 3D console (owner: VIZ). App.jsx imports the default export.

function Console({ state, stale, permissions }) {
  const { show } = useToast()
  const [view, setView] = useState('graph')
  const [selected, setSelected] = useState(null)
  const [resolved, setResolved] = useState(null)
  const [assets, setAssets] = useState([])
  const model = useMemo(() => buildScene(state, assets, { selectedHostId: selected }), [state && state.version, assets, selected])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let alive = true
    api.assets().then((result) => { if (alive) setAssets(result.items || []) }).catch(() => {})
    return () => { alive = false }
  }, [])

  // the newest forecast that has an outcome, for the outcome card
  useEffect(() => {
    let alive = true
    api.forecasts().then((list) => { if (alive) setResolved([...list].reverse().find((f) => f.status === 'hit' || f.status === 'miss') || null) }).catch(() => {})
    return () => { alive = false }
  }, [state && state.metrics ? state.metrics.forecasts_resolved : 0])  // eslint-disable-line react-hooks/exhaustive-deps

  const pending = Boolean(state && state.forecast && state.forecast.status === 'pending')

  useEffect(() => {
    const onCommand = (event) => {
      const command = event.detail || {}
      if (command.type === 'view' && ['graph', 'alerts', 'reports'].includes(command.view)) {
        setView(command.view)
        setSelected(null)
      }
      if (command.type === 'start-demo' && permissions?.can_run_replay) {
        api.startReplay('golden-path', 1)
          .then(() => show('Golden Path replay started (simulation)'))
          .catch((error) => show(error.message || 'Could not start the replay.'))
      }
    }
    window.addEventListener('precog:console-command', onCommand)
    return () => window.removeEventListener('precog:console-command', onCommand)
  }, [show, permissions])

  let panel
  if (!state) panel = <LoadingState />
  else if (view === 'alerts') panel = <AlertsPanel state={state} />
  else if (view === 'reports') panel = <ReportsPanel state={state} />
  else if (selected) panel = <NodeDetailPanel state={state} hostId={selected} onClose={() => setSelected(null)} onDone={show} canContain={permissions?.can_contain} />
  else panel = <ForecastPanel state={state} resolved={resolved} onDone={show} canContain={permissions?.can_contain} />

  return (
    <div className="c-app" data-waiting={pending ? 'true' : 'false'}>
      <TopBar state={state} stale={stale} permissions={permissions} />
      <StaleBanner stale={stale} />
      <LeftRail view={view} onChange={(v) => { setView(v); setSelected(null) }} />
      <main className="c-centre">
        {state && <div className="c-map-heading"><div><span className="c-eyebrow">TACTICAL NETWORK VIEW / 01</span><h1>Attack surface</h1></div><div className="c-map-totals"><span><b>{state.graph.hosts.length.toString().padStart(2, '0')}</b> ASSETS</span><span><b>{Object.keys(state.graph.hosts.reduce((zones, host) => ({ ...zones, [host.zone]: true }), {})).length.toString().padStart(2, '0')}</b> ZONES</span><span><b>{state.alerts.length.toString().padStart(2, '0')}</b> EVENTS</span></div></div>}
        <Scene3D model={model} pendingForecast={pending} selectedHostId={selected} onSelect={(id) => { setSelected(id); if (id) setView('graph') }} />
        {state && <SceneSummary state={state} />}
        {state && state.replay.state === 'idle' && permissions?.can_run_replay && <DemoStart className="c-demo-launch" hostCount={state.graph.hosts.length} />}
      </main>
      <aside className="c-right" data-focus={pending ? 'true' : 'false'}>{panel}</aside>
      <TimelineStrip alerts={state ? state.alerts : []} forecast={state ? state.forecast : null} />
    </div>
  )
}

export default function ConsoleApp() {
  const { permissions } = useAuth()
  const { state, stale, loggedOut } = useWorldState()
  if (loggedOut) return <Navigate to="/login" replace />
  return <ToastProvider><Console state={state} stale={stale} permissions={permissions} /></ToastProvider>
}

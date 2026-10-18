import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { SimulationBadge, StaleBanner, ToastProvider } from '../../shared/components.jsx'
import { useWorldState } from '../../shared/usePolling.js'
import { AlertDetailScreen, AlertsScreen, ForecastScreen, HistoryScreen, HomeScreen } from './screens.jsx'
import { highAlertCount } from './logic.js'
import './mobile.css'

// The phone app (owner: GRAPH). App.jsx imports the default export. VIZ imports the named components below.
export { AccuracyCounter, AttackPath2D, ForecastBars, OutcomeCard, SeverityBadge, StateChip } from './components.jsx'

export function TabBar({ state }) {
  const high = state ? highAlertCount(state.alerts) : 0
  const pending = Boolean(state && state.forecast)
  const tabs = [['/mobile', 'Home', '⌂', true], ['/mobile/alerts', 'Alerts', '△', false], ['/mobile/forecast', 'Forecast', '◌', false], ['/mobile/history', 'History', '◷', false]]
  return (
    <nav className="m-tabs" aria-label="Main">
      {tabs.map(([to, label, icon, end]) => (
        <NavLink key={to} to={to} end={end} className="m-tab">
          <span aria-hidden="true">{icon}</span><span>{label}</span>
          {label === 'Alerts' && high > 0 && <span className="m-tab-badge" aria-label={`${high} high alerts`}>{high}</span>}
          {label === 'Forecast' && pending && <span className="m-tab-dot" aria-label="A forecast is pending" />}
        </NavLink>
      ))}
    </nav>
  )
}

export default function MobileApp() {
  const { state, stale, loggedOut } = useWorldState()
  if (loggedOut) return <Navigate to="/login" replace />
  return (
    <ToastProvider>
      <div className="m-app">
        <header className="m-top"><h1>Precog SOC</h1><SimulationBadge /></header>
        <StaleBanner stale={stale} />
        <Routes>
          <Route index element={<HomeScreen state={state} stale={stale} />} />
          <Route path="alerts" element={<AlertsScreen state={state} />} />
          <Route path="alerts/:id" element={<AlertDetailScreen state={state} />} />
          <Route path="forecast" element={<ForecastScreen state={state} />} />
          <Route path="history" element={<HistoryScreen state={state} />} />
          <Route path="*" element={<Navigate to="/mobile" replace />} />
        </Routes>
        <TabBar state={state} />
      </div>
    </ToastProvider>
  )
}

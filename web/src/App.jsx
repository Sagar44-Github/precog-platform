import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './shared/AppShell.jsx'
import { LoginPage, RequireAuth } from './shared/AuthContext.jsx'
import { LoadingState } from './shared/components.jsx'
import { ThemeProvider } from './shared/theme-context.jsx'

const MobileApp = lazy(() => import('./areas/mobile/index.jsx'))
const ConsoleApp = lazy(() => import('./areas/console/index.jsx'))
const AlertsPage = lazy(() => import('./areas/ops/alerts.jsx'))
const AlertDetailPage = lazy(() => import('./areas/ops/alert-detail.jsx'))
const HostsPage = lazy(() => import('./areas/ops/hosts.jsx'))
const HostDetailPage = lazy(() => import('./areas/ops/host-detail.jsx'))
const AuditPage = lazy(() => import('./areas/ops/audit.jsx'))
const SystemPage = lazy(() => import('./areas/ops/system.jsx'))
const SettingsPage = lazy(() => import('./areas/ops/settings.jsx'))
const IncidentsPage = lazy(() => import('./areas/ops/incidents.jsx'))
const IncidentDetailPage = lazy(() => import('./areas/ops/incident-detail.jsx'))
const ReportsPage = lazy(() => import('./areas/ops/reports.jsx'))
const ReportDetailPage = lazy(() => import('./areas/ops/report-detail.jsx'))
const ForecastsPage = lazy(() => import('./areas/ops/forecasts.jsx'))
const ForecastDetailPage = lazy(() => import('./areas/ops/forecast-detail.jsx'))
const AnalyticsPage = lazy(() => import('./areas/ops/analytics.jsx'))
const ContainmentPage = lazy(() => import('./areas/ops/containment.jsx'))
const ReplayStudioPage = lazy(() => import('./areas/ops/replay-studio.jsx'))
const ScenarioBuilderPage = lazy(() => import('./areas/ops/scenario-builder.jsx'))
import { UiPreferencesProvider } from './shared/ui-preferences.jsx'

function WorkspacePage({ children }) {
  return <RequireAuth><AppShell><Suspense fallback={<LoadingState />}>{children}</Suspense></AppShell></RequireAuth>
}

// Owner: LEAD-CORE. Written once. Nobody else edits this file.
// Each area is one folder with one fixed entry file. To change a screen, edit your own area folder only.
export default function App() {
  return (
    <ThemeProvider>
      <UiPreferencesProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/mobile/*" element={<RequireAuth><Suspense fallback={<LoadingState />}><MobileApp /></Suspense></RequireAuth>} />
          <Route path="/console/*" element={<RequireAuth><AppShell><Suspense fallback={<LoadingState />}><ConsoleApp /></Suspense></AppShell></RequireAuth>} />
          <Route path="/alerts" element={<WorkspacePage><AlertsPage /></WorkspacePage>} />
          <Route path="/alerts/:alertId" element={<WorkspacePage><AlertDetailPage /></WorkspacePage>} />
          <Route path="/incidents" element={<WorkspacePage><IncidentsPage /></WorkspacePage>} />
          <Route path="/incidents/:incidentId" element={<WorkspacePage><IncidentDetailPage /></WorkspacePage>} />
          <Route path="/reports" element={<WorkspacePage><ReportsPage /></WorkspacePage>} />
          <Route path="/reports/:sessionId" element={<WorkspacePage><ReportDetailPage /></WorkspacePage>} />
          <Route path="/forecasts" element={<WorkspacePage><ForecastsPage /></WorkspacePage>} />
          <Route path="/forecasts/:forecastId" element={<WorkspacePage><ForecastDetailPage /></WorkspacePage>} />
          <Route path="/analytics" element={<WorkspacePage><AnalyticsPage /></WorkspacePage>} />
          <Route path="/containment" element={<WorkspacePage><ContainmentPage /></WorkspacePage>} />
          <Route path="/replay" element={<WorkspacePage><ReplayStudioPage /></WorkspacePage>} />
          <Route path="/scenarios" element={<WorkspacePage><ScenarioBuilderPage /></WorkspacePage>} />
          <Route path="/hosts" element={<WorkspacePage><HostsPage /></WorkspacePage>} />
          <Route path="/hosts/:hostId" element={<WorkspacePage><HostDetailPage /></WorkspacePage>} />
          <Route path="/audit" element={<WorkspacePage><AuditPage /></WorkspacePage>} />
          <Route path="/system" element={<WorkspacePage><SystemPage /></WorkspacePage>} />
          <Route path="/settings" element={<WorkspacePage><SettingsPage /></WorkspacePage>} />
          <Route path="*" element={<Navigate to="/console" replace />} />
        </Routes>
      </UiPreferencesProvider>
    </ThemeProvider>
  )
}

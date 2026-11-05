import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './shared/AppShell.jsx'
import { LoginPage, RequireAuth } from './shared/AuthContext.jsx'
import { LoadingState } from './shared/components.jsx'
import { ThemeProvider } from './shared/theme-context.jsx'

const MobileApp = lazy(() => import('./areas/mobile/index.jsx'))
const ConsoleApp = lazy(() => import('./areas/console/index.jsx'))
const LandingPage = lazy(() => import('./landing/LandingPage.jsx'))
const IncidentsApp = lazy(() => import('./areas/incidents/index.jsx'))
const ReplayStudioApp = lazy(() => import('./areas/replay/index.jsx'))
const TwinApp = lazy(() => import('./areas/twin/index.jsx'))
const TwinHostsApp = lazy(() => import('./areas/twin/index.jsx').then((module) => ({ default: module.HostsPage })))
const TwinHostDetailApp = lazy(() => import('./areas/twin/index.jsx').then((module) => ({ default: module.HostDetailPage })))
const ForecastsApp = lazy(() => import('./areas/precog/index.jsx').then((module) => ({ default: module.ForecastsPage })))
const ForecastDetailApp = lazy(() => import('./areas/precog/index.jsx').then((module) => ({ default: module.ForecastDetailPage })))
const WhatIfApp = lazy(() => import('./areas/precog/index.jsx').then((module) => ({ default: module.WhatIfPage })))
const AnalyticsApp = lazy(() => import('./areas/precog/index.jsx').then((module) => ({ default: module.AnalyticsPage })))
const ContainmentApp = lazy(() => import('./areas/containment/index.jsx'))
const AlertsPage = lazy(() => import('./areas/ops/alerts.jsx'))
const AlertDetailPage = lazy(() => import('./areas/ops/alert-detail.jsx'))
const ReportsPage = lazy(() => import('./areas/ops/reports.jsx'))
const ReportDetailPage = lazy(() => import('./areas/ops/report-detail.jsx'))
const HelpPage = lazy(() => import('./areas/ops/help.jsx'))
const AboutPage = lazy(() => import('./areas/ops/about.jsx'))
const AuditPage = lazy(() => import('./areas/ops/audit.jsx'))
const SystemPage = lazy(() => import('./areas/ops/system.jsx'))
const SettingsPage = lazy(() => import('./areas/ops/settings.jsx'))
const TopologyExplorerPage = lazy(() => import('./areas/console/topology-explorer.jsx'))
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
        <Route path="/" element={<Suspense fallback={<LoadingState />}><LandingPage /></Suspense>} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/console/topology" element={<WorkspacePage><TopologyExplorerPage /></WorkspacePage>} />
        <Route path="/alerts" element={<WorkspacePage><AlertsPage /></WorkspacePage>} />
        <Route path="/alerts/:alertId" element={<WorkspacePage><AlertDetailPage /></WorkspacePage>} />
        <Route path="/reports" element={<WorkspacePage><ReportsPage /></WorkspacePage>} />
        <Route path="/reports/:sessionId" element={<WorkspacePage><ReportDetailPage /></WorkspacePage>} />
        <Route path="/help" element={<WorkspacePage><HelpPage /></WorkspacePage>} />
        <Route path="/about" element={<WorkspacePage><AboutPage /></WorkspacePage>} />
        <Route path="/audit" element={<WorkspacePage><AuditPage /></WorkspacePage>} />
        <Route path="/system" element={<WorkspacePage><SystemPage /></WorkspacePage>} />
        <Route path="/settings" element={<WorkspacePage><SettingsPage /></WorkspacePage>} />
        <Route path="/mobile/*" element={<RequireAuth><Suspense fallback={<LoadingState />}><MobileApp /></Suspense></RequireAuth>} />
        <Route path="/incidents/*" element={<RequireAuth><Suspense fallback={<LoadingState />}><IncidentsApp /></Suspense></RequireAuth>} />
        <Route path="/replay/*" element={<RequireAuth><AppShell><Suspense fallback={<LoadingState />}><ReplayStudioApp /></Suspense></AppShell></RequireAuth>} />
        <Route path="/scenarios/*" element={<RequireAuth><AppShell><Suspense fallback={<LoadingState />}><ReplayStudioApp /></Suspense></AppShell></RequireAuth>} />
        <Route path="/runs/*" element={<RequireAuth><AppShell><Suspense fallback={<LoadingState />}><ReplayStudioApp /></Suspense></AppShell></RequireAuth>} />
        <Route path="/twin/*" element={<RequireAuth><AppShell><Suspense fallback={<LoadingState />}><TwinApp /></Suspense></AppShell></RequireAuth>} />
        <Route path="/hosts" element={<RequireAuth><AppShell><Suspense fallback={<LoadingState />}><TwinHostsApp /></Suspense></AppShell></RequireAuth>} />
        <Route path="/hosts/:id" element={<RequireAuth><AppShell><Suspense fallback={<LoadingState />}><TwinHostDetailApp /></Suspense></AppShell></RequireAuth>} />
        <Route path="/forecasts" element={<RequireAuth><AppShell><Suspense fallback={<LoadingState />}><ForecastsApp /></Suspense></AppShell></RequireAuth>} />
        <Route path="/forecasts/:id" element={<RequireAuth><AppShell><Suspense fallback={<LoadingState />}><ForecastDetailApp /></Suspense></AppShell></RequireAuth>} />
        <Route path="/lab" element={<RequireAuth><AppShell><Suspense fallback={<LoadingState />}><WhatIfApp /></Suspense></AppShell></RequireAuth>} />
        <Route path="/analytics" element={<RequireAuth><AppShell><Suspense fallback={<LoadingState />}><AnalyticsApp /></Suspense></AppShell></RequireAuth>} />
        <Route path="/containment" element={<RequireAuth><Suspense fallback={<LoadingState />}><ContainmentApp /></Suspense></RequireAuth>} />
        <Route path="/console/*" element={<RequireAuth><AppShell><Suspense fallback={<LoadingState />}><ConsoleApp /></Suspense></AppShell></RequireAuth>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </UiPreferencesProvider>
    </ThemeProvider>
  )
}

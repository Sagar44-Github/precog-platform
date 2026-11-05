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

// Owner: LEAD-CORE. Written once. Nobody else edits this file.
// Each area is one folder with one fixed entry file. To change a screen, edit your own area folder only.
export default function App() {
  return (
    <ThemeProvider>
      <Routes>
        <Route path="/" element={<Suspense fallback={<LoadingState />}><LandingPage /></Suspense>} />
        <Route path="/login" element={<LoginPage />} />
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
    </ThemeProvider>
  )
}

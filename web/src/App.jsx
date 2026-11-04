import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { LoginPage, RequireAuth } from './shared/AuthContext.jsx'
import { LoadingState } from './shared/components.jsx'

const MobileApp = lazy(() => import('./areas/mobile/index.jsx'))
const ConsoleApp = lazy(() => import('./areas/console/index.jsx'))

// Owner: LEAD-CORE. Written once. Nobody else edits this file.
// Each area is one folder with one fixed entry file. To change a screen, edit your own area folder only.
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/mobile/*" element={<RequireAuth><Suspense fallback={<LoadingState />}><MobileApp /></Suspense></RequireAuth>} />
      <Route path="/console/*" element={<RequireAuth><Suspense fallback={<LoadingState />}><ConsoleApp /></Suspense></RequireAuth>} />
      <Route path="*" element={<Navigate to="/console" replace />} />
    </Routes>
  )
}

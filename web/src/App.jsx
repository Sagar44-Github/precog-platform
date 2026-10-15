import { Navigate, Route, Routes } from 'react-router-dom'
import { LoginPage, RequireAuth } from './shared/AuthContext.jsx'
import MobileApp from './areas/mobile/index.jsx'
import ConsoleApp from './areas/console/index.jsx'

// Owner: LEAD-CORE. Written once. Nobody else edits this file.
// Each area is one folder with one fixed entry file. To change a screen, edit your own area folder only.
export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/mobile/*" element={<RequireAuth><MobileApp /></RequireAuth>} />
      <Route path="/console/*" element={<RequireAuth><ConsoleApp /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/mobile" replace />} />
    </Routes>
  )
}

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { AuthProvider } from './shared/AuthContext.jsx'
import './shared/theme.css'

// Owner: LEAD-CORE. Written once. Nobody else edits this file.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter basename="/app">
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)

// Register the service worker so the browser can offer "install" (production build only).
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/app/sw.js', { scope: '/app/' }).catch(() => {})
  })
}

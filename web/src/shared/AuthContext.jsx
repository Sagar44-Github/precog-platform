import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { api, ApiError } from './api.js'
import { ThemeToggle } from './theme-context.jsx'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [username, setUsername] = useState(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    api.me()
      .then((reply) => setUsername(reply.username))
      .catch(() => setUsername(null))
      .finally(() => setChecking(false))
  }, [])

  const value = {
    username,
    checking,
    async login(name, password) {
      const reply = await api.login(name, password)
      setUsername(reply.username)
    },
    async logout() {
      await api.logout()
      setUsername(null)
    },
  }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)

export function RequireAuth({ children }) {
  const { username, checking } = useAuth()
  const location = useLocation()
  if (checking) return <div className="center-page muted">Checking login...</div>
  if (!username) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return children
}

export function LoginPage() {
  const { login, username } = useAuth()
  const location = useLocation()
  const [name, setName] = useState('admin')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  if (username) return <Navigate to={location.state?.from || '/console'} replace />

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setMessage('')
    try {
      await login(name, password)
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : 'Cannot reach the server.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-shell">
      <div className="login-ambient" aria-hidden="true"><i /><i /><i /></div>
      <ThemeToggle className="login-theme-toggle" />
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand-mark" aria-hidden="true"><span>◈</span><i /></div>
        <p className="login-kicker">THREAT OPERATIONS · REPLAY LAB</p>
        <h1>Precog <span>SOC</span></h1>
        <p className="login-copy">See the next move before it happens.</p>
        <div className="login-sim-note"><span className="login-live-dot" /> SIMULATION ENVIRONMENT</div>
        <label className="login-label" htmlFor="login-username">Operator ID</label>
        <input id="login-username" className="field" aria-label="Username" value={name} onChange={(e) => setName(e.target.value)} autoComplete="username" />
        <label className="login-label" htmlFor="login-password">Access key</label>
        <input id="login-password" className="field" aria-label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        <div className="error-text" role="alert">{message}</div>
        <button className="button login-submit" type="submit" disabled={busy}>{busy ? 'Authenticating…' : <><span>Enter command center</span><b aria-hidden="true">↗</b></>}</button>
        <p className="login-footer">Local replay mode <span>·</span> Human-confirmed containment</p>
      </form>
      <div className="login-corner login-corner-left">PREC0G / SOC <span>v1.0</span></div>
      <div className="login-corner login-corner-right">LOCAL NODE · SECURE SESSION</div>
    </div>
  )
}

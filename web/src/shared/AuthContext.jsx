import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { api, ApiError } from './api.js'

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

  if (username) return <Navigate to={location.state?.from || '/mobile'} replace />

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
    <div className="center-page">
      <form className="card" style={{ width: 'min(360px, 100%)' }} onSubmit={submit}>
        <h1 style={{ marginTop: 0 }}>Precog SOC</h1>
        <p className="muted">Demo account sign-in</p>
        <input className="field" aria-label="Username" value={name} onChange={(e) => setName(e.target.value)} autoComplete="username" />
        <input className="field" aria-label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        <div className="error-text" role="alert">{message}</div>
        <button className="button" type="submit" disabled={busy}>{busy ? 'Signing in...' : 'Sign in'}</button>
      </form>
    </div>
  )
}

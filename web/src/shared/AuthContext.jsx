import { createContext, lazy, Suspense, useContext, useEffect, useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { api, ApiError } from './api.js'
import { ThemeToggle } from './theme-context.jsx'
import ThemeLogo from './ThemeLogo.jsx'
import { Icon } from './icons.jsx'

const SignInScene = lazy(() => import('./SignInScene.jsx'))

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [username, setUsername] = useState(null)
  const [role, setRole] = useState(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    api.me()
      .then((reply) => { setUsername(reply.username); setRole(reply.role || null) })
      .catch(() => { setUsername(null); setRole(null) })
      .finally(() => setChecking(false))
  }, [])

  const value = {
    username,
    role,
    readOnly: role === 'viewer',
    checking,
    async login(name, password) {
      const reply = await api.login(name, password)
      setUsername(reply.username)
      setRole(reply.role || null)
    },
    async logout() {
      await api.logout()
      setUsername(null)
      setRole(null)
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
  const [showPassword, setShowPassword] = useState(false)

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
      <ThemeToggle className="login-theme-toggle" />
      <main className="signin-layout">
        <section className="signin-visual" aria-label="Precog threat detection model">
          <header className="signin-visual-header"><Link to="/" className="signin-brand"><ThemeLogo /><span>PRECOG <b>SOC</b></span></Link><span className="signin-demo-label"><i /> SIMULATION</span></header>
          <div className="signin-story"><p className="login-kicker">DETECT · RECONSTRUCT · PREDICT · CONTAIN</p><h1>See the next move<br />before it happens.</h1><p>A simulated network, a reconstructed attack path, and a model-based forecast of where it may go next.</p></div>
          <div className="signin-network-frame"><div className="signin-scene-caption"><span><i className="signin-key observed" /> OBSERVED PATH</span><span><i className="signin-key predicted" /> MODEL ESTIMATE</span><span><i className="signin-key isolated" /> ISOLATION</span></div><Suspense fallback={<div className="signin-scene signin-scene-loading" aria-label="Loading network visualization" />}><SignInScene /></Suspense><div className="signin-host-labels"><span>Workstation A</span><span>Detection point</span><span>Web Server B</span><span>File Server</span></div></div>
          <p className="signin-honesty">Illustrative 3D replay · Six-host demo network · No live traffic</p>
        </section>
        <section className="signin-auth-wrap">
          <form className="login-card" onSubmit={submit}>
            <div className="login-brand-mark"><ThemeLogo /></div>
            <p className="login-kicker">OPERATOR ACCESS</p>
            <h2>Sign in to Precog <span>SOC</span></h2>
            <p className="login-copy">Use your demo operator account to open the simulation workspace.</p>
            <div className="login-sim-note"><span className="login-live-dot" /> SIMULATION ENVIRONMENT</div>
            <label className="login-label" htmlFor="login-username">Operator ID</label>
            <input id="login-username" className="field" aria-label="Username" value={name} onChange={(e) => setName(e.target.value)} autoComplete="username" />
            <label className="login-label" htmlFor="login-password">Access key</label>
            <div className="signin-password-wrap"><input id="login-password" className="field" aria-label="Password" type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /><button type="button" className="signin-password-toggle" onClick={() => setShowPassword((shown) => !shown)} aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}><Icon name={showPassword ? 'eye-off' : 'eye'} size={18} /></button></div>
            <div className="error-text" role="alert">{message}</div>
            <button className="button login-submit" type="submit" disabled={busy}>{busy ? <><span className="signin-spinner" aria-hidden="true" /> Authenticating…</> : <><span>Enter command center</span><b aria-hidden="true">↗</b></>}</button>
            <p className="login-footer">Secure session <span>·</span> Human-confirmed containment</p>
          </form>
          <footer className="signin-auth-foot"><span>PREC0G / SOC · v1.0</span><Link to="/">Back to product overview</Link></footer>
        </section>
      </main>
    </div>
  )
}

import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext.jsx'
import { SimulationBadge } from './components.jsx'
import { Icon } from './icons.jsx'
import { ThemeToggle, useTheme } from './theme-context.jsx'
import { apiGet } from './api.js'
import './app-shell.css'

const CONSOLE_WIDTH = 1024

function useConsoleHandoff() {
  const [handoff, setHandoff] = useState(() => typeof window !== 'undefined' && window.innerWidth < CONSOLE_WIDTH)
  useEffect(() => {
    const query = window.matchMedia(`(max-width: ${CONSOLE_WIDTH - 1}px)`)
    const update = () => setHandoff(query.matches)
    update()
    query.addEventListener?.('change', update)
    return () => query.removeEventListener?.('change', update)
  }, [])
  return handoff
}

function commandEvent(detail) {
  window.dispatchEvent(new CustomEvent('precog:console-command', { detail }))
}

export function CommandPalette({ open, onClose }) {
  const navigate = useNavigate()
  const { theme, toggleTheme } = useTheme()
  const { role } = useAuth()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef(null)
  const dialogRef = useRef(null)

  const commands = useMemo(() => [
    { label: 'Open live console', detail: 'Go to the 3D replay console', icon: 'activity', keywords: 'workspace desktop', run: () => navigate('/console') },
    { label: 'Open mobile SOC', detail: 'Open the phone PWA screens', icon: 'smartphone', keywords: 'phone pwa', run: () => navigate('/mobile') },
    { label: 'Open incident investigations', detail: 'Review correlated alerts and analyst notes', icon: 'shield', keywords: 'cases incident investigation', run: () => navigate('/incidents') },
    { label: 'Open Precog forecasts', detail: 'Review ranked estimates and their observed outcomes', icon: 'activity', keywords: 'forecast prediction explainability', run: () => navigate('/forecasts') },
    { label: 'Open what-if lab', detail: 'Explore containment counterfactuals without changing the replay', icon: 'sliders', keywords: 'what if counterfactual containment', run: () => navigate('/lab') },
    { label: 'Open model analytics', detail: 'Review calibration and run held-out experiments', icon: 'clock', keywords: 'evaluation metrics model calibration', run: () => navigate('/analytics') },
    { label: 'Open response governance', detail: 'Preview and confirm simulation-only response playbooks', icon: 'shield', keywords: 'containment actions approvals releases playbooks', run: () => navigate('/containment') },
    { label: 'Open network twin', detail: 'Explore demo assets, paths and recorded states', icon: 'network', keywords: 'hosts topology digital twin', run: () => navigate('/twin') },
    { label: 'Open replay studio', detail: 'Step through a scripted replay and compare runs', icon: 'play', keywords: 'replay studio runs timeline', run: () => navigate('/replay') },
    { label: 'Open scenario library', detail: 'Choose or build a scripted scenario', icon: 'layers', keywords: 'scenario builder library', run: () => navigate('/scenarios') },
    { label: 'Open run history', detail: 'Review completed runs and compare outcomes', icon: 'clock', keywords: 'runs history compare', run: () => navigate('/runs') },
    { label: 'Show alert stream', detail: 'Open alerts in the console panel', icon: 'activity', keywords: 'alerts events', run: () => commandEvent({ type: 'view', view: 'alerts' }) },
    { label: 'Show session report', detail: 'Open the current session report panel', icon: 'sliders', keywords: 'reports metrics', run: () => commandEvent({ type: 'view', view: 'reports' }) },
    ...(role === 'viewer' ? [] : [{ label: 'Start Golden Path replay', detail: 'Start the deterministic simulation', icon: 'play', keywords: 'demo replay simulation', run: () => commandEvent({ type: 'start-demo' }) }]),
    { label: `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`, detail: 'Change the display theme', icon: theme === 'dark' ? 'sun' : 'moon', keywords: 'appearance color', run: toggleTheme },
  ], [navigate, role, theme, toggleTheme])
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return commands
    return commands.filter((command) => `${command.label} ${command.detail} ${command.keywords}`.toLowerCase().includes(needle))
  }, [commands, query])

  useEffect(() => {
    if (!open) return undefined
    const onKeyDown = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose() }
      if (event.key === 'ArrowDown' && filtered.length) { event.preventDefault(); setActive((index) => (index + 1) % filtered.length) }
      if (event.key === 'ArrowUp' && filtered.length) { event.preventDefault(); setActive((index) => (index - 1 + filtered.length) % filtered.length) }
      if (event.key === 'Enter' && filtered[active]) { event.preventDefault(); filtered[active].run(); onClose() }
      if (event.key === 'Tab') {
        const focusable = dialogRef.current?.querySelectorAll('input, button:not(:disabled)')
        if (!focusable?.length) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose, filtered, active])

  useEffect(() => {
    if (!open) return undefined
    setQuery('')
    setActive(0)
    const focus = window.setTimeout(() => inputRef.current?.focus(), 0)
    return () => window.clearTimeout(focus)
  }, [open])

  if (!open) return null
  return (
    <div className="command-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section ref={dialogRef} className="command-dialog" role="dialog" aria-modal="true" aria-labelledby="command-title">
        <h2 id="command-title" className="sr-only">Command palette</h2>
        <div className="command-search-row">
          <Icon name="search" />
          <input ref={inputRef} value={query} onChange={(event) => { setQuery(event.target.value); setActive(0) }} placeholder="Search pages and actions…" aria-label="Search commands" aria-controls="command-options" aria-activedescendant={filtered[active] ? `command-option-${active}` : undefined} />
          <kbd>ESC</kbd>
        </div>
        <p className="command-section-label">COMMANDS</p>
        <div id="command-options" className="command-options" role="listbox" aria-label="Commands">
          {filtered.length ? filtered.map((command, index) => (
            <button
              type="button"
              role="option"
              id={`command-option-${index}`}
              aria-selected={index === active}
              className="command-option"
              key={command.label}
              onMouseEnter={() => setActive(index)}
              onClick={() => { command.run(); onClose() }}
            >
              <span className="command-option-icon"><Icon name={command.icon} size={18} /></span>
              <span className="command-option-copy"><b>{command.label}</b><small>{command.detail}</small></span>
              {index === active && <kbd>↵</kbd>}
            </button>
          )) : <p className="command-empty">No matching commands.</p>}
        </div>
        <footer className="command-hints"><span><kbd>↑</kbd><kbd>↓</kbd> to navigate</span><span><kbd>↵</kbd> to run</span></footer>
      </section>
    </div>
  )
}

export function ConsoleHandoff() {
  return (
    <main className="console-handoff">
      <div className="handoff-topline">
        <Link className="handoff-brand" to="/console"><span className="brand-mark"><Icon name="activity" /></span><span>Precog <b>SOC</b></span></Link>
        <div className="handoff-actions"><SimulationBadge /><ThemeToggle /></div>
      </div>
      <section className="handoff-card">
        <div className="handoff-orbit" aria-hidden="true"><span /><i /><b /></div>
        <p className="app-eyebrow">DESKTOP WORKSPACE · 1024 PX MINIMUM</p>
        <h1>Open the console on a wider screen</h1>
        <p className="handoff-copy">The 3D topology is designed for a desktop workspace. The mobile SOC keeps alerts, forecasts and session history ready on this device.</p>
        <Link to="/mobile" className="handoff-link">Open mobile SOC <Icon name="chevron" size={17} /></Link>
      </section>
      <p className="handoff-footnote">All events and responses shown here are simulated.</p>
    </main>
  )
}

export default function AppShell({ children }) {
  const { username, role, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [openIncidents, setOpenIncidents] = useState(0)
  const [incidentNotice, setIncidentNotice] = useState(false)
  const [pendingResponses, setPendingResponses] = useState(0)
  const handoff = useConsoleHandoff() && location.pathname.startsWith('/console')
  const pageTitle = location.pathname.startsWith('/replay') ? 'Replay studio'
    : location.pathname.startsWith('/twin') ? 'Network twin'
      : location.pathname.startsWith('/hosts') ? 'Asset directory'
    : location.pathname.includes('/edit') || location.pathname.endsWith('/new') ? 'Scenario builder'
      : location.pathname.startsWith('/scenarios') ? 'Scenario library'
    : location.pathname.startsWith('/forecasts') ? (location.pathname.split('/').length > 2 ? 'Forecast explanation' : 'Precog forecasts')
      : location.pathname.startsWith('/lab') ? 'What-if lab'
        : location.pathname.startsWith('/analytics') ? 'Model analytics'
      : location.pathname.startsWith('/containment') ? 'Response governance'
    : location.pathname.includes('/compare') ? 'Run comparison'
          : location.pathname.startsWith('/runs') ? 'Run history' : 'Live console'
  const closePalette = () => setPaletteOpen(false)

  useEffect(() => {
    if (!username) return undefined
    let alive = true
    const refresh = async () => {
      try {
        const result = await apiGet('/api/x/incidents?status=open&limit=1')
        if (!alive) return
        setOpenIncidents((previous) => {
          if (result.total > previous) setIncidentNotice(true)
          return result.total
        })
      } catch { /* the console still works if incident polling is unavailable */ }
    }
    refresh()
    const timer = window.setInterval(refresh, 5000)
    return () => { alive = false; window.clearInterval(timer) }
  }, [username])

  useEffect(() => {
    if (!username) return undefined
    let alive = true
    const refresh = async () => {
      try {
        const records = await apiGet('/api/x/containment/governance?limit=100')
        if (!alive) return
        const pending = [...records.approvals, ...records.releases].filter((item) => ['pending_approval', 'pending_confirmation'].includes(item.status)).length
        setPendingResponses(pending)
      } catch { /* governance can be opened directly if polling is unavailable */ }
    }
    refresh()
    const timer = window.setInterval(refresh, 5000)
    return () => { alive = false; window.clearInterval(timer) }
  }, [username])

  useEffect(() => {
    const onKeyDown = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPaletteOpen((open) => !open)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  async function signOut() {
    try { await logout() } finally { navigate('/login', { replace: true }) }
  }

  if (handoff) return <ConsoleHandoff />

  return (
    <div className="app-shell">
      <aside className="app-sidebar" aria-label="Workspace navigation">
        <Link to="/console" className="app-brand">
          <span className="brand-mark"><Icon name="activity" size={21} /></span>
          <span className="brand-copy"><b>Precog <strong>SOC</strong></b><small>SIMULATION LAB</small></span>
        </Link>
        <p className="app-nav-caption">WORKSPACE</p>
        <nav className="app-primary-nav" aria-label="Main navigation">
          <NavLink to="/console" end className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="activity" /><span>Live console</span><kbd>1</kbd>
          </NavLink>
          <NavLink to="/mobile" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="smartphone" /><span>Mobile SOC</span><kbd>2</kbd>
          </NavLink>
          <NavLink to="/incidents" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="shield" /><span>Incidents</span>{openIncidents > 0 && <b className="app-nav-count" aria-label={`${openIncidents} open incidents`}>{openIncidents}</b>}
          </NavLink>
          <NavLink to="/twin" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="network" /><span>Network twin</span>
          </NavLink>
          <NavLink to="/hosts" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="server" /><span>Hosts</span>
          </NavLink>
          <NavLink to="/replay" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="play" /><span>Replay studio</span>
          </NavLink>
          <NavLink to="/scenarios" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="layers" /><span>Scenarios</span>
          </NavLink>
          <NavLink to="/runs" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="clock" /><span>Run history</span>
          </NavLink>
          <NavLink to="/forecasts" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="activity" /><span>Forecasts</span>
          </NavLink>
          <NavLink to="/lab" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="sliders" /><span>What-if lab</span>
          </NavLink>
          <NavLink to="/analytics" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="clock" /><span>Analytics</span>
          </NavLink>
          <NavLink to="/containment" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="shield" /><span>Response governance</span>{pendingResponses > 0 && <b className="app-nav-count" aria-label={`${pendingResponses} pending response approvals`}>{pendingResponses}</b>}
          </NavLink>
        </nav>
        <div className="app-sidebar-spacer" />
        <div className="app-simulation-note"><span className="status-square" /> SIMULATED ENVIRONMENT</div>
        <div className="app-account">
          <span className="account-avatar" aria-hidden="true">{(username || 'A').slice(0, 1).toUpperCase()}</span>
          <span className="account-copy"><b>{username || 'Operator'}</b><small>{(role || 'operator').toUpperCase()} ROLE</small></span>
          <button type="button" className="icon-button account-logout" onClick={signOut} aria-label="Sign out" title="Sign out"><Icon name="logout" size={17} /></button>
        </div>
      </aside>
      <div className="app-main">
        <header className="app-topbar">
          <div className="app-breadcrumb"><span>Workspace</span><Icon name="chevron" size={15} /><h1>{pageTitle}</h1></div>
          <div className="app-top-actions">
            {incidentNotice && <Link className="incident-notice" to="/incidents" onClick={() => setIncidentNotice(false)}>New incident <span aria-hidden="true">↗</span></Link>}
            <button type="button" className="command-trigger" onClick={() => setPaletteOpen(true)} aria-haspopup="dialog" aria-expanded={paletteOpen}>
              <Icon name="search" size={17} /><span>Search commands</span><kbd><Icon name="command" size={12} /> K</kbd>
            </button>
            <ThemeToggle className="top-theme-toggle" />
            <SimulationBadge />
          </div>
        </header>
        <div className="app-shell-content">{children}</div>
      </div>
      <CommandPalette open={paletteOpen} onClose={closePalette} />
    </div>
  )
}

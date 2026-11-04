import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext.jsx'
import { SimulationBadge } from './components.jsx'
import { Icon } from './icons.jsx'
import { ThemeToggle, useTheme } from './theme-context.jsx'
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
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef(null)
  const dialogRef = useRef(null)

  const commands = useMemo(() => [
    { label: 'Open live console', detail: 'Go to the 3D replay console', icon: 'activity', keywords: 'workspace desktop', run: () => navigate('/console') },
    { label: 'Open mobile SOC', detail: 'Open the phone PWA screens', icon: 'smartphone', keywords: 'phone pwa', run: () => navigate('/mobile') },
    { label: 'Show alert stream', detail: 'Open alerts in the console panel', icon: 'activity', keywords: 'alerts events', run: () => commandEvent({ type: 'view', view: 'alerts' }) },
    { label: 'Show session report', detail: 'Open the current session report panel', icon: 'sliders', keywords: 'reports metrics', run: () => commandEvent({ type: 'view', view: 'reports' }) },
    { label: 'Start Golden Path replay', detail: 'Start the deterministic simulation', icon: 'play', keywords: 'demo replay simulation', run: () => commandEvent({ type: 'start-demo' }) },
    { label: `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`, detail: 'Change the display theme', icon: theme === 'dark' ? 'sun' : 'moon', keywords: 'appearance color', run: toggleTheme },
  ], [navigate, theme, toggleTheme])
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
  const { username, logout } = useAuth()
  const navigate = useNavigate()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const handoff = useConsoleHandoff()
  const closePalette = () => setPaletteOpen(false)

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
        <Link to="/console" className="app-brand" aria-label="Precog SOC home">
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
        </nav>
        <div className="app-sidebar-spacer" />
        <div className="app-simulation-note"><span className="status-square" /> SIMULATED ENVIRONMENT</div>
        <div className="app-account">
          <span className="account-avatar" aria-hidden="true">{(username || 'A').slice(0, 1).toUpperCase()}</span>
          <span className="account-copy"><b>{username || 'Operator'}</b><small>DEMO OPERATOR</small></span>
          <button type="button" className="icon-button account-logout" onClick={signOut} aria-label="Sign out" title="Sign out"><Icon name="logout" size={17} /></button>
        </div>
      </aside>
      <div className="app-main">
        <header className="app-topbar">
          <div className="app-breadcrumb"><span>Workspace</span><Icon name="chevron" size={15} /><h1>Live console</h1></div>
          <div className="app-top-actions">
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

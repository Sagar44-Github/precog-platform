import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext.jsx'
import { SimulationBadge } from './components.jsx'
import { Icon } from './icons.jsx'
import { ThemeToggle, useTheme } from './theme-context.jsx'
import ThemeLogo from './ThemeLogo.jsx'
import { apiGet } from './api.js'
import GuidedTour from './GuidedTour.jsx'
import './app-shell.css'

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
    { label: 'Open incident investigations', detail: 'Review correlated alerts and analyst notes', icon: 'shield', keywords: 'cases incident investigation', run: () => navigate('/incidents') },
    { label: 'Open Precog forecasts', detail: 'Review ranked estimates and their observed outcomes', icon: 'activity', keywords: 'forecast prediction explainability', run: () => navigate('/forecasts') },
    { label: 'Open what-if lab', detail: 'Explore containment counterfactuals without changing the replay', icon: 'sliders', keywords: 'what if counterfactual containment', run: () => navigate('/lab') },
    { label: 'Open model analytics', detail: 'Review calibration and run held-out experiments', icon: 'clock', keywords: 'evaluation metrics model calibration', run: () => navigate('/analytics') },
    { label: 'Open response governance', detail: 'Preview and confirm simulation-only response playbooks', icon: 'shield', keywords: 'containment actions approvals releases playbooks', run: () => navigate('/containment') },
    { label: 'Open network twin', detail: 'Explore demo assets, paths and recorded states', icon: 'network', keywords: 'hosts topology digital twin', run: () => navigate('/twin') },
    { label: 'Open replay studio', detail: 'Step through a scripted replay and compare runs', icon: 'play', keywords: 'replay studio runs timeline', run: () => navigate('/replay') },
    { label: 'Open scenario library', detail: 'Choose or build a scripted scenario', icon: 'layers', keywords: 'scenario builder library', run: () => navigate('/scenarios') },
    { label: 'Open run history', detail: 'Review completed runs and compare outcomes', icon: 'clock', keywords: 'runs history compare', run: () => navigate('/runs') },
    { label: 'Open alert explorer', detail: 'Search and review detection events', icon: 'activity', keywords: 'alerts events', run: () => navigate('/alerts') },
    { label: 'Open session reports', detail: 'Review replay reports and timelines', icon: 'sliders', keywords: 'reports metrics', run: () => navigate('/reports') },
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

const MONITORING_LINKS = [
  { to: '/alerts', label: 'Alerts', icon: 'alerts' },
  { to: '/reports', label: 'Reports', icon: 'reports' },
  { to: '/audit', label: 'Audit log', icon: 'audit' },
  { to: '/system', label: 'System health', icon: 'system' },
]

function MonitoringOperationsNav() {
  const location = useLocation()
  const triggerRef = useRef(null)
  const menuRef = useRef(null)
  const closeTimer = useRef(null)
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState(null)
  const active = MONITORING_LINKS.some(({ to }) => location.pathname === to || location.pathname.startsWith(`${to}/`))

  function clearCloseTimer() {
    if (closeTimer.current) window.clearTimeout(closeTimer.current)
    closeTimer.current = null
  }

  function scheduleClose(delay = 170) {
    clearCloseTimer()
    closeTimer.current = window.setTimeout(() => setOpen(false), delay)
  }

  function openAndFocus(index = 0) {
    clearCloseTimer()
    setOpen(true)
    window.requestAnimationFrame(() => menuRef.current?.querySelectorAll('[role="menuitem"]')[index]?.focus())
  }

  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  useEffect(() => () => clearCloseTimer(), [])

  useEffect(() => {
    if (!open) return undefined
    const update = () => {
      const rect = triggerRef.current?.getBoundingClientRect()
      if (!rect) return
      const menuHeight = menuRef.current?.getBoundingClientRect().height || 190
      setPosition({
        left: Math.min(rect.right + 8, window.innerWidth - 232),
        top: Math.max(8, Math.min(rect.top, window.innerHeight - menuHeight - 8)),
      })
    }
    update()
    window.addEventListener('resize', update)
    document.addEventListener('scroll', update, true)
    const closeOnOutsidePointer = (event) => {
      if (triggerRef.current?.contains(event.target) || menuRef.current?.contains(event.target)) return
      setOpen(false)
    }
    const closeOnEscape = (event) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      setOpen(false)
      triggerRef.current?.focus()
    }
    document.addEventListener('pointerdown', closeOnOutsidePointer)
    window.addEventListener('keydown', closeOnEscape)
    return () => {
      window.removeEventListener('resize', update)
      document.removeEventListener('scroll', update, true)
      document.removeEventListener('pointerdown', closeOnOutsidePointer)
      window.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  function onTriggerKeyDown(event) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      openAndFocus(event.key === 'ArrowUp' ? MONITORING_LINKS.length - 1 : 0)
    } else if (event.key === 'Escape' && open) {
      event.preventDefault()
      setOpen(false)
    }
  }

  function onMenuKeyDown(event) {
    const items = Array.from(menuRef.current?.querySelectorAll('[role="menuitem"]') || [])
    const current = items.indexOf(document.activeElement)
    let next = null
    if (event.key === 'ArrowDown') next = (current + 1) % items.length
    else if (event.key === 'ArrowUp') next = (current - 1 + items.length) % items.length
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = items.length - 1
    else if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
      triggerRef.current?.focus()
      return
    }
    if (next !== null) {
      event.preventDefault()
      items[next]?.focus()
    }
  }

  function closeIfFocusLeaves(event) {
    if (event.relatedTarget === triggerRef.current || menuRef.current?.contains(event.relatedTarget)) return
    scheduleClose(0)
  }

  return <>
    <button
      ref={triggerRef}
      type="button"
      className={`app-nav-link app-nav-category-trigger${active ? ' is-active' : ''}`}
      aria-haspopup="menu"
      aria-expanded={open}
      aria-label="Monitoring & Operations"
      onClick={() => { clearCloseTimer(); setOpen(true) }}
      onPointerEnter={(event) => { if (event.pointerType === 'mouse') { clearCloseTimer(); setOpen(true) } }}
      onPointerLeave={(event) => { if (event.pointerType === 'mouse') scheduleClose() }}
      onFocus={() => { clearCloseTimer(); setOpen(true) }}
      onBlur={closeIfFocusLeaves}
      onKeyDown={onTriggerKeyDown}
    >
      <Icon name="system" /><span>Monitoring &amp; Operations</span><Icon className="app-nav-chevron" name="chevron" size={14} />
    </button>
    {open && typeof document !== 'undefined' && createPortal(
      <div
        ref={menuRef}
        id="monitoring-operations-menu"
        className="app-nav-menu"
        style={position ? { left: position.left, top: position.top } : undefined}
        role="menu"
        aria-label="Monitoring & Operations pages"
        onMouseEnter={clearCloseTimer}
        onMouseLeave={() => scheduleClose()}
        onFocus={clearCloseTimer}
        onBlur={closeIfFocusLeaves}
        onKeyDown={onMenuKeyDown}
      >
        {MONITORING_LINKS.map(({ to, label, icon }) => <NavLink key={to} to={to} role="menuitem" className={({ isActive }) => `app-nav-menu-link${isActive ? ' is-active' : ''}`} onClick={() => setOpen(false)}>
          <Icon name={icon} size={17} /><span>{label}</span>
        </NavLink>)}
      </div>, document.body,
    )}
  </>
}

export default function AppShell({ children }) {
  const { username, role, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [openIncidents, setOpenIncidents] = useState(0)
  const [incidentNotice, setIncidentNotice] = useState(false)
  const [pendingResponses, setPendingResponses] = useState(0)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [mobileOpsOpen, setMobileOpsOpen] = useState(false)
  const pageTitle = location.pathname.startsWith('/alerts') ? 'Alert explorer'
    : location.pathname.startsWith('/reports') ? 'Session reports'
      : location.pathname.startsWith('/incidents') ? 'Incident investigations'
        : location.pathname.startsWith('/audit') ? 'Audit log'
          : location.pathname.startsWith('/system') ? 'System health'
            : location.pathname.startsWith('/settings') ? 'Settings'
              : location.pathname.startsWith('/help') ? 'Operator help'
                : location.pathname.startsWith('/about') ? 'About Precog SOC'
    : location.pathname.startsWith('/replay') ? 'Replay studio'
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

  useEffect(() => { setMobileNavOpen(false); setMobileOpsOpen(false) }, [location.pathname])

  const mobileLinks = [
    ['/console', 'Live console', 'activity'], ['/incidents', 'Incidents', 'shield'],
    ['/twin', 'Network twin', 'network'], ['/hosts', 'Hosts & assets', 'server'],
    ['/replay', 'Replay studio', 'play'], ['/scenarios', 'Scenarios', 'layers'],
    ['/runs', 'Run history', 'clock'], ['/forecasts', 'Forecasts', 'activity'],
    ['/lab', 'What-if lab', 'sliders'], ['/analytics', 'Analytics', 'clock'],
    ['/containment', 'Response governance', 'shield'], ['/settings', 'Settings', 'settings'],
  ]

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

  return (
    <div className="app-shell">
      <aside className="app-sidebar" aria-label="Workspace navigation">
        <Link to="/" className="app-brand" title="Return to landing page">
          <ThemeLogo className="brand-mark" />
          <span className="brand-copy"><b>Precog <strong>SOC</strong></b><small>SIMULATION LAB</small></span>
        </Link>
        <p className="app-nav-caption">WORKSPACE</p>
        <nav className="app-primary-nav" aria-label="Main navigation">
          <NavLink to="/console" end title="Live console" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="activity" /><span>Live console</span>
          </NavLink>
          <NavLink to="/incidents" title="Incidents" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="shield" /><span>Incidents</span>{openIncidents > 0 && <b className="app-nav-count" aria-label={`${openIncidents} open incidents`}>{openIncidents}</b>}
          </NavLink>
          <NavLink to="/twin" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="network" /><span>Network twin</span>
          </NavLink>
          <NavLink to="/hosts" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}>
            <Icon name="server" /><span>Hosts & assets</span>
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
          <MonitoringOperationsNav />
          <NavLink to="/settings" className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}><Icon name="settings" /><span>Settings</span></NavLink>
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
          <button type="button" className="mobile-menu-trigger" aria-label="Open navigation" aria-expanded={mobileNavOpen} onClick={() => setMobileNavOpen(true)}><span /><span /><span /></button>
          <Link to="/" className="mobile-brand" aria-label="Precog SOC home"><ThemeLogo className="brand-mark" /></Link>
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
        <GuidedTour />
      </div>
      <nav className="mobile-bottom-nav" aria-label="Primary mobile navigation">
        <NavLink to="/console" end className={({ isActive }) => `mobile-bottom-link${isActive ? ' is-active' : ''}`}><Icon name="activity" /><span>Console</span></NavLink>
        <NavLink to="/incidents" className={({ isActive }) => `mobile-bottom-link${isActive ? ' is-active' : ''}`}><Icon name="shield" />{openIncidents > 0 && <i className="mobile-nav-dot" aria-label={`${openIncidents} open incidents`} />}<span>Incidents</span></NavLink>
        <NavLink to="/twin" className={({ isActive }) => `mobile-bottom-link${isActive ? ' is-active' : ''}`}><Icon name="network" /><span>Network</span></NavLink>
        <button type="button" className={`mobile-bottom-link${mobileNavOpen ? ' is-active' : ''}`} aria-expanded={mobileNavOpen} onClick={() => setMobileNavOpen(true)}><Icon name="layers" /><span>More</span></button>
      </nav>
      {mobileNavOpen && <div className="mobile-nav-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget) setMobileNavOpen(false) }}>
        <section className="mobile-nav-drawer" role="dialog" aria-modal="true" aria-label="Workspace navigation">
          <header><Link to="/" className="mobile-drawer-brand"><ThemeLogo className="brand-mark" /><b>Precog <strong>SOC</strong></b></Link><button type="button" className="icon-button" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)}><Icon name="close" /></button></header>
          <div className="mobile-drawer-scroll">
            {mobileLinks.slice(0, 11).map(([to, label, icon]) => <NavLink key={to} to={to} className={({ isActive }) => `mobile-drawer-link${isActive ? ' is-active' : ''}`}><Icon name={icon} size={19} /><span>{label}</span>{to === '/incidents' && openIncidents > 0 && <b className="app-nav-count">{openIncidents}</b>}{to === '/containment' && pendingResponses > 0 && <b className="app-nav-count">{pendingResponses}</b>}</NavLink>)}
            <button type="button" className="mobile-drawer-link mobile-ops-toggle" aria-expanded={mobileOpsOpen} onClick={() => setMobileOpsOpen((open) => !open)}><Icon name="system" size={19} /><span>Monitoring &amp; Operations</span><Icon className="mobile-ops-chevron" name="chevron" size={16} /></button>
            {mobileOpsOpen && <div className="mobile-ops-links">{MONITORING_LINKS.map(({ to, label, icon }) => <NavLink key={to} to={to} className={({ isActive }) => `mobile-drawer-link${isActive ? ' is-active' : ''}`}><Icon name={icon} size={18} /><span>{label}</span></NavLink>)}</div>}
            <NavLink to="/settings" className={({ isActive }) => `mobile-drawer-link mobile-settings-link${isActive ? ' is-active' : ''}`}><Icon name="settings" size={19} /><span>Settings</span></NavLink>
          </div>
          <footer><span className="mobile-user-avatar">{(username || 'A').slice(0, 1).toUpperCase()}</span><span><b>{username}</b><small>{(role || 'operator').toUpperCase()} ROLE</small></span><button type="button" className="icon-button" onClick={signOut} aria-label="Sign out"><Icon name="logout" size={18} /></button></footer>
        </section>
      </div>}
      <CommandPalette open={paletteOpen} onClose={closePalette} />
    </div>
  )
}

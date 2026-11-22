import { createContext, useCallback, useContext, useEffect, useState } from 'react'

// Shared components (owner: LEAD-CORE). GRAPH and VIZ import these; they never copy them.

/** The permanent "this is a simulation" pill (UI/UX brief 6.1). */
export function SimulationBadge() {
  return <span className="sim-badge" aria-label="Everything in this app is simulated">SIMULATION</span>
}

/** The amber strip shown when the backend has not answered for a while (brief 6.8). */
export function StaleBanner({ stale }) {
  if (!stale) return null
  return <div className="stale-banner" role="status">Connection lost: showing old data</div>
}

/** An empty list or card (brief 6.16). */
export function EmptyState({ children }) {
  return <div className="empty-state">{children}</div>
}

/** Grey bars shown while the first answer is on its way (brief 6.16). */
export function LoadingState({ lines = 3 }) {
  return (
    <div aria-busy="true" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => <div className="skeleton" key={i} style={{ width: `${90 - i * 15}%` }} />)}
    </div>
  )
}

/** A native, keyboard-operable section disclosure with a persistent title and status. */
export function CollapsibleSection({ title, meta, children, open = false, className = '' }) {
  return <details className={`disclosure ${className}`.trim()} open={open}>
    <summary><span>{title}</span>{meta && <small>{meta}</small>}</summary>
    <div className="disclosure-body">{children}</div>
  </details>
}

const ToastContext = createContext({ show: () => {} })

/** Wrap a screen with this, then call useToast().show('text') (brief 6.14). Closes by itself after 4 seconds. */
export function ToastProvider({ children, seconds = 4 }) {
  const [notice, setNotice] = useState(null)
  const show = useCallback((value) => {
    const next = typeof value === 'string'
      ? { kind: 'info', title: 'Simulation update', message: value }
      : value && typeof value === 'object'
        ? { kind: 'info', ...value }
        : null
    if (!next?.message) return
    setNotice({ ...next, id: `${Date.now()}-${Math.random()}` })
  }, [])
  useEffect(() => {
    if (!notice) return undefined
    const timer = setTimeout(() => setNotice(null), seconds * 1000)
    return () => clearTimeout(timer)
  }, [notice, seconds])
  const kind = notice?.kind === 'error' ? 'error' : notice?.kind === 'success' ? 'success' : 'info'
  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      {notice && <div className={`toast toast-${kind}`} role={kind === 'error' ? 'alert' : 'status'} aria-live={kind === 'error' ? 'assertive' : 'polite'} key={notice.id}>
        <span className="toast-mark" aria-hidden="true">{kind === 'success' ? '✓' : kind === 'error' ? '!' : 'i'}</span>
        <div className="toast-copy">
          {notice.status && <span className="toast-status">{notice.status}</span>}
          {notice.title && <strong>{notice.title}</strong>}
          <p>{notice.message}</p>
        </div>
        <button type="button" className="toast-dismiss" aria-label="Dismiss notification" onClick={() => setNotice(null)}>×</button>
      </div>}
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)

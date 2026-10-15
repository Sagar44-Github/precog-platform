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

const ToastContext = createContext({ show: () => {} })

/** Wrap a screen with this, then call useToast().show('text') (brief 6.14). Closes by itself after 4 seconds. */
export function ToastProvider({ children, seconds = 4 }) {
  const [message, setMessage] = useState('')
  const show = useCallback((text) => setMessage(text), [])
  useEffect(() => {
    if (!message) return undefined
    const timer = setTimeout(() => setMessage(''), seconds * 1000)
    return () => clearTimeout(timer)
  }, [message, seconds])
  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      {message && <div className="toast" role="status">{message}</div>}
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)

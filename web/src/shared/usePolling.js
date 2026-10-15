import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from './api.js'
import { applyReply, isStale } from './pollingLogic.js'

export const POLL_INTERVAL_MS = 1500

/**
 * Keeps the screen up to date by asking the backend for changes (owner: LEAD-CORE).
 * Returns { state, stale, loggedOut }.
 *   state     - the latest world state (null until the first reply)
 *   stale     - true when the backend has not answered for a while; keep showing the last state, marked as old
 *   loggedOut - true when the backend says the login is no longer valid
 */
export function useWorldState(intervalMs = POLL_INTERVAL_MS) {
  const [state, setState] = useState(null)
  const [stale, setStale] = useState(false)
  const [loggedOut, setLoggedOut] = useState(false)
  const lastSuccess = useRef(null)
  const version = useRef(null)

  useEffect(() => {
    let cancelled = false
    let timer = null

    async function tick() {
      try {
        const reply = await api.state(version.current)
        if (cancelled) return
        lastSuccess.current = Date.now()
        version.current = reply.version
        setState((previous) => applyReply(previous, reply))
        setStale(false)
      } catch (error) {
        if (cancelled) return
        if (error instanceof ApiError && error.status === 401) {
          setLoggedOut(true)
          return // stop polling; the screen will send the user to the login page
        }
        setStale(isStale(lastSuccess.current, Date.now(), intervalMs))
      }
      if (!cancelled) timer = setTimeout(tick, intervalMs)
    }

    tick()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [intervalMs])

  return { state, stale, loggedOut }
}

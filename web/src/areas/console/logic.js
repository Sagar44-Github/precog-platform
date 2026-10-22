// Pure helper functions for the 3D console (owner: VIZ). No React and no 3D here, so they are easy to test.
// The phone area (GRAPH) has similar helpers, but the console keeps its own copy so the two areas never depend on each other's files.

export const hostName = (state, id) => {
  const host = state && state.graph ? state.graph.hosts.find((h) => h.host_id === id) : null
  return host ? host.name : id
}

export const percent = (confidence) => Math.round(Number(confidence || 0) * 100)

/** The four-level threat rule from the UI/UX brief (Section 6.2). */
export function threatLevel(state) {
  if (!state || !state.graph) return null
  const hosts = state.graph.hosts
  const compromised = hosts.filter((h) => h.state === 'compromised').length
  const contained = hosts.filter((h) => h.state === 'contained').length
  const alerts = state.alerts.length
  const key = compromised ? 'attack' : contained ? 'contained' : alerts ? 'watching' : 'calm'
  const meta = {
    calm: { word: 'Calm', icon: '○', color: 'var(--severity-low)' },
    watching: { word: 'Watching', icon: '◆', color: 'var(--severity-medium)' },
    attack: { word: 'Under attack', icon: '⬣', color: 'var(--severity-critical)' },
    contained: { word: 'Contained', icon: '⛨', color: 'var(--state-contained)' },
  }[key]
  return { key, ...meta }
}

export function formatTime(ts, timeZone) {
  if (!ts) return ''
  const text = String(ts)
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(text) ? text : text.replace(' ', 'T') + 'Z')
  return Number.isNaN(date.getTime()) ? text : date.toLocaleTimeString('en-GB', { hour12: false, timeZone })
}

/** The words next to the replay buttons (UI/UX brief 6.9). */
export function replayWord(replay) {
  const words = { idle: 'Idle', running: 'Running', paused: 'Paused', waiting_for_decision: 'Waiting for your decision', finished: 'Finished' }
  return words[replay && replay.state] || 'Idle'
}

/** Which replay buttons do something right now. */
export function replayButtons(replay) {
  const state = replay ? replay.state : 'idle'
  const busy = state === 'running' || state === 'paused' || state === 'waiting_for_decision'
  return {
    start: !busy,
    pause: state === 'running',
    resume: state === 'paused' || state === 'waiting_for_decision',
    restart: state !== 'idle',
  }
}

export const SPEEDS = [1, 2, 4]

/** The text summary shown beside the 3D canvas, for screen readers and as a plain-list fallback (UI/UX brief 12). */
export function sceneSummary(state) {
  if (!state || !state.graph) return 'No data yet.'
  const hosts = state.graph.hosts
  const parts = [`${hosts.length} hosts.`]
  const compromised = hosts.filter((h) => h.state === 'compromised').map((h) => h.name)
  const contained = hosts.filter((h) => h.state === 'contained').map((h) => h.name)
  if (compromised.length) parts.push(`${compromised.length} compromised: ${compromised.join(', ')}.`)
  if (contained.length) parts.push(`${contained.length} contained: ${contained.join(', ')}.`)
  const forecast = state.forecast && state.forecast.status === 'pending' ? state.forecast.targets[0] : null
  if (forecast) parts.push(`1 forecast: ${hostName(state, forecast.host_id)} ${percent(forecast.confidence)} %.`)
  return parts.join(' ')
}

/** One mark per alert on the timeline strip, positioned 0 to 1 along the time span of the alerts (oldest left). */
export function timelineMarks(alerts) {
  if (!alerts.length) return []
  const times = alerts.map((a) => new Date(a.ts).getTime())
  const low = Math.min(...times)
  const span = Math.max(1, Math.max(...times) - low)
  return alerts.map((a, i) => ({ id: a.event_id, severity: a.severity, position: alerts.length === 1 ? 1 : (times[i] - low) / span }))
}

// ---------- containment flow for the console: propose, then confirm in a dialog ----------
export const CONFIRM_SECONDS = 60
export const initialContain = { step: 'idle', action: null, message: '', secondsLeft: CONFIRM_SECONDS }

export function containReducer(state, event) {
  switch (event.type) {
    case 'tap': return ['idle', 'error', 'expired', 'done'].includes(state.step) ? { ...initialContain, step: 'proposing' } : state
    case 'proposed': return state.step === 'proposing' ? { ...state, step: 'confirming', action: event.action, secondsLeft: CONFIRM_SECONDS, message: '' } : state
    case 'tick': {
      if (state.step !== 'confirming') return state
      const left = state.secondsLeft - 1
      return left <= 0 ? { ...state, step: 'expired', secondsLeft: 0, message: 'This request expired. Try again.' } : { ...state, secondsLeft: left }
    }
    case 'confirm': return state.step === 'confirming' ? { ...state, step: 'sending' } : state
    case 'confirmed': return state.step === 'sending' ? { ...state, step: 'done', action: event.action } : state
    case 'cancel': return state.step === 'confirming' ? { ...initialContain } : state
    case 'error': return { ...state, step: 'error', message: event.message || 'Something went wrong.' }
    case 'reset': return { ...initialContain }
    default: return state
  }
}

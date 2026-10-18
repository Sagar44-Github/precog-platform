// Pure helper functions for the phone screens (owner: GRAPH). No React in this file, so it is easy to test.
// "state" below is the world state the backend sends (contracts/schemas/world_state.schema.json).

export const SEVERITY = {
  HIGH: { word: 'High', icon: '▲', color: 'var(--severity-high)' },
  MEDIUM: { word: 'Medium', icon: '◆', color: 'var(--severity-medium)' },
  LOW: { word: 'Low', icon: '●', color: 'var(--severity-low)' },
}

export const HOST_STATE = {
  normal: { word: 'Normal', icon: '○', color: 'var(--state-normal)' },
  compromised: { word: 'Compromised', icon: '⬣', color: 'var(--state-compromised)' },
  contained: { word: 'Contained', icon: '⛨', color: 'var(--state-contained)' },
}

export const severityMeta = (severity) => SEVERITY[severity] || { word: 'Unrated', icon: '○', color: 'var(--severity-low)' }

export const hostStateMeta = (state) => HOST_STATE[state] || HOST_STATE.normal

/** The name of a host ("Web Server B") from its id ("server-b"), using the hosts in the graph. Unknown ids come back unchanged. */
export function hostName(state, hostId) {
  const found = state && state.graph && state.graph.hosts ? state.graph.hosts.find((h) => h.host_id === hostId) : null
  return found ? found.name : hostId
}

export function hostState(state, hostId) {
  const found = state && state.graph && state.graph.hosts ? state.graph.hosts.find((h) => h.host_id === hostId) : null
  return found ? found.state : 'normal'
}

/** The four-level threat rule from the UI/UX brief (Section 6.2). */
export function threatLevel(state) {
  if (!state || !state.graph) return null
  const hosts = state.graph.hosts || []
  const compromised = hosts.filter((h) => h.state === 'compromised').length
  const contained = hosts.filter((h) => h.state === 'contained').length
  const alerts = (state.alerts || []).length
  const pending = state.forecast && state.forecast.status === 'pending' ? 1 : 0
  let key
  if (compromised > 0) key = 'attack'
  else if (contained > 0) key = 'contained'
  else if (alerts > 0) key = 'watching'
  else key = 'calm'
  const meta = {
    calm: { word: 'Calm', icon: '○', color: 'var(--severity-low)' },
    watching: { word: 'Watching', icon: '◆', color: 'var(--severity-medium)' },
    attack: { word: 'Under attack', icon: '⬣', color: 'var(--severity-critical)' },
    contained: { word: 'Contained', icon: '⛨', color: 'var(--state-contained)' },
  }[key]
  const parts = []
  if (compromised) parts.push(`${compromised} ${compromised === 1 ? 'host' : 'hosts'} compromised`)
  if (pending) parts.push('1 forecast pending')
  if (!parts.length && contained) parts.push(`${contained} ${contained === 1 ? 'host' : 'hosts'} contained`)
  if (!parts.length && alerts) parts.push(`${alerts} ${alerts === 1 ? 'alert' : 'alerts'}`)
  if (!parts.length) parts.push('No alerts yet')
  return { key, ...meta, caption: parts.join(', ') }
}

/** Local time as HH:MM:SS. timeZone is only for tests ('UTC'). */
export function formatTime(ts, timeZone) {
  if (!ts) return ''
  const text = String(ts)
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(text) ? text : text.replace(' ', 'T') + 'Z')
  if (Number.isNaN(date.getTime())) return text
  return date.toLocaleTimeString('en-GB', { hour12: false, timeZone })
}

export const percent = (confidence) => Math.round(Number(confidence || 0) * 100)

/** The Top-3 rows with readable names and whole-number percentages. */
export function forecastRows(state) {
  const forecast = state && state.forecast
  if (!forecast) return []
  return forecast.targets.map((t) => ({ rank: t.rank, hostId: t.host_id, name: hostName(state, t.host_id), percent: percent(t.confidence) }))
}

export const mitreUrl = (techniqueId) => (techniqueId ? `https://attack.mitre.org/techniques/${String(techniqueId).replace('.', '/')}/` : null)

export function filterAlerts(alerts, severity) {
  return severity === 'ALL' ? alerts : alerts.filter((a) => a.severity === severity)
}

export const highAlertCount = (alerts) => alerts.filter((a) => a.severity === 'HIGH').length

/** The path of compromised hosts as names, ending with the rank-1 predicted host when there is a pending forecast. */
export function attackPath(state) {
  if (!state || !state.graph) return { steps: [], next: null }
  const steps = state.graph.compromised_path.map((id) => ({ hostId: id, name: hostName(state, id) }))
  const rows = forecastRows(state)
  return { steps, next: rows.length ? { hostId: rows[0].hostId, name: rows[0].name, percent: rows[0].percent } : null }
}

/** The wording and tone of a resolved forecast (UI/UX brief 6.15). */
export function outcomeText(forecast, state) {
  if (!forecast || !forecast.outcome || forecast.status === 'pending' || forecast.status === 'superseded') return null
  const target = hostName(state, forecast.outcome.attempted_host)
  if (forecast.status === 'hit') {
    return forecast.outcome.blocked
      ? { tone: 'contained', text: `Precog was right. The move toward ${target} was blocked.` }
      : { tone: 'happened', text: `Precog was right. The attacker reached ${target}.` }
  }
  return { tone: 'muted', text: `Precog missed. The attacker went to ${target} instead.` }
}

export const accuracyText = (metrics) => (!metrics || !metrics.forecasts_resolved
  ? 'No forecasts resolved yet'
  : `${metrics.hits} / ${metrics.forecasts_resolved} (${percent(metrics.hit_rate)} %)`)

// ---------- containment flow: a small state machine ----------
// idle -> proposing -> confirming (the sheet is open) -> sending -> done
// A problem at any step goes to 'error'; the 60-second timer goes to 'expired'; Cancel goes back to 'idle'.
export const CONFIRM_SECONDS = 60
export const SLIDE_THRESHOLD = 0.8

export const initialContain = { step: 'idle', action: null, message: '', secondsLeft: CONFIRM_SECONDS }

export function containReducer(state, event) {
  switch (event.type) {
    case 'tap': return state.step === 'idle' || state.step === 'error' || state.step === 'expired' || state.step === 'done'
      ? { ...initialContain, step: 'proposing' } : state
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

export const sliderComplete = (progress) => progress >= SLIDE_THRESHOLD
export const clamp01 = (value) => Math.max(0, Math.min(1, value))

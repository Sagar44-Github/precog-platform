// The ONLY place that talks to the backend (owner: LEAD-CORE).
// Every screen uses these functions, so errors and login handling behave the same everywhere.

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export class NetworkError extends Error {
  constructor(message) {
    super(message)
    this.name = 'NetworkError'
  }
}

async function request(method, path, body) {
  let response
  try {
    response = await fetch(path, {
      method,
      credentials: 'same-origin',
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (error) {
    throw new NetworkError('Cannot reach the server.')
  }
  let data = null
  try {
    data = await response.json()
  } catch (error) {
    data = null
  }
  if (!response.ok) {
    const info = data && data.error ? data.error : {}
    throw new ApiError(response.status, info.code || 'http_' + response.status, info.message || 'The server answered with an error.')
  }
  return data
}

export const apiGet = (path) => request('GET', path)
export const apiPost = (path, body = {}) => request('POST', path, body)

function withQuery(path, values = {}) {
  const query = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  })
  const suffix = query.toString()
  return suffix ? `${path}?${suffix}` : path
}

// Named helpers, one per backend endpoint the screens need. Names match docs: TRD section 11.
export const api = {
  health: () => apiGet('/api/x/health'),
  login: (username, password) => apiPost('/api/x/login', { username, password }),
  logout: () => apiPost('/api/x/logout'),
  me: () => apiGet('/api/x/me'),
  state: (since) => apiGet(since === null || since === undefined ? '/api/x/state' : `/api/x/state?since=${since}`),
  alerts: (limit = 50) => apiGet(`/api/x/alerts?limit=${limit}`),
  alert: (id) => apiGet(`/api/x/alerts/${encodeURIComponent(id)}`),
  searchAlerts: (filters = {}) => apiGet(withQuery('/api/x/alerts/search', filters)),
  assets: () => apiGet('/api/x/assets'),
  audit: (filters = {}) => apiGet(withQuery('/api/x/audit', filters)),
  incidents: (filters = {}) => apiGet(withQuery('/api/x/incidents', filters)),
  incident: (id) => apiGet(`/api/x/incidents/${encodeURIComponent(id)}`),
  addIncidentNote: (id, text) => apiPost(`/api/x/incidents/${encodeURIComponent(id)}/notes`, { text }),
  setIncidentStatus: (id, status) => request('PATCH', `/api/x/incidents/${encodeURIComponent(id)}/status`, { status }),
  reports: () => apiGet('/api/x/reports'),
  report: (sessionId) => apiGet(`/api/x/reports/${encodeURIComponent(sessionId)}`),
  system: () => apiGet('/api/x/system'),
  graph: () => apiGet('/api/x/graph'),
  forecasts: (filters = {}) => apiGet(withQuery('/api/x/forecasts', filters)),
  currentForecast: () => apiGet('/api/x/forecasts/current'),
  forecast: (id) => apiGet(`/api/x/forecasts/${encodeURIComponent(id)}`),
  whatIfForecast: (fromHost) => apiGet(withQuery('/api/x/forecasts/what-if', { from_host: fromHost })),
  analytics: () => apiGet('/api/x/analytics'),
  proposeContainment: (targetHost, forecastId, requestedBy) =>
    apiPost('/api/x/containment/propose', { target_host: targetHost, forecast_id: forecastId, requested_by: requestedBy }),
  confirmContainment: (actionId) => apiPost('/api/x/containment/confirm', { action_id: actionId }),
  cancelContainment: (actionId) => apiPost('/api/x/containment/cancel', { action_id: actionId }),
  session: () => apiGet('/api/x/session'),
  sessions: () => apiGet('/api/x/sessions'),
  precogMetrics: () => apiGet('/api/x/metrics/precog'),
  replayStatus: () => apiGet('/api/x/replay/status'),
  startReplay: (scenarioId, speed = 1) => apiPost('/api/x/replay/start', { scenario_id: scenarioId, speed }),
  pauseReplay: () => apiPost('/api/x/replay/pause'),
  resumeReplay: () => apiPost('/api/x/replay/resume'),
  restartReplay: () => apiPost('/api/x/replay/restart'),
  registerPush: (token) => apiPost('/api/x/push/register', { token }),
}

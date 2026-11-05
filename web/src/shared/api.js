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
      headers: body === undefined ? {} : { 'Content-Type': 'application/json', 'X-Precog-Request': '1' },
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
export const apiDelete = (path) => request('DELETE', path)

// Named helpers, one per backend endpoint the screens need. Names match docs: TRD section 11.
export const api = {
  health: () => apiGet('/api/x/health'),
  login: (username, password) => apiPost('/api/x/login', { username, password }),
  logout: () => apiPost('/api/x/logout'),
  me: () => apiGet('/api/x/me'),
  state: (since) => apiGet(since === null || since === undefined ? '/api/x/state' : `/api/x/state?since=${since}`),
  alerts: (limit = 50) => apiGet(`/api/x/alerts?limit=${limit}`),
  alert: (id) => apiGet(`/api/x/alerts/${encodeURIComponent(id)}`),
  graph: () => apiGet('/api/x/graph'),
  forecasts: (status) => apiGet(status ? `/api/x/forecasts?status=${status}` : '/api/x/forecasts'),
  currentForecast: () => apiGet('/api/x/forecasts/current'),
  forecastExplanation: (id) => apiGet(`/api/x/forecasts/${encodeURIComponent(id)}/explain`),
  whatIf: (input) => apiPost('/api/x/whatif', input),
  modelOverview: () => apiGet('/api/x/analytics/model'),
  evaluatePrecog: (parameters) => apiPost('/api/x/analytics/evaluate', parameters),
  precogExperiments: () => apiGet('/api/x/analytics/experiments'),
  proposeContainment: (targetHost, forecastId, requestedBy) =>
    apiPost('/api/x/containment/propose', { target_host: targetHost, forecast_id: forecastId, requested_by: requestedBy }),
  confirmContainment: (actionId) => apiPost('/api/x/containment/confirm', { action_id: actionId }),
  cancelContainment: (actionId) => apiPost('/api/x/containment/cancel', { action_id: actionId }),
  responsePlaybooks: () => apiGet('/api/x/containment/playbooks'),
  previewPlaybook: (input) => apiPost('/api/x/containment/preview', input),
  responseRecords: (limit = 100) => apiGet(`/api/x/containment/governance?limit=${limit}`),
  proposePlaybook: (input) => apiPost('/api/x/containment/governance/propose', input),
  approvePlaybook: (actionId, decision, reason = '') => apiPost('/api/x/containment/governance/approve', { action_id: actionId, decision, reason }),
  confirmPlaybook: (actionId) => apiPost('/api/x/containment/governance/confirm', { action_id: actionId }),
  cancelPlaybook: (actionId, reason) => apiPost('/api/x/containment/governance/cancel', { action_id: actionId, reason }),
  exportResponseRecords: (format = 'json') => `/api/x/containment/governance/export?format=${encodeURIComponent(format)}`,
  session: () => apiGet('/api/x/session'),
  sessions: () => apiGet('/api/x/sessions'),
  precogMetrics: () => apiGet('/api/x/metrics/precog'),
  replayStatus: () => apiGet('/api/x/replay/status'),
  startReplay: (scenarioId, speed = 1) => apiPost('/api/x/replay/start', { scenario_id: scenarioId, speed }),
  pauseReplay: () => apiPost('/api/x/replay/pause'),
  resumeReplay: () => apiPost('/api/x/replay/resume'),
  restartReplay: () => apiPost('/api/x/replay/restart'),
  scenarios: () => apiGet('/api/x/scenarios'),
  scenario: (id) => apiGet(`/api/x/scenarios/${encodeURIComponent(id)}`),
  validateScenario: (scenario) => apiPost('/api/x/scenarios/validate', { scenario }),
  dryRunScenario: (scenario) => apiPost('/api/x/scenarios/dry-run', { scenario }),
  saveScenario: (scenario) => apiPost('/api/x/scenarios', { scenario }),
  deleteScenario: (id) => apiDelete(`/api/x/scenarios/${encodeURIComponent(id)}`),
  startStudio: (scenarioId, speed = 1) => apiPost('/api/x/replay/studio/start', { scenario_id: scenarioId, speed }),
  studioStatus: () => apiGet('/api/x/replay/studio/status'),
  stepReplay: () => apiPost('/api/x/replay/step'),
  stepBackReplay: () => apiPost('/api/x/replay/step-back'),
  seekReplay: (position) => apiPost('/api/x/replay/seek', { position }),
  setReplaySpeed: (speed) => apiPost('/api/x/replay/speed', { speed }),
  setBreakpoints: (sequences) => apiPost('/api/x/replay/breakpoints', { sequences }),
  runs: () => apiGet('/api/x/runs'),
  run: (id) => apiGet(`/api/x/runs/${encodeURIComponent(id)}`),
  runSnapshots: (id) => apiGet(`/api/x/runs/${encodeURIComponent(id)}/snapshots`),
  runSnapshot: (id, version) => apiGet(`/api/x/snapshots?run=${encodeURIComponent(id)}&version=${version}`),
  compareRuns: (a, b) => apiGet(`/api/x/runs/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  topology: () => apiGet('/api/x/topology'),
  topologyPaths: (from, to, limit = 10) => apiGet(`/api/x/topology/paths?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&limit=${limit}`),
  segmentationPreview: (from, removeFrom, removeTo) => apiGet(`/api/x/topology/segmentation-preview?from=${encodeURIComponent(from)}&remove_from=${encodeURIComponent(removeFrom)}&remove_to=${encodeURIComponent(removeTo)}`),
  host: (id) => apiGet(`/api/x/hosts/${encodeURIComponent(id)}`),
  hostHistory: (id, limit = 200) => apiGet(`/api/x/hosts/${encodeURIComponent(id)}/history?limit=${limit}`),
  registerPush: (token) => apiPost('/api/x/push/register', { token }),
}

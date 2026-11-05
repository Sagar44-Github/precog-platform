import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, ApiError } from '../../shared/api.js'
import { useAuth } from '../../shared/AuthContext.jsx'
import { Button, EmptyMessage, Field, PageFrame, PageHeader, ResourceNotice, formatTime, useResource } from './shared.jsx'
import './containment.css'

const PLAYBOOKS = [
  ['host', 'Contain one host'],
  ['zone', 'Contain a zone'],
  ['predicted_path', 'Contain along the predicted path'],
  ['top_three', 'Contain the predicted Top-3'],
]

function targetIds(action) {
  return action.target_hosts || [action.target_host]
}

export default function ContainmentPage() {
  const { operator } = useAuth()
  const permissions = operator?.permissions || {}
  const [revision, setRevision] = useState(0)
  const [playbook, setPlaybook] = useState('host')
  const [targetHost, setTargetHost] = useState('')
  const [zone, setZone] = useState('')
  const [forecastId, setForecastId] = useState('')
  const [releaseActionId, setReleaseActionId] = useState('')
  const [busyAction, setBusyAction] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [notice, setNotice] = useState('')

  const load = useCallback(async () => {
    const [actions, activeActions, graph, forecasts] = await Promise.all([
      api.containmentActions({ include_archived: 1 }),
      api.containmentActions(),
      api.graph(),
      api.forecasts({ status: 'pending' }),
    ])
    return { actions, activeActionIds: activeActions.map((action) => action.action_id), graph, forecasts }
  }, [revision])
  const { data, loading, error, refresh } = useResource(load, `containment:${revision}`)
  const hosts = data?.graph?.hosts || []
  const availableHosts = hosts.filter((host) => host.state !== 'contained')
  const zones = [...new Set(hosts.map((host) => host.zone).filter(Boolean))].sort()
  const forecasts = data?.forecasts || []
  const activeIds = new Set(data?.activeActionIds || [])
  const hostById = useMemo(() => Object.fromEntries(hosts.map((host) => [host.host_id, host])), [hosts])
  const currentForecast = forecasts.find((forecast) => forecast.forecast_id === forecastId) || forecasts[0]
  const executedContainments = (data?.actions || []).filter((action) =>
    (action.operation || 'contain') === 'contain' && action.status === 'executed' && activeIds.has(action.action_id))

  useEffect(() => {
    const timer = window.setInterval(() => setRevision((value) => value + 1), 3000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!availableHosts.some((host) => host.host_id === targetHost)) setTargetHost(availableHosts[0]?.host_id || '')
    if (!zones.includes(zone)) setZone(zones[0] || '')
    if (!forecasts.some((forecast) => forecast.forecast_id === forecastId)) setForecastId(forecasts[0]?.forecast_id || '')
    if (!executedContainments.some((action) => action.action_id === releaseActionId)) setReleaseActionId(executedContainments[0]?.action_id || '')
  }, [availableHosts, zones.join('|'), forecasts, executedContainments, targetHost, zone, forecastId, releaseActionId])

  const previewTargets = useMemo(() => {
    if (playbook === 'host') return targetHost ? [targetHost] : []
    if (playbook === 'zone') return hosts.filter((host) => host.zone === zone && host.state !== 'contained').map((host) => host.host_id)
    if (!currentForecast) return []
    const predicted = currentForecast.targets.map((target) => target.host_id)
    const targets = playbook === 'top_three'
      ? predicted.slice(0, 3)
      : [...new Set([...(data?.graph?.compromised_path || []), ...predicted])]
    return targets.filter((hostId) => hostById[hostId]?.state !== 'contained')
  }, [playbook, targetHost, zone, hosts, currentForecast, data?.graph?.compromised_path, hostById])

  async function propose(event) {
    event.preventDefault()
    setBusyAction('propose')
    setErrorMessage('')
    setNotice('')
    try {
      const options = playbook === 'host' ? { target_host: targetHost }
        : playbook === 'zone' ? { zone }
          : { forecast_id: currentForecast?.forecast_id }
      const action = await api.proposeContainmentPlaybook(playbook, options)
      setNotice(`Request ${action.action_id} is waiting for confirmation. No host changed yet.`)
      setRevision((value) => value + 1)
      refresh()
    } catch (reason) {
      setErrorMessage(reason instanceof ApiError ? reason.message : 'The playbook request could not be created.')
    } finally {
      setBusyAction('')
    }
  }

  async function confirm(action) {
    setBusyAction(action.action_id)
    setErrorMessage('')
    setNotice('')
    try {
      await api.confirmContainment(action.action_id)
      setNotice(action.operation === 'release' ? 'Release confirmed. Simulated host state restored.' : 'Containment confirmed. Host state changed only in this simulation.')
      setRevision((value) => value + 1)
      refresh()
    } catch (reason) {
      setErrorMessage(reason instanceof ApiError ? reason.message : 'The confirmation could not be completed.')
    } finally {
      setBusyAction('')
    }
  }

  async function cancel(action) {
    setBusyAction(action.action_id)
    setErrorMessage('')
    try {
      await api.cancelContainment(action.action_id)
      setNotice('The pending request was cancelled. No host state changed.')
      setRevision((value) => value + 1)
      refresh()
    } catch (reason) {
      setErrorMessage(reason instanceof ApiError ? reason.message : 'The request could not be cancelled.')
    } finally {
      setBusyAction('')
    }
  }

  async function proposeRelease() {
    if (!releaseActionId) return
    setBusyAction('release')
    setErrorMessage('')
    setNotice('')
    try {
      const action = await api.proposeContainmentRelease(releaseActionId)
      setNotice(`Release request ${action.action_id} is waiting for confirmation.`)
      setRevision((value) => value + 1)
      refresh()
    } catch (reason) {
      setErrorMessage(reason instanceof ApiError ? reason.message : 'The release request could not be created.')
    } finally {
      setBusyAction('')
    }
  }

  const actions = [...(data?.actions || [])].sort((left, right) => String(right.proposed_at).localeCompare(String(left.proposed_at)))
  const isForecastPlaybook = playbook === 'predicted_path' || playbook === 'top_three'

  return <PageFrame className="containment-page">
    <PageHeader eyebrow="RESPONSE / SIMULATED CONTAINMENT" title="Containment" description="Review proposed responses, apply a playbook, and confirm each simulated state change." actions={<Button className="ops-button-secondary" type="button" onClick={() => { setRevision((value) => value + 1); refresh() }}>Refresh history</Button>} />

    <div className="containment-guardrail"><span className="containment-mark" aria-hidden="true">◇</span><p><strong>Simulation only.</strong> Requests affect the in-memory replay graph and audit log; they do not change a real network. Every contain and release action requires a separate confirmation.</p><span className="containment-role">{operator?.role_name || 'Viewer'} access</span></div>

    <div className="containment-layout">
      <section className="ops-card containment-playbook-card" aria-labelledby="containment-playbook-title">
        <div className="ops-card-header"><div><h3 id="containment-playbook-title">Response playbook</h3><p>Build an explicit target list, review it, then submit for confirmation.</p></div><span className="containment-step-label">PROPOSE → CONFIRM</span></div>
        {permissions.can_contain ? <form className="containment-playbook-form" onSubmit={propose}>
          <Field label="Playbook"><select value={playbook} onChange={(event) => setPlaybook(event.target.value)} aria-label="Containment playbook">
            {PLAYBOOKS.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select></Field>
          {playbook === 'host' && <Field label="Host"><select value={targetHost} onChange={(event) => setTargetHost(event.target.value)} aria-label="Target host">{availableHosts.map((host) => <option value={host.host_id} key={host.host_id}>{host.name} · {host.host_id}</option>)}</select></Field>}
          {playbook === 'zone' && <Field label="Zone"><select value={zone} onChange={(event) => setZone(event.target.value)} aria-label="Target zone">{zones.map((value) => <option key={value} value={value}>{value}</option>)}</select></Field>}
          {isForecastPlaybook && <Field label="Pending forecast"><select value={currentForecast?.forecast_id || ''} onChange={(event) => setForecastId(event.target.value)} aria-label="Pending forecast">{forecasts.map((forecast) => <option key={forecast.forecast_id} value={forecast.forecast_id}>{forecast.forecast_id} · from {forecast.from_host}</option>)}</select></Field>}
          <div className="containment-preview" aria-live="polite"><span className="containment-preview-count">{previewTargets.length.toString().padStart(2, '0')}</span><div><strong>Simulated hosts in this request</strong><p>{previewTargets.length ? previewTargets.map((id) => hostById[id]?.name || id).join(' · ') : 'Select a playbook and target to preview hosts.'}</p></div></div>
          <Button className="ops-button-primary" type="submit" disabled={busyAction !== '' || previewTargets.length === 0}>{busyAction === 'propose' ? 'Submitting…' : 'Propose containment'}</Button>
        </form> : <div className="containment-readonly"><strong>Read-only role</strong><p>Viewer accounts can inspect history and forecasts, but cannot propose or confirm containment or control replay.</p></div>}

        {permissions.can_release && <div className="containment-release-form"><div><h4>Release a contained host</h4><p>Release restores the state recorded before the original containment. It also uses propose then confirm.</p></div><Field label="Active containment"><select value={releaseActionId} onChange={(event) => setReleaseActionId(event.target.value)} aria-label="Containment to release"><option value="">No active containment to release</option>{executedContainments.map((action) => <option value={action.action_id} key={action.action_id}>{action.action_id} · {targetIds(action).map((id) => hostById[id]?.name || id).join(', ')}</option>)}</select></Field><Button className="ops-button-secondary" type="button" onClick={proposeRelease} disabled={!releaseActionId || busyAction !== ''}>Propose release</Button></div>}
      </section>

      <section className="ops-card containment-history-card" aria-labelledby="containment-history-title">
        <div className="ops-card-header"><div><h3 id="containment-history-title">Action history</h3><p>Current replay and bounded session archive · {actions.length} recorded actions</p></div><span className="containment-history-mark">AUDIT TRAIL</span></div>
        <ResourceNotice loading={loading} error={error} data={data} onRetry={refresh} />
        {errorMessage && <p className="ops-error" role="alert">{errorMessage}</p>}
        {notice && <p className="containment-notice" role="status">{notice}</p>}
        {data && (actions.length ? <div className="containment-action-list">{actions.map((action) => {
          const operation = action.operation || 'contain'
          const isRelease = operation === 'release'
          const canConfirm = action.status === 'pending_confirmation' && (isRelease ? permissions.can_release : permissions.can_contain)
          const canCancel = action.status === 'pending_confirmation' && (isRelease ? permissions.can_release : permissions.can_contain)
          const canRelease = operation === 'contain' && action.status === 'executed' && activeIds.has(action.action_id) && permissions.can_release
          return <article className="containment-action-row" key={action.action_id}>
            <span className={`containment-action-icon ${isRelease ? 'is-release' : ''}`} aria-hidden="true">{isRelease ? '↶' : '◇'}</span>
            <div className="containment-action-main"><div className="containment-action-title"><strong>{isRelease ? 'Release' : 'Contain'} · {targetIds(action).map((id) => hostById[id]?.name || id).join(', ')}</strong><span className={`containment-status status-${action.status}`}>{action.status.replaceAll('_', ' ')}</span></div>
              <p>{action.playbook ? `${action.playbook.replaceAll('_', ' ')} playbook` : 'Host playbook'}{action.related_action_id ? ` · reverses ${action.related_action_id}` : ''}{action.session_id ? ` · ${action.session_id}` : ''}</p>
              <small>{formatTime(action.proposed_at)}{action.result ? ` · ${action.result}` : ''}</small>
              {(canConfirm || canCancel || canRelease) && <div className="containment-action-controls">
                {canConfirm && <Button type="button" className="ops-button-primary" disabled={busyAction !== ''} onClick={() => confirm(action)}>{busyAction === action.action_id ? 'Applying…' : isRelease ? 'Confirm release' : 'Confirm containment'}</Button>}
                {canCancel && <Button type="button" className="ops-button-secondary" disabled={busyAction !== ''} onClick={() => cancel(action)}>Cancel request</Button>}
                {canRelease && <Button type="button" className="ops-button-secondary" disabled={busyAction !== ''} onClick={() => { setReleaseActionId(action.action_id); document.getElementById('containment-history-title')?.scrollIntoView({ block: 'nearest' }) }}>Select for release</Button>}
              </div>}
            </div>
          </article>
        })}</div> : <EmptyMessage title="No containment actions recorded">Propose a playbook when the replay has a decision to review. Requests stay pending until a permitted operator confirms or cancels them.</EmptyMessage>)}
      </section>
    </div>
  </PageFrame>
}

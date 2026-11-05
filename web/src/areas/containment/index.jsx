import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { EmptyState, LoadingState } from '../../shared/components.jsx'
import { Icon } from '../../shared/icons.jsx'
import { useAuth } from '../../shared/AuthContext.jsx'
import { allowedPlaybooksForRole, filterGovernanceRecords, previewProbabilityPercent } from './logic.js'
import './containment.css'

function labelFor(playbookId) {
  return ({
    'contain-host': 'Contain one host',
    'contain-zone': 'Contain a zone',
    'contain-predicted-path': 'Contain predicted path',
    'contain-top-three': 'Contain Top-3 targets',
    'release-host': 'Release one host',
  })[playbookId] || playbookId
}

function statusLabel(status) {
  return (status || 'unknown').replaceAll('_', ' ')
}

function RecordCard({ record, release = false, onConfirm, onCancel, onApprove, onReject, busy, canOperate, canAdminApprove }) {
  const canConfirm = ['pending_confirmation'].includes(record.status)
  const canApprove = record.status === 'pending_approval'
  const hosts = record.preview_snapshot?.hosts_affected || []
  return <article className="gov-record">
    <div className="gov-record-head"><div><p className="gov-kicker">{release ? 'RELEASE RECORD' : 'APPROVAL RECORD'} · {record.action_id}</p><h3>{labelFor(record.playbook_id)}</h3></div><span className={`gov-status is-${record.status}`}>{statusLabel(record.status)}</span></div>
    <div className="gov-record-meta"><span>{record.proposed_by} · {record.proposed_role}</span><time>{record.proposed_at}</time><span>{hosts.map((host) => host.name).join(', ')}</span></div>
    <p className="gov-record-reason">{record.reason}</p>
    {record.approval && <p className="gov-record-approval">{record.approval.decision} by {record.approval.actor} · {record.approval.role}</p>}
    {record.execution_summary && <p className="gov-record-result">{record.execution_summary}</p>}
    {record.host_action_ids?.length > 0 && <p className="gov-record-result">Simulated host actions: {record.host_action_ids.join(', ')}</p>}
    {(canConfirm || canApprove || ['pending_approval', 'pending_confirmation'].includes(record.status)) && <div className="gov-record-actions">
      {canApprove && canAdminApprove && onApprove && canOperate && <button type="button" className="gov-button gov-button-primary" disabled={busy} onClick={() => onApprove(record)}>Approve as second admin</button>}
      {canApprove && canAdminApprove && onReject && canOperate && <button type="button" className="gov-button gov-button-quiet" disabled={busy} onClick={() => onReject(record)}>Reject with reason</button>}
      {canConfirm && canOperate && <button type="button" className="gov-button gov-button-primary" disabled={busy} onClick={() => onConfirm(record)}>Confirm simulated action</button>}
      {['pending_approval', 'pending_confirmation'].includes(record.status) && canOperate && <button type="button" className="gov-button gov-button-quiet" disabled={busy} onClick={() => onCancel(record)}>Cancel request</button>}
    </div>}
  </article>
}

export default function ContainmentPage() {
  const { role } = useAuth()
  const [searchParams] = useSearchParams()
  const [playbooks, setPlaybooks] = useState([])
  const [topology, setTopology] = useState(null)
  const [forecasts, setForecasts] = useState([])
  const [records, setRecords] = useState({ approvals: [], releases: [], revision: 0 })
  const [playbookId, setPlaybookId] = useState('contain-host')
  const [hostId, setHostId] = useState(searchParams.get('host') || '')
  const [zone, setZone] = useState('')
  const [forecastId, setForecastId] = useState(searchParams.get('forecast') || '')
  const [incidentId] = useState(searchParams.get('incident') || '')
  const [reason, setReason] = useState('')
  const [preview, setPreview] = useState(null)
  const [activeRecord, setActiveRecord] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [filter, setFilter] = useState('all')
  const [playbookFilter, setPlaybookFilter] = useState('all')

  const refreshRecords = useCallback(async () => {
    const next = await api.responseRecords(100)
    setRecords(next)
    return next
  }, [])

  useEffect(() => {
    let alive = true
    Promise.all([api.responsePlaybooks(), api.topology(), api.forecasts(), api.responseRecords(100)])
      .then(([items, network, forecastList, history]) => {
        if (!alive) return
        setPlaybooks(items)
        setTopology(network)
        setForecasts(forecastList)
        setRecords(history)
        if (!zone && network.zones.length) setZone(network.zones[0].zone)
        if (!forecastId && forecastList.length) setForecastId(forecastList[forecastList.length - 1].forecast_id)
      })
      .catch((failure) => alive && setError(failure.message || 'Response governance could not load.'))
    return () => { alive = false }
  }, []) // Initial route state is intentionally read once.

  useEffect(() => {
    const timer = window.setInterval(() => { refreshRecords().catch(() => {}) }, 5000)
    return () => window.clearInterval(timer)
  }, [refreshRecords])

  const availablePlaybooks = useMemo(() => allowedPlaybooksForRole(playbooks, role), [playbooks, role])
  const selectedPlaybook = playbooks.find((item) => item.playbook_id === playbookId)
  const isRelease = playbookId === 'release-host'
  const hostOptions = (topology?.hosts || []).filter((host) => isRelease ? host.state === 'contained' : host.state !== 'contained')
  const allRecords = useMemo(() => filterGovernanceRecords(records, 'all'), [records])
  const shownRecords = useMemo(() => filterGovernanceRecords(records, filter, playbookFilter), [records, filter, playbookFilter])
  const active = activeRecord ? allRecords.find((record) => record.action_id === activeRecord.action_id) || activeRecord : null

  function formInput() {
    return {
      playbook_id: playbookId,
      ...(selectedPlaybook?.scope === 'host' ? { host_id: hostId } : {}),
      ...(selectedPlaybook?.scope === 'zone' ? { zone } : {}),
      ...(selectedPlaybook?.scope === 'path' || selectedPlaybook?.scope === 'forecast' ? { forecast_id: forecastId } : {}),
      ...(selectedPlaybook?.scope === 'host' && forecastId ? { forecast_id: forecastId } : {}),
    }
  }

  async function doPreview(event) {
    event.preventDefault()
    setBusy(true); setError(''); setPreview(null)
    try { setPreview(await api.previewPlaybook(formInput())) }
    catch (failure) { setError(failure.message || 'Impact preview failed.') }
    finally { setBusy(false) }
  }

  async function doPropose() {
    setBusy(true); setError('')
    try {
      const response = await api.proposePlaybook({ ...formInput(), reason: reason.trim(), ...(incidentId ? { incident_id: incidentId } : {}) })
      setActiveRecord(response.record)
      setPreview(response.record.preview_snapshot)
      await refreshRecords()
    } catch (failure) { setError(failure.message || 'The response proposal could not be recorded.') }
    finally { setBusy(false) }
  }

  async function doConfirm() {
    if (!active) return
    setConfirming(false); setBusy(true); setError('')
    try {
      const response = await api.confirmPlaybook(active.action_id)
      setActiveRecord(response.record)
      const [, network] = await Promise.all([refreshRecords(), api.topology()])
      setTopology(network)
    } catch (failure) { setError(failure.message || 'The request could not be confirmed.') }
    finally { setBusy(false) }
  }

  async function doCancel(record) {
    const why = window.prompt('Reason for cancelling this simulated request:', 'Cancelled after review.')
    if (why === null) return
    setBusy(true); setError('')
    try {
      const response = await api.cancelPlaybook(record.action_id, why)
      setActiveRecord(response.record)
      await refreshRecords()
    } catch (failure) { setError(failure.message || 'The request could not be cancelled.') }
    finally { setBusy(false) }
  }

  async function doApprove(record) {
    setBusy(true); setError('')
    try {
      const response = await api.approvePlaybook(record.action_id, 'approve')
      setActiveRecord(response.record)
      await refreshRecords()
    } catch (failure) { setError(failure.message || 'Approval failed. A different administrator must approve this request.') }
    finally { setBusy(false) }
  }

  async function doReject(record) {
    const why = window.prompt('Reason for rejecting this simulated zone action:')
    if (why === null) return
    setBusy(true); setError('')
    try {
      const response = await api.approvePlaybook(record.action_id, 'reject', why)
      setActiveRecord(response.record)
      await refreshRecords()
    } catch (failure) { setError(failure.message || 'The proposal could not be rejected.') }
    finally { setBusy(false) }
  }

  async function exportHistory(format) {
    try {
      const response = await fetch(api.exportResponseRecords(format), { credentials: 'same-origin' })
      if (!response.ok) throw new Error('Export could not be downloaded.')
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `precog-response-governance.${format === 'markdown' ? 'md' : 'json'}`
      document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url)
    } catch (failure) { setError(failure.message || 'Export failed.') }
  }

  if (!topology && !error) return <div className="gov-page"><LoadingState /></div>
  return <main className="gov-page">
    <div className="gov-content">
      <header className="gov-heading"><div><p className="gov-kicker">SIMULATED RESPONSE · PROPOSE → REVIEW → CONFIRM</p><h1>Response governance</h1><p>Preview impact, record an approval decision, then confirm the action. Containment changes only the replay’s in-memory state.</p></div><div className="gov-heading-links"><Link to="/incidents">Incidents ↗</Link><Link to="/twin">Network twin ↗</Link></div></header>
      {error && <div className="gov-error" role="alert">{error}</div>}
      <div className="gov-layout">
        <section className="gov-card gov-launcher">
          <div className="gov-card-heading"><div><p className="gov-kicker">PLAYBOOK LAUNCHER</p><h2>Build an action preview</h2></div><span className="gov-readonly">IN-MEMORY SIMULATION</span></div>
          {role === 'viewer' && <p className="gov-role-note">Viewer access is read only. An analyst can propose single-host containment; administrators can run broader playbooks.</p>}
          {availablePlaybooks.length > 0 ? <form onSubmit={doPreview}>
            <label>Response playbook<select value={playbookId} onChange={(event) => { setPlaybookId(event.target.value); setPreview(null); setError('') }}>{availablePlaybooks.map((item) => <option key={item.playbook_id} value={item.playbook_id}>{item.label}</option>)}</select></label>
            {selectedPlaybook?.scope === 'host' && <label>Host<select value={hostId} onChange={(event) => { setHostId(event.target.value); setPreview(null) }}><option value="">Choose a host</option>{hostOptions.map((host) => <option key={host.host_id} value={host.host_id}>{host.name} · {host.state}</option>)}</select></label>}
            {selectedPlaybook?.scope === 'zone' && <label>Zone<select value={zone} onChange={(event) => { setZone(event.target.value); setPreview(null) }}>{(topology?.zones || []).map((item) => <option key={item.zone} value={item.zone}>{item.zone} · {item.host_ids.length} hosts</option>)}</select></label>}
            {['path', 'forecast'].includes(selectedPlaybook?.scope) && <label>Forecast<select value={forecastId} onChange={(event) => { setForecastId(event.target.value); setPreview(null) }}><option value="">Choose a forecast</option>{forecasts.map((item) => <option key={item.forecast_id} value={item.forecast_id}>{item.forecast_id} · from {item.from_host} · {item.status}</option>)}</select></label>}
            <label>Decision reason<textarea value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} required placeholder="Why is this simulated response being proposed?" /></label>
            <small className="gov-count">{reason.length} / 500 · plain text, recorded in the audit trail</small>
            <div className="gov-form-actions"><button type="submit" className="gov-button gov-button-quiet" disabled={busy || !selectedPlaybook || (selectedPlaybook.scope === 'host' && !hostId) || (selectedPlaybook.scope === 'zone' && !zone) || (['path', 'forecast'].includes(selectedPlaybook?.scope) && !forecastId)}>{busy ? 'Working…' : 'Preview impact'}</button>
              {preview && <button type="button" className="gov-button gov-button-primary" disabled={busy || reason.trim().length === 0} onClick={doPropose}>Propose for confirmation</button>}</div>
          </form> : <EmptyState>No response action is available for this role.</EmptyState>}
          {selectedPlaybook && <p className="gov-playbook-description">{selectedPlaybook.description}</p>}
        </section>

        <section className="gov-card gov-impact" aria-live="polite">
          <div className="gov-card-heading"><div><p className="gov-kicker">IMPACT REVIEW</p><h2>{preview ? labelFor(preview.playbook_id) : 'Preview before proposing'}</h2></div><span className="gov-readonly">MODEL ESTIMATE</span></div>
          {!preview ? <p className="gov-empty-copy">Choose a playbook and review affected hosts, feasible links, criticality and estimated forecast probability before proposing.</p> : <>
            <div className="gov-impact-stats"><div><b>{preview.hosts_affected.length}</b><span>hosts affected</span></div><div><b>{preview.feasible_edges_changed.length}</b><span>feasible links changed</span></div><div><b>{previewProbabilityPercent(preview, playbookId)}%</b><span>{isRelease ? 'probability restored' : 'forecast share removed'}</span></div><div><b>{preview.criticality_total.toFixed(2)}</b><span>summed criticality</span></div></div>
            <h3>Affected hosts</h3><ul className="gov-host-list">{preview.hosts_affected.map((host) => <li key={host.host_id}><span><b>{host.name}</b><small>{host.host_id} · {host.state} · {Math.round(host.criticality * 100)}% criticality</small></span><strong>{Math.round(host.forecast_probability * 100)}%</strong></li>)}</ul>
            <h3>Consequences</h3><ul className="gov-side-effects">{preview.side_effects.map((item) => <li key={item}>{item}</li>)}</ul>
            <p className="gov-reeval"><b>Expected re-evaluation</b><br />{preview.expected_reevaluation}</p>
            <p className="gov-estimate-note">Probability removed/restored is an estimate from Precog’s scripted model and the six-host demo network. It is not a guarantee of real-world protection.</p>
          </>}
        </section>
      </div>

      {active && ['pending_approval', 'pending_confirmation'].includes(active.status) && <section className="gov-card gov-current-action"><div className="gov-card-heading"><div><p className="gov-kicker">PENDING ACTION · EXPIRES {active.expires_at}</p><h2>{labelFor(active.playbook_id)}</h2></div><span className={`gov-status is-${active.status}`}>{statusLabel(active.status)}</span></div><p>{active.reason}</p><div className="gov-pending-hosts">{active.preview_snapshot.hosts_affected.map((host) => <span key={host.host_id}>{host.name}</span>)}</div>{active.status === 'pending_approval' && <p className="gov-role-note">A different administrator must approve this proposal before it can be confirmed.</p>}</section>}

      <section className="gov-card gov-history">
        <div className="gov-card-heading"><div><p className="gov-kicker">DECISION LOG · {allRecords.length} RECENT</p><h2>Approvals, actions &amp; releases</h2></div><div className="gov-export-actions"><button className="gov-button gov-button-quiet" type="button" onClick={() => exportHistory('json')}>Export JSON</button><button className="gov-button gov-button-quiet" type="button" onClick={() => exportHistory('markdown')}>Export Markdown</button></div></div>
        <div className="gov-history-filter"><label>Status<select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All statuses</option>{['pending_approval', 'pending_confirmation', 'executed', 'released', 'cancelled', 'expired', 'rejected', 'partially_executed'].map((value) => <option value={value} key={value}>{statusLabel(value)}</option>)}</select></label><label>Playbook<select value={playbookFilter} onChange={(event) => setPlaybookFilter(event.target.value)}><option value="all">All playbooks</option>{playbooks.map((item) => <option key={item.playbook_id} value={item.playbook_id}>{item.label}</option>)}</select></label><span>Audit logged · {records.revision} updates</span></div>
        {shownRecords.length === 0 ? <EmptyState>No governance actions yet. Preview a playbook to begin.</EmptyState> : <div className="gov-record-list">{shownRecords.map((record) => <RecordCard key={record.action_id} record={record} release={record.playbook_id === 'release-host'} busy={busy} canOperate={role !== 'viewer'} canAdminApprove={role === 'admin'} onConfirm={(item) => { setActiveRecord(item); setConfirming(true) }} onCancel={doCancel} onApprove={doApprove} onReject={doReject} />)}</div>}
      </section>
      <footer className="gov-footer"><span>PRECOG SOC · SIMULATION</span><span>No real hosts, accounts or network controls are changed.</span></footer>
    </div>
    {confirming && active && <div className="gov-modal-backdrop"><section className="gov-confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="gov-confirm-title"><p className="gov-kicker">SIMULATED ACTION CONFIRMATION</p><h2 id="gov-confirm-title">Confirm {labelFor(active.playbook_id).toLowerCase()}?</h2><p>This affects {active.preview_snapshot.hosts_affected.map((host) => host.name).join(', ')} in the demo state. Legitimate simulated use may be interrupted; no real network changes occur.</p><div className="gov-form-actions"><button className="gov-button gov-button-quiet" type="button" onClick={() => setConfirming(false)}>Go back</button><button className="gov-button gov-button-primary" type="button" disabled={busy} onClick={doConfirm}>Confirm simulated action</button></div></section></div>}
  </main>
}

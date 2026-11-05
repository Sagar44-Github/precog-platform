import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { Button, EmptyMessage, Field, PageFrame, PageHeader, ResourceNotice, formatTime, useResource } from './shared.jsx'
import { CandidateEvidence, ForecastTargets } from './forecast-evidence.jsx'
import './forecast-analytics.css'

function outcomeLabel(forecast) {
  if (forecast.status === 'hit') return `Hit · rank ${forecast.outcome?.rank_hit}`
  if (forecast.status === 'miss') return 'Miss'
  if (forecast.status === 'superseded') return 'Superseded'
  return 'Pending'
}

export default function ForecastsPage() {
  const [status, setStatus] = useState('')
  const [revision, setRevision] = useState(0)
  const [graphRevision, setGraphRevision] = useState(0)
  const [fromHost, setFromHost] = useState('')
  const [preview, setPreview] = useState(null)
  const [previewError, setPreviewError] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const load = useCallback(() => api.forecasts({ include_archived: 1 }), [revision])
  const loadGraph = useCallback(() => api.graph(), [graphRevision])
  const { data, loading, error, refresh } = useResource(load, `forecasts:${revision}`)
  const { data: graph } = useResource(loadGraph, 'forecast-graph')
  const compromised = (graph?.hosts || []).filter((host) => host.state === 'compromised')
  const compromisedKey = compromised.map((host) => host.host_id).join('|')
  const visible = (data || []).filter((forecast) => !status || forecast.status === status)
    .sort((left, right) => String(right.ts).localeCompare(String(left.ts)))

  useEffect(() => {
    const timer = window.setInterval(() => setGraphRevision((value) => value + 1), 1500)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!compromised.some((host) => host.host_id === fromHost)) setFromHost(compromised[0]?.host_id || '')
  }, [compromisedKey, fromHost])

  async function showWhatIf(event) {
    event.preventDefault()
    if (!fromHost) return
    setPreview(null)
    setPreviewError('')
    setPreviewLoading(true)
    try { setPreview(await api.whatIfForecast(fromHost)) }
    catch (reason) { setPreviewError(reason.message || 'What-if preview could not be created.') }
    finally { setPreviewLoading(false) }
  }

  return <PageFrame className="forecast-page">
      <PageHeader eyebrow="PRECOG / FORECAST LEDGER" title="Forecasts" description="Every recorded prediction keeps its original candidate set, transition evidence, model ranking, and observed outcome." actions={<><Link className="ops-button ops-button-secondary" to="/analytics">Model analytics</Link><Button className="ops-button-secondary" type="button" onClick={() => { refresh(); setRevision((value) => value + 1); setGraphRevision((value) => value + 1) }}>Refresh ledger</Button></>} />

    <section className="ops-card forecast-preview-card" aria-labelledby="what-if-title">
      <div className="ops-card-header"><div><h3 id="what-if-title">Read-only what-if</h3><p>Preview predicted targets for a host that is compromised in the current simulation.</p></div><span className="forecast-label">NO STATE CHANGE</span></div>
      <form className="forecast-preview-form" onSubmit={showWhatIf}>
        <Field label="Compromised host"><select value={fromHost} onChange={(event) => setFromHost(event.target.value)} disabled={!compromised.length} aria-label="Compromised host">
          <option value="">{compromised.length ? 'Choose a host' : 'No compromised host in this replay'}</option>
          {compromised.map((host) => <option value={host.host_id} key={host.host_id}>{host.name} · {host.host_id}</option>)}
        </select></Field>
        <Button type="submit" className="ops-button-secondary" disabled={!fromHost || previewLoading}>{previewLoading ? 'Calculating…' : 'Preview forecast'}</Button>
      </form>
      {previewError && <p className="ops-error" role="alert">{previewError}</p>}
      {preview && <div className="what-if-result" aria-live="polite">
        <p className="ops-eyebrow">PREDICTED NEXT HOSTS FROM <span className="ops-mono">{preview.from_host}</span></p>
        <ForecastTargets targets={preview.targets} />
        <p className="forecast-quiet-note">{preview.note}</p>
        <CandidateEvidence explanation={preview.explanation} />
      </div>}
    </section>

    <section className="ops-card forecast-ledger-card" aria-label="Forecast records">
      <div className="ops-card-header"><div><h3>Recorded predictions</h3><p>{visible.length} forecasts · includes the bounded replay session archive</p></div><label className="forecast-status-filter"><span>Status</span><select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter forecasts by status"><option value="">All statuses</option><option value="pending">Pending</option><option value="hit">Hit</option><option value="miss">Miss</option><option value="superseded">Superseded</option></select></label></div>
      <ResourceNotice loading={loading} error={error} data={data} onRetry={refresh} />
      {data && (visible.length ? <div className="ops-table-wrap"><table className="ops-table forecast-ledger-table"><thead><tr><th>Forecast</th><th>From</th><th>Predicted targets</th><th>Observed result</th><th>Session</th><th>Recorded</th></tr></thead><tbody>
        {visible.map((forecast) => <tr key={forecast.forecast_id}>
          <td data-label="Forecast"><Link className="ops-table-link" to={`/forecasts/${encodeURIComponent(forecast.forecast_id)}`}>{forecast.forecast_id}</Link><span className="cell-secondary">{forecast.explanation?.model?.name === 'markov' ? 'Markov model' : 'Recorded prediction'}</span></td>
          <td data-label="From" className="ops-mono">{forecast.from_host}</td>
          <td data-label="Predicted targets">{forecast.targets.map((target) => <span className="forecast-inline-target" key={target.host_id}><b>{target.rank}</b> {target.host_id} <small>{(target.confidence * 100).toFixed(1)}%</small></span>)}</td>
          <td data-label="Observed result"><span className={`forecast-outcome outcome-${forecast.status}`}>{outcomeLabel(forecast)}</span>{forecast.outcome?.blocked && <span className="cell-secondary">Move was blocked</span>}</td>
          <td data-label="Session"><span className="ops-mono">{forecast.session_id || 'Current session'}</span></td>
          <td data-label="Recorded"><span className="cell-secondary">{formatTime(forecast.ts)}</span></td>
        </tr>)}
      </tbody></table></div> : <EmptyMessage title="No forecasts match this filter">Start a replay or change the status filter. Predictions are recorded only when a scripted host becomes compromised.</EmptyMessage>)}
    </section>
    <p className="forecast-honesty-note">A forecast is a ranked prediction, not a statement of certainty. A miss stays visible in this ledger. The what-if preview does not alter live state.</p>
  </PageFrame>
}

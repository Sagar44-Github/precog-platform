import { useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { Button, PageFrame, PageHeader, ResourceNotice, formatTime, useResource } from './shared.jsx'
import { CandidateEvidence, ForecastTargets } from './forecast-evidence.jsx'
import './forecast-analytics.css'

function describeOutcome(forecast) {
  if (forecast.status === 'miss') return `Miss · attempted ${forecast.outcome?.attempted_host || 'host not recorded'}, outside the Top 3.`
  if (forecast.status === 'hit') return `Hit at rank ${forecast.outcome?.rank_hit} · attempted ${forecast.outcome?.attempted_host || 'unknown host'}.`
  if (forecast.status === 'superseded') return 'Superseded before the next move was observed.'
  return 'Pending · the next scripted move has not resolved this prediction.'
}

export default function ForecastDetailPage() {
  const { forecastId } = useParams()
  const load = useCallback(() => api.forecast(forecastId), [forecastId])
  const { data, loading, error, refresh } = useResource(load, forecastId)
  return <PageFrame className="forecast-page forecast-detail-page">
    <PageHeader eyebrow="PRECOG / FORECAST RECORD" title="Forecast detail" description="Review the prediction as it was captured, including the feasible candidate set and the evidence behind each rank." actions={<Link className="ops-button ops-button-secondary" to="/forecasts">Back to forecasts</Link>} />
    <ResourceNotice loading={loading} error={error} data={data} onRetry={refresh} />
    {data && <>
      <section className="ops-stat-grid forecast-detail-stats" aria-label="Forecast summary">
        <div className="ops-stat"><span>Forecast</span><strong className="forecast-stat-id">{data.forecast_id}</strong></div>
        <div className="ops-stat"><span>Starting host</span><strong className="forecast-stat-id">{data.from_host}</strong></div>
        <div className="ops-stat"><span>Recorded</span><strong className="forecast-stat-time">{formatTime(data.ts)}</strong></div>
        <div className="ops-stat"><span>Technique hint table</span><strong className="forecast-stat-source">{data.explanation?.technique_hint_source || data.source}</strong></div>
      </section>
      <section className="ops-detail-grid forecast-detail-grid">
        <article className="ops-card">
          <div className="ops-card-header"><div><h3>Predicted next hosts</h3><p>Ranked confidence values are model estimates, not certainties.</p></div><span className={`forecast-outcome outcome-${data.status}`}>{data.status}</span></div>
          <div className="ops-card-body">
            <ForecastTargets targets={data.targets} attemptedHost={data.outcome?.attempted_host} />
            <p className={`forecast-result-note ${data.status === 'miss' ? 'forecast-result-miss' : ''}`} role="status">{describeOutcome(data)}</p>
            {data.outcome?.blocked && <p className="forecast-quiet-note">The move was blocked in simulation after a confirmed containment action.</p>}
            {data.technique_hint && <div className="forecast-technique-hint"><span className="ops-eyebrow">PREDICTED TECHNIQUE HINT</span><strong>{data.technique_hint.technique_name}</strong><span className="ops-mono">{data.technique_hint.technique_id} · {(data.technique_hint.probability * 100).toFixed(1)}%</span></div>}
          </div>
        </article>
        <article className="ops-card forecast-record-card"><div className="ops-card-header"><div><h3>Record context</h3><p>Session and resolution details</p></div></div><div className="ops-card-body"><dl className="ops-detail-list">
          <div><dt>Session</dt><dd className="ops-mono">{data.session_id || 'Legacy record'}</dd></div>
          <div><dt>Technique lookup table</dt><dd>{data.explanation?.technique_hint_source || data.source}</dd></div>
          <div><dt>Observed outcome</dt><dd>{describeOutcome(data)}</dd></div>
          <div><dt>Attempt blocked</dt><dd>{data.outcome ? (data.outcome.blocked ? 'Yes · simulation' : 'No') : 'Not resolved'}</dd></div>
        </dl></div></article>
      </section>
      <section className="ops-card forecast-detail-evidence"><div className="ops-card-header"><div><h3>Why the model ranked these hosts</h3><p>Counts and rankings were stored when this prediction was created.</p></div></div><div className="ops-card-body"><CandidateEvidence explanation={data.explanation} /></div></section>
      <p className="forecast-honesty-note">This is a simulation record. A miss remains a miss in the ledger; containment does not rewrite the predicted outcome.</p>
    </>}
  </PageFrame>
}

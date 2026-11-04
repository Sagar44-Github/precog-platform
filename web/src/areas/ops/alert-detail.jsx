import { useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { PageFrame, PageHeader, ResourceNotice, Severity, SourceBadge, StateBadge, formatTime, useResource } from './shared.jsx'

export default function AlertDetailPage() {
  const { alertId } = useParams()
  const load = useCallback(async () => {
    const [alert, inventory] = await Promise.all([api.alert(alertId), api.assets()])
    return { alert, assets: inventory.items }
  }, [alertId])
  const { data, loading, error, refresh } = useResource(load, alertId)
  const alert = data?.alert
  const host = data?.assets.find((item) => item.host_id === alert?.host)

  return <PageFrame>
    <PageHeader eyebrow="DETECTION / EVENT RECORD" title={alert?.event_id || 'Alert detail'} description="One detection event with its host, risk, technique context, and source." actions={<Link to="/alerts" className="ops-button ops-button-secondary">Back to alerts</Link>} />
    <ResourceNotice loading={loading} error={error} data={data} onRetry={refresh} />
    {alert && <>
      <div className="ops-stat-grid">
        <div className="ops-stat"><span>Severity</span><strong><Severity value={alert.severity} /></strong></div>
        <div className="ops-stat"><span>Risk score</span><strong>{Math.round(alert.risk_score)} / 100</strong></div>
        <div className="ops-stat"><span>Detection source</span><strong><SourceBadge value={alert.source} /></strong></div>
        <div className="ops-stat"><span>Host state</span><strong><Link className="ops-text-link" to={`/hosts/${encodeURIComponent(alert.host)}`}><StateBadge value={host?.state || 'normal'} /></Link></strong></div>
      </div>
      <div className="ops-detail-grid">
        <section className="ops-card"><div className="ops-card-header"><div><h3>Event explanation</h3><p>Human-readable summary from the replay pipeline</p></div></div><div className="ops-card-body">
          <p className="ops-alert-explanation">{alert.explanation}</p>
          <dl className="ops-detail-list">
            <div><dt>Event ID</dt><dd className="ops-mono">{alert.event_id}</dd></div>
            <div><dt>Observed</dt><dd>{formatTime(alert.ts)}</dd></div>
            <div><dt>Host</dt><dd><Link className="ops-text-link" to={`/hosts/${encodeURIComponent(alert.host)}`}>{alert.host}</Link></dd></div>
            <div><dt>Packet ID</dt><dd className="ops-mono">{alert.packet_id ?? '—'}</dd></div>
            <div><dt>Anomaly flag</dt><dd>{alert.anomaly ? 'Flagged anomalous' : 'Not flagged anomalous'}</dd></div>
            <div><dt>Source label</dt><dd>{alert.source === 'scripted' ? 'Scripted scenario event' : 'NIDS detector event'}</dd></div>
            <div><dt>Risk score</dt><dd>{alert.risk_score} / 100</dd></div>
            <div><dt>Severity</dt><dd><Severity value={alert.severity} /></dd></div>
          </dl>
        </div></section>
        <section className="ops-card"><div className="ops-card-header"><div><h3>Technique context</h3><p>ATT&amp;CK mapping from the event processor</p></div></div><div className="ops-card-body">
          {alert.technique_id ? <>
            <p className="ops-technique-id">{alert.technique_id}</p>
            <h3 className="ops-technique-name">{alert.technique_name || 'Technique name unavailable'}</h3>
            <p className="ops-description">This label describes the simulated event record and does not indicate real activity.</p>
            <a className="ops-text-link" href={`https://attack.mitre.org/techniques/${alert.technique_id.replace('.', '/')}/`} target="_blank" rel="noreferrer">Open MITRE ATT&amp;CK reference ↗</a>
          </> : <p className="muted">No technique was assigned to this event.</p>}
        </div></section>
      </div>
    </>}
  </PageFrame>
}

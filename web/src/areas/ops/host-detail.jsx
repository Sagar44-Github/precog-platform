import { useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { EmptyMessage, PageFrame, PageHeader, ResourceNotice, StateBadge, formatTime, useResource } from './shared.jsx'

export default function HostDetailPage() {
  const { hostId } = useParams()
  const load = useCallback(() => api.assets(), [])
  const { data, loading, error, refresh } = useResource(load, hostId)
  const host = data?.items.find((item) => item.host_id === hostId)

  return <PageFrame>
    <PageHeader eyebrow="ASSETS / HOST RECORD" title={host?.name || 'Host detail'} description={host ? `${host.role} in the ${host.zone} zone.` : 'Current inventory details and replay state history.'} actions={<Link to="/hosts" className="ops-button ops-button-secondary">Back to hosts</Link>} />
    <ResourceNotice loading={loading} error={error} data={data} onRetry={refresh} />
    {data && !host && <EmptyMessage title="Host not found">This id is not part of the six-host demo network.</EmptyMessage>}
    {host && <>
      <div className="ops-stat-grid">
        <div className="ops-stat"><span>Current state</span><strong><StateBadge value={host.state} /></strong></div>
        <div className="ops-stat"><span>Risk score</span><strong>{Math.round(host.risk_score)} / 100</strong></div>
        <div className="ops-stat"><span>Criticality</span><strong>{Math.round(host.criticality * 100)}%</strong></div>
        <div className="ops-stat"><span>Network zone</span><strong>{host.zone}</strong></div>
      </div>
      <div className="ops-detail-grid">
        <section className="ops-card"><div className="ops-card-header"><div><h3>Asset profile</h3><p>Static inventory joined with current replay state</p></div></div><div className="ops-card-body">
          <dl className="ops-detail-list">
            <div><dt>Host id</dt><dd className="ops-mono">{host.host_id}</dd></div>
            <div><dt>Address</dt><dd className="ops-mono">{host.address}</dd></div>
            <div><dt>Zone</dt><dd>{host.zone}</dd></div>
            <div><dt>Role</dt><dd>{host.role}</dd></div>
            <div><dt>Services</dt><dd>{host.services.length ? host.services.join(', ') : 'No modeled services'}</dd></div>
            <div><dt>Reachable demo hosts</dt><dd>{host.reachable_hosts.length ? host.reachable_hosts.map((id) => <span key={id}><Link className="ops-text-link" to={`/hosts/${encodeURIComponent(id)}`}>{id}</Link> </span>) : 'No outbound paths'}</dd></div>
          </dl>
        </div></section>
        <section className="ops-card"><div className="ops-card-header"><div><h3>State history</h3><p>Changes observed in this replay session</p></div></div><div className="ops-card-body">
          {host.state_history.length ? <ol className="ops-history">{[...host.state_history].reverse().map((entry, index) => <li key={`${entry.ts}-${index}`}><span>{entry.from_state ? `${entry.from_state} → ${entry.state}` : `Initial state: ${entry.state}`}</span><time>{formatTime(entry.ts)}</time></li>)}</ol> : <EmptyMessage title="No state changes recorded">This host has remained in its initial state during the current replay.</EmptyMessage>}
        </div></section>
      </div>
      <section className="ops-card ops-weakness-card"><div className="ops-card-header"><div><h3>Modeled weaknesses</h3><p>Invented demo data used only for simulated topology scoring</p></div></div><div className="ops-card-body">
        <p className="ops-simulated-note">Every record below is synthetic and carries a DEMO- identifier. These are not real CVEs, validated vulnerabilities, or findings against a real host.</p>
        {host.weaknesses.length ? host.weaknesses.map((weakness) => <article className="ops-weakness" key={weakness.id}>
          <div className="ops-weakness-head"><strong className="ops-mono">{weakness.id}</strong><span className="ops-mono">Modeled CVSS {weakness.cvss.toFixed(1)} / 10</span></div>
          <p>{weakness.description}</p>
          <span className="ops-service-chip">Modeled service: {weakness.service}</span>
        </article>) : <EmptyMessage title="No modeled weaknesses">This host has no synthetic weakness records in the demo topology.</EmptyMessage>}
      </div></section>
    </>}
  </PageFrame>
}

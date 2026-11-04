import { useCallback, useMemo, useState } from 'react'
import { api } from '../../shared/api.js'
import { Button, EmptyMessage, Field, FilterBar, PageFrame, PageHeader, ResourceNotice, SearchField, StateBadge, TableLink, useResource } from './shared.jsx'

export default function HostsPage() {
  const [draft, setDraft] = useState({ q: '', zone: '', state: '' })
  const [filter, setFilter] = useState(draft)
  const load = useCallback(() => api.assets(), [])
  const { data, loading, error, refresh } = useResource(load, 'asset-inventory')
  const zones = useMemo(() => [...new Set((data?.items || []).map((host) => host.zone))].sort(), [data])
  const items = (data?.items || []).filter((host) => {
    const needle = filter.q.toLowerCase()
    return (!needle || `${host.name} ${host.host_id} ${host.address} ${host.role}`.toLowerCase().includes(needle))
      && (!filter.zone || host.zone === filter.zone)
      && (!filter.state || host.state === filter.state)
  })
  function apply(event) { event.preventDefault(); setFilter({ ...draft }) }
  function reset() { const empty = { q: '', zone: '', state: '' }; setDraft(empty); setFilter(empty) }

  return <PageFrame>
    <PageHeader eyebrow="ASSETS / DEMO NETWORK" title="Hosts & assets" description="Inventory of the six simulated hosts, their network zones, services, modeled weaknesses, and current replay state." actions={<Button type="button" className="ops-button-secondary" onClick={refresh}>Refresh inventory</Button>} />
    <ResourceNotice loading={loading} error={error} data={data} onRetry={refresh} />
    {data && <>
      <div className="ops-stat-grid">
        <div className="ops-stat"><span>Demo hosts</span><strong>{data.total}</strong></div>
        <div className="ops-stat"><span>Zones</span><strong>{zones.length}</strong></div>
        <div className="ops-stat"><span>Compromised</span><strong>{data.items.filter((host) => host.state === 'compromised').length}</strong></div>
        <div className="ops-stat"><span>Contained</span><strong>{data.items.filter((host) => host.state === 'contained').length}</strong></div>
      </div>
      <FilterBar className="ops-host-filter" onSubmit={apply} onReset={reset}>
        <Field label="Search"><SearchField value={draft.q} onChange={(event) => setDraft({ ...draft, q: event.target.value })} placeholder="Name, id, address, role…" /></Field>
        <Field label="Zone"><select value={draft.zone} onChange={(event) => setDraft({ ...draft, zone: event.target.value })}><option value="">All zones</option>{zones.map((zone) => <option key={zone} value={zone}>{zone}</option>)}</select></Field>
        <Field label="State"><select value={draft.state} onChange={(event) => setDraft({ ...draft, state: event.target.value })}><option value="">All states</option><option value="normal">normal</option><option value="compromised">compromised</option><option value="contained">contained</option></select></Field>
      </FilterBar>
      <section className="ops-card"><div className="ops-card-header"><div><h3>Demo network inventory</h3><p>{items.length} of {data.total} assets shown · weaknesses are simulated</p></div></div>
        {items.length ? <div className="ops-table-wrap"><table className="ops-table"><thead><tr><th>Asset</th><th>Zone</th><th>State</th><th>Risk</th><th>Services</th><th>Simulated weaknesses</th></tr></thead><tbody>
          {items.map((host) => <tr key={host.host_id}>
            <td data-label="Asset"><TableLink to={`/hosts/${encodeURIComponent(host.host_id)}`}>{host.name}</TableLink><span className="cell-secondary cell-mono">{host.host_id} · {host.address}</span></td>
            <td data-label="Zone">{host.zone}<span className="cell-secondary">{host.role}</span></td>
            <td data-label="State"><StateBadge value={host.state} /></td>
            <td data-label="Risk"><div className="ops-risk"><div className="ops-risk-track" aria-label={`Risk score ${Math.round(host.risk_score)} out of 100`}><span style={{ width: `${host.risk_score}%` }} /></div><span className="ops-risk-value">{Math.round(host.risk_score)}</span></div></td>
            <td data-label="Services">{host.services.map((service) => <span className="ops-service-chip" key={service}>{service}</span>)}</td>
            <td data-label="Simulated weaknesses"><span className="ops-mono">{host.weaknesses.length} DEMO- records</span></td>
          </tr>)}
        </tbody></table></div> : <EmptyMessage title="No assets match these filters">Clear the filters to see the full simulated network.</EmptyMessage>}
      </section>
    </>}
  </PageFrame>
}

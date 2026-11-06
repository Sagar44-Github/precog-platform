import { useCallback, useMemo } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { useAuth } from '../../shared/AuthContext.jsx'
import { Button, ErrorMessage, LoadingMessage, PageFrame, PageHeader, useResource } from '../ops/shared.jsx'
import { capabilityLabel, comparisonRows, isSwitchable } from './model.js'
import './datasets.css'

function DatasetCounts({ counts = {} }) {
  return <dl className="dataset-counts">{[['hosts', 'Hosts'], ['edges', 'Links'], ['events', 'Events'], ['routes', 'Routes']].map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{Number(counts[key] || 0).toLocaleString()}</dd></div>)}</dl>
}

function CapabilityList({ capabilities = {} }) {
  return <ul className="dataset-capabilities">{Object.entries(capabilities).map(([key, value]) => <li key={key}><span>{key.replaceAll('_', ' ')}</span><b>{capabilityLabel(value)}</b></li>)}</ul>
}

function WorkspaceButton({ item, current }) {
  const { role } = useAuth()
  if (current) return <span className="dataset-active-state">Active workspace</span>
  if (!isSwitchable(item)) return <span className="dataset-disabled-state">Pack not installed</span>
  if (role === 'viewer') return <span className="dataset-disabled-state">Read only · analyst/admin can switch</span>
  return <WorkspaceActivateButton item={item} />
}

function WorkspaceActivateButton({ item }) {
  const activate = async () => {
    if (!window.confirm(`Switch to ${item.name}? The current replay state will reset.`)) return
    await api.activateWorkspace(item.id)
    window.location.assign(`/datasets/${encodeURIComponent(item.id)}`)
  }
  return <Button type="button" onClick={activate}>Switch workspace</Button>
}

export default function DatasetsPage() {
  const load = useCallback(() => api.workspaces(), [])
  const { data, loading, error, refresh } = useResource(load, 'dataset-list')
  const items = data?.workspaces || []
  const active = data?.active_workspace || ''
  return <PageFrame className="datasets-page">
    <PageHeader eyebrow="DATA / WORKSPACES" title="Dataset workspaces" description="Inspect installed packs and registered data sources. Availability and capability labels describe this local deployment; unavailable packs cannot be activated." actions={<><Link className="ops-button ops-button-secondary" to="/datasets/upload">Upload dataset</Link><Link className="ops-button ops-button-secondary" to={`/datasets/compare?left=${encodeURIComponent(active || 'demo-6')}`}>Compare datasets</Link></>} />
    {loading && !data && <LoadingMessage label="Loading registered dataset packs…" />}
    {error && !data && <ErrorMessage message={error} onRetry={refresh} />}
    <section className="dataset-grid" aria-label="Registered datasets">{items.map((item) => <article className={`dataset-card${item.status === 'unavailable' ? ' is-unavailable' : ''}`} key={item.id}>
      <div className="dataset-card-top"><span className={`dataset-status status-${item.status}`}>{item.status === 'active' ? 'ACTIVE' : item.status === 'unavailable' ? 'NOT INSTALLED' : 'AVAILABLE'}</span><span className="dataset-version">v{item.version}</span></div>
      <h3>{item.name}</h3><p className="dataset-id">{item.id}</p><DatasetCounts counts={item.counts} />
      <p className="dataset-provenance">Redistribution: <b>{String(item.redistribution || 'unknown').replaceAll('-', ' ')}</b></p>
      <details className="dataset-capability-disclosure"><summary>Declared capabilities</summary><CapabilityList capabilities={item.capabilities} /></details>
      <div className="dataset-card-actions"><Link className="ops-button ops-button-secondary" to={`/datasets/${encodeURIComponent(item.id)}`}>Dataset details</Link><WorkspaceButton item={item} current={item.id === active} /></div>
    </article>)}</section>
    {!loading && !items.length && <p className="dataset-empty">No registered dataset packs were returned.</p>}
    <p className="dataset-honesty">Recorded datasets provide context for scripted simulation. Derived topology and movement routes are estimates; they do not establish live protection or real attacker behavior.</p>
  </PageFrame>
}

export function DatasetDetailPage() {
  const { id = '' } = useParams()
  const load = useCallback(() => Promise.all([api.workspaceCard(id), api.workspaces()]), [id])
  const { data, loading, error, refresh } = useResource(load, id)
  const [card, listing] = data || []
  const item = listing?.workspaces?.find((candidate) => candidate.id === id)
  const active = listing?.active_workspace === id
  return <PageFrame className="datasets-page">
    <PageHeader eyebrow="DATA / DATASET CARD" title={card?.name || 'Dataset details'} description="Source and capability context for this workspace. Registered metadata does not imply the full source dataset is installed." actions={<Link className="ops-button ops-button-secondary" to="/datasets">All datasets</Link>} />
    {loading && !data && <LoadingMessage label="Loading dataset card…" />}
    {error && !data && <ErrorMessage message={error} onRetry={refresh} />}
    {card && <>
      <section className="dataset-detail-hero"><div><span className="dataset-id">{card.id}</span><h3>{card.name}</h3><p>{item?.status === 'unavailable' ? 'Pack not installed in this deployment. This page shows registry metadata and source limitations only.' : 'Pack available locally for simulated replay.'}</p></div><WorkspaceButton item={item} current={active} /></section>
      <section className="dataset-detail-grid">
        <article className="dataset-detail-panel"><h3>Source and redistribution</h3><dl><div><dt>Source</dt><dd>{card.source?.name || card.source?.id || card.id}</dd></div><div><dt>License / status</dt><dd>{card.source?.licence || card.redistribution}</dd></div><div><dt>Terms</dt><dd>{card.source?.terms_summary || card.redistribution}</dd></div><div><dt>Citation</dt><dd>{card.source?.citation || 'See the dataset source card.'}</dd></div></dl></article>
        <article className="dataset-detail-panel"><h3>Workflow capability</h3><CapabilityList capabilities={card.capabilities} /><h4>Limitations</h4><ul className="dataset-limitations">{(card.limitations || []).map((limit, index) => <li key={index}>{limit}</li>)}</ul></article>
      </section>
      <details className="dataset-source-text"><summary>Read dataset card summary</summary><pre>{card.summary}</pre></details>
    </>}
  </PageFrame>
}

export function DatasetComparePage() {
  const [params, setParams] = useSearchParams()
  const load = useCallback(async () => {
    const listing = await api.workspaces()
    const fallbackLeft = listing.active_workspace || listing.workspaces?.[0]?.id || ''
    const fallbackRight = listing.workspaces?.find((item) => item.id !== fallbackLeft)?.id || fallbackLeft
    const ids = [...new Set([params.get('left') || fallbackLeft, params.get('right') || fallbackRight].filter(Boolean))]
    const cards = await Promise.all(ids.map(async (id) => {
      try { return [id, await api.workspaceCard(id)] } catch { return [id, null] }
    }))
    return { listing, cards: Object.fromEntries(cards) }
  }, [params])
  const { data, loading, error, refresh } = useResource(load, params.toString())
  const items = data?.listing?.workspaces || []
  const leftId = params.get('left') || data?.listing?.active_workspace || items[0]?.id || ''
  const rightId = params.get('right') || items.find((item) => item.id !== leftId)?.id || leftId
  const left = data?.cards?.[leftId]
  const right = data?.cards?.[rightId]
  const rows = useMemo(() => comparisonRows(left, right), [left, right])
  const update = (key, value) => { const next = new URLSearchParams(params); next.set(key, value); setParams(next) }
  return <PageFrame className="datasets-page">
    <PageHeader eyebrow="DATA / COMPARISON" title="Compare dataset workspaces" description="Compare declared counts, capabilities, and provenance for two registered packs." actions={<Link className="ops-button ops-button-secondary" to="/datasets">All datasets</Link>} />
    {loading && !data && <LoadingMessage label="Loading dataset cards…" />}
    {error && !data && <ErrorMessage message={error} onRetry={refresh} />}
    {data && <>
      <div className="dataset-compare-selects"><label>Workspace A<select value={leftId} onChange={(event) => update('left', event.target.value)}>{items.map((item) => <option key={item.id} value={item.id}>{item.id}</option>)}</select></label><span aria-hidden="true">↔</span><label>Workspace B<select value={rightId} onChange={(event) => update('right', event.target.value)}>{items.map((item) => <option key={item.id} value={item.id}>{item.id}</option>)}</select></label></div>
      <div className="dataset-compare-grid"><DatasetCompareCard title={left?.name || leftId} item={items.find((item) => item.id === leftId)} card={left} /><DatasetCompareCard title={right?.name || rightId} item={items.find((item) => item.id === rightId)} card={right} /></div>
      <section className="dataset-detail-panel"><h3>Capability comparison</h3><div className="dataset-compare-table" role="table" aria-label="Dataset capability comparison"><div className="dataset-compare-row is-heading" role="row"><b role="columnheader">Workflow</b><b role="columnheader">{left?.name || leftId}</b><b role="columnheader">{right?.name || rightId}</b></div>{rows.map((row) => <div className="dataset-compare-row" role="row" key={row.key}><span role="rowheader">{row.label}</span><span role="cell">{row.left}</span><span role="cell">{row.right}</span></div>)}</div></section>
    </>}
    <p className="dataset-honesty">A “derived” capability is generated for the simulation and is not a property asserted by the original dataset.</p>
  </PageFrame>
}

function DatasetCompareCard({ title, item, card }) {
  return <article className="dataset-detail-panel"><h3>{title}</h3><p className="dataset-id">{item?.id}</p><DatasetCounts counts={item?.counts} /><p><b>Availability:</b> {item?.status || 'unknown'}</p><p><b>Redistribution:</b> {item?.redistribution || card?.redistribution || 'unknown'}</p><p className="dataset-compare-source">{card?.source?.citation || 'Citation is not present in the workspace card.'}</p></article>
}

import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { Button, EmptyMessage, Field, FilterBar, PageFrame, PageHeader, Pagination, ResourceNotice, SearchField, formatTime, useResource } from './shared.jsx'

export default function AuditPage() {
  const [draft, setDraft] = useState({ type: '', ref_id: '', q: '', from: '', to: '' })
  const [applied, setApplied] = useState(draft)
  const [cursor, setCursor] = useState('')
  const load = useCallback(() => api.audit({ ...applied, cursor, limit: 50 }), [applied, cursor])
  const { data, loading, error, refresh } = useResource(load, `${JSON.stringify(applied)}:${cursor}`)
  function apply(event) { event.preventDefault(); setApplied({ ...draft }); setCursor('') }
  function reset() { const empty = { type: '', ref_id: '', q: '', from: '', to: '' }; setDraft(empty); setApplied(empty); setCursor('') }

  return <PageFrame>
    <PageHeader eyebrow="GOVERNANCE / EVENT HISTORY" title="Audit log" description="Read-only records written by detection, forecast, containment, and incident review components. Summaries are scrubbed before storage." actions={<Button className="ops-button-secondary" type="button" onClick={refresh}>Refresh log</Button>} />
      <FilterBar className="ops-audit-filter" onSubmit={apply} onReset={reset}>
      <Field label="Record type"><select value={draft.type} onChange={(event) => setDraft({ ...draft, type: event.target.value })}><option value="">All record types</option><option value="detection">Detection</option><option value="forecast">Forecast</option><option value="containment">Containment</option><option value="incident">Incident</option></select></Field>
      <Field label="Reference id"><input value={draft.ref_id} onChange={(event) => setDraft({ ...draft, ref_id: event.target.value })} placeholder="evt-, fc-, act-" /></Field>
      <Field label="Summary search"><SearchField value={draft.q} onChange={(event) => setDraft({ ...draft, q: event.target.value })} placeholder="Search scrubbed summaries" /></Field>
      <Field label="From"><input type="date" value={draft.from} onChange={(event) => setDraft({ ...draft, from: event.target.value })} /></Field>
      <Field label="To"><input type="date" value={draft.to} onChange={(event) => setDraft({ ...draft, to: event.target.value })} /></Field>
    </FilterBar>
    <ResourceNotice loading={loading} error={error} data={data} onRetry={refresh} />
    {data && <section className="ops-card"><div className="ops-card-header"><div><h3>Audit records</h3><p>{data.total} matching records in the local JSON-lines log</p></div></div>
      {data.items.length ? <>
        <div className="ops-table-wrap"><table className="ops-table"><thead><tr><th>Type</th><th>Reference</th><th>Summary</th><th>Timestamp</th></tr></thead><tbody>
          {data.items.map((entry, index) => <tr key={`${entry.ts}-${entry.ref_id}-${index}`}>
            <td data-label="Type"><span className={`ops-audit-type audit-${entry.type}`}>{entry.type}</span></td>
            <td data-label="Reference" className="cell-mono">{entry.type === 'detection' ? <Link className="ops-text-link" to={`/alerts/${encodeURIComponent(entry.ref_id)}`}>{entry.ref_id}</Link> : entry.ref_id}</td>
            <td data-label="Summary" className="cell-wrap">{entry.summary}</td>
            <td data-label="Timestamp"><span className="cell-secondary">{formatTime(entry.ts)}</span></td>
          </tr>)}
        </tbody></table></div>
        <Pagination cursor={cursor} nextCursor={data.next_cursor} total={data.total} onPrevious={() => setCursor(String(Math.max(0, Number(cursor || 0) - 50)) || '')} onNext={() => setCursor(data.next_cursor)} />
      </> : <EmptyMessage title="No audit records match these filters">Detection, forecast, and containment entries appear when the replay pipeline runs.</EmptyMessage>}
    </section>}
  </PageFrame>
}

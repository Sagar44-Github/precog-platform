import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { useUiPreferences } from '../../shared/ui-preferences.jsx'
import { Button, EmptyMessage, Field, FilterBar, PageFrame, PageHeader, Pagination, ResourceNotice, SearchField, Severity, SourceBadge, TableLink, formatTime, useResource } from './shared.jsx'

const PAGE_SIZE = 50
const FIELDS = ['event_id', 'ts', 'host', 'severity', 'risk_score', 'technique_id', 'technique_name', 'source', 'explanation']

function saveFile(filename, content, type) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function csvCell(value) {
  let text = String(value ?? '')
  if (/^[\t\r =+\-@]/.test(text)) text = `'${text}`
  return `"${text.replaceAll('"', '""')}"`
}

export default function AlertsPage() {
  const { preferences } = useUiPreferences()
  const [draft, setDraft] = useState({ q: '', severity: preferences.defaultAlertSeverity, host: '', technique: '', from: '', to: '', sort: 'ts', order: 'desc' })
  const [applied, setApplied] = useState(draft)
  const [cursor, setCursor] = useState('')
  const [exportError, setExportError] = useState('')
  const load = useCallback(() => api.searchAlerts({ ...applied, cursor, limit: PAGE_SIZE }), [applied, cursor])
  const { data, loading, error, refresh } = useResource(load, `${JSON.stringify(applied)}:${cursor}`)

  function apply(event) {
    event.preventDefault()
    setApplied({ ...draft })
    setCursor('')
  }

  function reset() {
    const empty = { q: '', severity: '', host: '', technique: '', from: '', to: '', sort: 'ts', order: 'desc' }
    setDraft(empty)
    setApplied(empty)
    setCursor('')
  }

  async function exportRows(format) {
    setExportError('')
    try {
      const reply = await api.searchAlerts({ ...applied, cursor: '', limit: 200 })
      if (format === 'json') {
        saveFile('precog-alerts.json', JSON.stringify(reply.items, null, 2), 'application/json')
      } else {
        const lines = [FIELDS.join(','), ...reply.items.map((row) => FIELDS.map((field) => csvCell(row[field])).join(','))]
        saveFile('precog-alerts.csv', lines.join('\r\n'), 'text/csv;charset=utf-8')
      }
    } catch (reason) {
      setExportError(reason.message || 'Export could not be created.')
    }
  }

  return (
    <PageFrame>
      <PageHeader eyebrow="DETECTION / EVENT EXPLORER" title="Alerts" description="Search and review detection events from the current replay. Scripted records are identified in the source column." actions={<><Button className="ops-button-secondary" type="button" onClick={() => exportRows('csv')}>Export CSV</Button><Button className="ops-button-secondary" type="button" onClick={() => exportRows('json')}>Export JSON</Button></>} />
      <FilterBar className="ops-alert-filter" onSubmit={apply} onReset={reset}>
        <Field label="Search"><SearchField value={draft.q} onChange={(event) => setDraft({ ...draft, q: event.target.value })} placeholder="Explanation, host, technique…" /></Field>
        <Field label="Severity"><select value={draft.severity} onChange={(event) => setDraft({ ...draft, severity: event.target.value })}><option value="">All severities</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option><option>NORMAL</option></select></Field>
        <Field label="Host"><input value={draft.host} onChange={(event) => setDraft({ ...draft, host: event.target.value })} placeholder="Host id" /></Field>
        <Field label="Technique"><input value={draft.technique} onChange={(event) => setDraft({ ...draft, technique: event.target.value })} placeholder="T1110 or name" /></Field>
        <Field label="From"><input type="date" value={draft.from} onChange={(event) => setDraft({ ...draft, from: event.target.value })} /></Field>
        <Field label="To"><input type="date" value={draft.to} onChange={(event) => setDraft({ ...draft, to: event.target.value })} /></Field>
        <Field label="Sort by"><select value={draft.sort} onChange={(event) => setDraft({ ...draft, sort: event.target.value })}><option value="ts">Time</option><option value="risk_score">Risk score</option><option value="severity">Severity</option></select></Field>
        <Field label="Order"><select value={draft.order} onChange={(event) => setDraft({ ...draft, order: event.target.value })}><option value="desc">Newest / highest</option><option value="asc">Oldest / lowest</option></select></Field>
      </FilterBar>
      {exportError && <p className="ops-error" role="alert">{exportError}</p>}
      <ResourceNotice loading={loading} error={error} data={data} onRetry={refresh} />
      {data && <section className="ops-card" aria-label="Alert search results">
        <div className="ops-card-header"><div><h3>Event records</h3><p>{data.total} matching alerts in the current replay buffer</p></div><Button type="button" className="ops-button-quiet" onClick={refresh}>Refresh</Button></div>
        {data.items.length ? <>
          <div className="ops-table-wrap"><table className="ops-table"><thead><tr><th>Event</th><th>Severity</th><th>Host</th><th>Technique</th><th>Risk</th><th>Source</th><th>Observed</th></tr></thead><tbody>
            {data.items.map((alert) => <tr key={alert.event_id}>
              <td data-label="Event"><TableLink to={`/alerts/${encodeURIComponent(alert.event_id)}`}>{alert.event_id}</TableLink><span className="cell-secondary cell-wrap">{alert.explanation}</span></td>
              <td data-label="Severity"><Severity value={alert.severity} /></td>
              <td data-label="Host"><Link className="ops-text-link ops-mono" to={`/hosts/${encodeURIComponent(alert.host)}`}>{alert.host}</Link></td>
              <td data-label="Technique">{alert.technique_id ? <><span className="ops-mono">{alert.technique_id}</span><span className="cell-secondary">{alert.technique_name}</span></> : '—'}</td>
              <td data-label="Risk" className="cell-mono">{Math.round(alert.risk_score)} / 100</td>
              <td data-label="Source"><SourceBadge value={alert.source} /></td>
              <td data-label="Observed"><span className="cell-secondary">{formatTime(alert.ts)}</span></td>
            </tr>)}
          </tbody></table></div>
          <Pagination cursor={cursor} nextCursor={data.next_cursor} total={data.total} onPrevious={() => setCursor(String(Math.max(0, Number(cursor || 0) - PAGE_SIZE)) || '')} onNext={() => setCursor(data.next_cursor)} />
        </> : <EmptyMessage title="No alerts match these filters">Clear a filter or run a replay to add simulated detection events.</EmptyMessage>}
      </section>}
    </PageFrame>
  )
}

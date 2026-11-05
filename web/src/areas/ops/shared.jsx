import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Icon } from '../../shared/icons.jsx'
import '../../shared/ops-pages.css'

export function useResource(load, key) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let active = true
    setLoading(true)
    load().then((value) => {
      if (!active) return
      setData(value)
      setError('')
    }).catch((reason) => {
      if (active) setError(reason.message || 'Unable to load this view.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [load, key, revision])
  return { data, loading, error, refresh: () => setRevision((value) => value + 1) }
}

export function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <header className="ops-page-header">
      <div><p className="ops-eyebrow">{eyebrow}</p><h2>{title}</h2><p className="ops-description">{description}</p></div>
      <div className="ops-header-actions">{actions}</div>
    </header>
  )
}

export function PageFrame({ children, className = '' }) {
  return <main className={`ops-page ${className}`}>{children}</main>
}

export function LoadingMessage({ label = 'Loading workspace data…' }) {
  return <div className="ops-state-card" role="status"><span className="ops-loading-mark" aria-hidden="true" />{label}</div>
}

export function EmptyMessage({ title, children }) {
  return <div className="ops-empty"><span className="ops-empty-mark" aria-hidden="true" /><h3>{title}</h3>{children && <p>{children}</p>}</div>
}

export function ErrorMessage({ message, onRetry }) {
  return <div className="ops-error" role="alert"><div><strong>Could not load this view</strong><p>{message}</p></div>{onRetry && <button className="ops-button" type="button" onClick={onRetry}>Retry</button>}</div>
}

export function ResourceNotice({ loading, error, data, onRetry }) {
  if (loading && !data) return <LoadingMessage />
  if (error && !data) return <ErrorMessage message={error} onRetry={onRetry} />
  if (error && data) return <div className="ops-stale" role="status">Showing saved results. Refresh failed: {error} <button type="button" onClick={onRetry}>Retry</button></div>
  return null
}

export function Button({ children, className = '', ...props }) {
  return <button className={`ops-button ${className}`} {...props}>{children}</button>
}

export function LinkButton({ to, children, className = '' }) {
  return <Link className={`ops-button ${className}`} to={to}>{children}</Link>
}

export function Severity({ value }) {
  const severity = String(value || 'NORMAL').toLowerCase()
  return <span className={`ops-severity severity-${severity}`}><i aria-hidden="true" />{value || 'NORMAL'}</span>
}

export function StateBadge({ value }) {
  const state = String(value || 'normal').toLowerCase()
  return <span className={`ops-state-badge state-${state}`}><i aria-hidden="true" />{state}</span>
}

export function SourceBadge({ value }) {
  return <span className={`ops-source source-${value === 'scripted' ? 'scripted' : 'detector'}`}>{value === 'scripted' ? 'SCRIPTED' : 'NIDS DETECTOR'}</span>
}

export function Pagination({ cursor, nextCursor, total, onPrevious, onNext }) {
  const page = Math.floor(Number(cursor || 0) / 50) + 1
  return (
    <div className="ops-pagination"><span>{total} results · page {page}</span><div>
      <button type="button" className="ops-button ops-button-secondary" onClick={onPrevious} disabled={!cursor}>Previous</button>
      <button type="button" className="ops-button ops-button-secondary" onClick={onNext} disabled={!nextCursor}>Next</button>
    </div></div>
  )
}

export function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'medium', timeZone: 'UTC' }).format(date) + ' UTC'
}

export function TableLink({ to, children }) {
  return <Link className="ops-table-link" to={to}>{children}<Icon name="chevron" size={15} /></Link>
}

export function FilterBar({ children, onSubmit, onReset, className = '' }) {
  return <form className={`ops-filter-bar ${className}`} onSubmit={onSubmit}><div className="ops-filter-fields">{children}</div><div className="ops-filter-actions"><Button type="submit">Apply filters</Button>{onReset && <Button type="button" className="ops-button-secondary" onClick={onReset}>Reset</Button>}</div></form>
}

export function Field({ label, children, className = '' }) {
  return <label className={`ops-field ${className}`}><span>{label}</span>{children}</label>
}

export function SearchField({ value, onChange, placeholder = 'Search records' }) {
  return <div className="ops-search-field"><Icon name="search" size={17} /><input value={value} onChange={onChange} placeholder={placeholder} /></div>
}

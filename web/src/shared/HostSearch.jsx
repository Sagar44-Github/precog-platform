import { useEffect, useId, useState } from 'react'
import { api } from './api.js'
import './host-search.css'

/** Server-backed host search that works even when the active inventory is paged. */
export default function HostSearch({ onSelect, selectedHost = '', selectedName = '', label = 'Find a host' }) {
  const inputId = useId()
  const listId = useId()
  const [query, setQuery] = useState(selectedName)
  const [results, setResults] = useState([])
  const [focused, setFocused] = useState(false)
  const [active, setActive] = useState(-1)
  const [error, setError] = useState('')

  useEffect(() => {
    setQuery(selectedName || '')
  }, [selectedHost, selectedName])

  useEffect(() => {
    const search = query.trim()
    if (!focused || search.length < 1 || search === selectedName) {
      setResults([])
      setError('')
      return undefined
    }
    let alive = true
    const timer = window.setTimeout(() => {
      api.topologySummary({ limit: 8, q: search }).then((result) => {
        if (alive) { setResults(result.items || []); setError(''); setActive(-1) }
      }).catch((reason) => { if (alive) { setResults([]); setError(reason.message || 'Host search is unavailable.') } })
    }, 180)
    return () => { alive = false; window.clearTimeout(timer) }
  }, [focused, query, selectedName])

  function choose(host) {
    setQuery(host.name)
    setResults([])
    setFocused(false)
    onSelect?.(host)
  }

  function onKeyDown(event) {
    if (event.key === 'ArrowDown' && results.length) {
      event.preventDefault()
      setActive((index) => (index + 1) % results.length)
    } else if (event.key === 'ArrowUp' && results.length) {
      event.preventDefault()
      setActive((index) => index <= 0 ? results.length - 1 : index - 1)
    } else if (event.key === 'Enter' && active >= 0 && results[active]) {
      event.preventDefault()
      choose(results[active])
    } else if (event.key === 'Escape') {
      setResults([])
      setFocused(false)
    }
  }

  const open = focused && results.length > 0
  return <div className="host-search">
    <label htmlFor={inputId}>{label}</label>
    <input id={inputId} type="search" role="combobox" aria-autocomplete="list" aria-expanded={open}
      aria-controls={listId} aria-activedescendant={active >= 0 && open ? `${listId}-option-${active}` : undefined}
      value={query} placeholder="Name, zone, service or host ID" onFocus={() => setFocused(true)}
      onBlur={() => window.setTimeout(() => setFocused(false), 100)} onKeyDown={onKeyDown}
      onChange={(event) => { setQuery(event.target.value); setFocused(true) }} />
    {error && <span className="host-search-message" role="status">{error}</span>}
    {open && <div id={listId} className="host-search-results" role="listbox" aria-label="Matching hosts">
      {results.map((host, index) => <button id={`${listId}-option-${index}`} type="button" role="option" aria-selected={index === active}
        key={host.host_id} onMouseDown={(event) => event.preventDefault()} onClick={() => choose(host)}>
        <span><b>{host.name}</b><small>{host.zone} · {host.role}</small></span><code>{host.host_id}</code>
      </button>)}
    </div>}
    {focused && query.trim() && results.length === 0 && !error && <span className="host-search-message" role="status">No matching host found.</span>}
  </div>
}

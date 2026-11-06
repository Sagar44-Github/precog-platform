import { useRef, useState } from 'react'
import { virtualWindow } from './network3d/lite-layout.js'
import './virtualized-table.css'

/** Fixed-row virtual table. Renderers stay in the DOM only for the visible window plus overscan. */
export default function VirtualizedTable({ label, headers, items, totalCount = items.length, rowHeight = 62, height = 500, columns, renderRow }) {
  const viewport = useRef(null)
  const [scrollTop, setScrollTop] = useState(0)
  const windowed = virtualWindow(items.length, scrollTop, rowHeight, height, 5)
  const visible = items.slice(windowed.start, windowed.end)
  const gridTemplateColumns = columns || `minmax(220px, 2fr) repeat(${Math.max(0, headers.length - 1)}, minmax(90px, 1fr))`
  return <div className="virtual-table" role="table" aria-label={label} aria-rowcount={totalCount + 1}>
    <div className="virtual-table-header" role="rowgroup">
      <div className="virtual-table-row virtual-table-head" role="row" style={{ gridTemplateColumns }}>
        {headers.map((header) => <div role="columnheader" key={header}>{header}</div>)}
      </div>
    </div>
    <div className="virtual-table-viewport" ref={viewport} role="rowgroup" tabIndex="0" aria-label={`${label} rows`}
      style={{ height }} onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}>
      <div className="virtual-table-spacer" style={{ height: windowed.totalHeight }}>
        <div className="virtual-table-window" style={{ transform: `translateY(${windowed.offset}px)` }}>
          {visible.map((item, localIndex) => renderRow(item, windowed.start + localIndex, gridTemplateColumns, rowHeight))}
        </div>
      </div>
      {!items.length && <p className="virtual-table-empty">No matching hosts.</p>}
    </div>
  </div>
}

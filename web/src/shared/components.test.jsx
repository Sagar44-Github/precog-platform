import test from 'node:test'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { EmptyState, LoadingState, SimulationBadge, StaleBanner, ToastProvider } from './components.jsx'
import DemoStart from './DemoStart.jsx'

test('the simulation badge always says SIMULATION', () => {
  assert.match(renderToStaticMarkup(<SimulationBadge />), /SIMULATION/)
})

test('the stale banner shows only when stale', () => {
  assert.equal(renderToStaticMarkup(<StaleBanner stale={false} />), '')
  assert.match(renderToStaticMarkup(<StaleBanner stale />), /Connection lost: showing old data/)
})

test('empty and loading states render', () => {
  assert.match(renderToStaticMarkup(<EmptyState>No alerts yet.</EmptyState>), /No alerts yet\./)
  assert.equal((renderToStaticMarkup(<LoadingState lines={4} />).match(/skeleton/g) || []).length, 4)
})

test('the toast provider renders its children and no toast until one is shown', () => {
  const html = renderToStaticMarkup(<ToastProvider><p>screen</p></ToastProvider>)
  assert.match(html, /<p>screen<\/p>/)
  assert.doesNotMatch(html, /class="toast"/)
})

test('the demo launcher explains the replay and keeps containment human-confirmed', () => {
  const html = renderToStaticMarkup(<DemoStart hostCount={6} />)
  assert.match(html, /Start Golden Path/)
  assert.match(html, /SIMULATION ONLY/)
  assert.match(html, /You choose whether to contain/)
  assert.match(html, /6 HOSTS/)
})

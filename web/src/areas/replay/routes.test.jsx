import test from 'node:test'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server.js'
import { Route, Routes } from 'react-router-dom'
import ReplayStudioApp from './index.jsx'
import AppShell from '../../shared/AppShell.jsx'
import { AuthProvider } from '../../shared/AuthContext.jsx'
import { ThemeProvider } from '../../shared/theme-context.jsx'

function render(location) {
  return renderToStaticMarkup(
    <StaticRouter location={location}>
      <AuthProvider><ThemeProvider><Routes><Route path="*" element={<AppShell><ReplayStudioApp /></AppShell>} /></Routes></ThemeProvider></AuthProvider>
    </StaticRouter>,
  )
}

test('studio and scenario library deep links render the app shell and simulation disclosure', () => {
  const studio = render('/replay')
  assert.match(studio, /Replay studio/)
  assert.match(studio, /Scenario library/)
  assert.match(studio, /SIMULATION/)
  const library = render('/scenarios')
  assert.match(library, /Scenarios/)
  assert.match(library, /Build scenario/)
})

test('scenario builder and edit deep links resolve to the builder workbench', () => {
  assert.match(render('/scenarios/new'), /Scenario builder/)
  assert.match(render('/scenarios/user-demo/edit'), /Edit scenario/)
})

test('run history, report and query based comparison deep links resolve', () => {
  assert.match(render('/runs'), /Run history/)
  assert.match(render('/runs/RUN-000001'), /RUN-000001/)
  const comparison = render('/runs/compare?a=RUN-000001&b=RUN-000002')
  assert.match(comparison, /Run comparison/)
  assert.match(comparison, /Wall-clock fields are excluded/)
})

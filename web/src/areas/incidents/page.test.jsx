import test from 'node:test'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server.js'
import { Route, Routes } from 'react-router-dom'
import IncidentsApp from './index.jsx'
import { AuthProvider } from '../../shared/AuthContext.jsx'
import { ThemeProvider } from '../../shared/theme-context.jsx'

function render(location) {
  return renderToStaticMarkup(
    <StaticRouter location={location}>
      <AuthProvider><ThemeProvider><Routes><Route path="/incidents/*" element={<IncidentsApp />} /></Routes></ThemeProvider></AuthProvider>
    </StaticRouter>,
  )
}

test('incident queue renders its case filters and replay path inside the shared workspace', () => {
  const html = render('/incidents')
  assert.match(html, /Incident investigations/)
  assert.match(html, /Filter cases/i)
  assert.match(html, /All statuses/)
  assert.match(html, /Run a replay/)
})

test('incident detail URLs render a deep-linked investigation without a nested shell', () => {
  const html = render('/incidents/INC-0001')
  assert.match(html, /Loading investigation/)
  assert.doesNotMatch(html, /Workspace navigation/)
})

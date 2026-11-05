import test from 'node:test'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server.js'
import { AuthProvider, LoginPage } from './AuthContext.jsx'
import { ThemeProvider } from './theme-context.jsx'

test('sign-in keeps the existing credentials flow and presents the Precog network story', () => {
  const html = renderToStaticMarkup(<StaticRouter location="/login"><AuthProvider><ThemeProvider><LoginPage /></ThemeProvider></AuthProvider></StaticRouter>)
  for (const text of ['DETECT · RECONSTRUCT · PREDICT · CONTAIN', 'OBSERVED PATH', 'MODEL ESTIMATE', 'ISOLATION', 'Operator ID', 'Access key', 'Enter command center', 'Show password', 'Back to product overview']) {
    assert.ok(html.includes(text), `expected sign-in markup to include ${text}`)
  }
  assert.match(html, /autoComplete="current-password"/)
  assert.match(html, /role="alert"/)
})

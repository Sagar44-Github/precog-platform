import test from 'node:test'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server.js'
import { AuthProvider } from '../shared/AuthContext.jsx'
import LandingPage from './LandingPage.jsx'

test('public landing page has one h1, ordered sections, a skip link, and accessible demo controls', () => {
  const html = renderToStaticMarkup(<StaticRouter location="/"><AuthProvider><LandingPage /></AuthProvider></StaticRouter>)
  assert.equal((html.match(/<h1\b/g) || []).length, 1)
  assert.equal((html.match(/<h2\b/g) || []).length, 3)
  assert.ok(html.indexOf('Skip to content') < html.indexOf('landing-brand'))
  assert.match(html, /aria-label="Interactive 3D network replay"/)
  assert.match(html, /id="landing-step-range"/)
  assert.match(html, /id="landing-host-select"/)
  assert.match(html, /Replay Golden Path/)
  assert.match(html, /Detect/)
  assert.match(html, /Confirm/)
  assert.match(html, /45%/)
  assert.match(html, /demo hosts/)
  assert.match(html, /network zones/)
})

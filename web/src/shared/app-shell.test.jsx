import test from 'node:test'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server.js'
import { AuthProvider } from './AuthContext.jsx'
import AppShell, { CommandPalette } from './AppShell.jsx'
import { ThemeProvider } from './theme-context.jsx'

function render(element) {
  return renderToStaticMarkup(
    <StaticRouter location="/console">
      <AuthProvider><ThemeProvider>{element}</ThemeProvider></AuthProvider>
    </StaticRouter>,
  )
}

test('the desktop shell provides workspace navigation and a permanent simulation label', () => {
  const html = render(<AppShell><div>console content</div></AppShell>)
  assert.match(html, /Workspace navigation/)
  assert.match(html, /Live console/)
  assert.match(html, /Monitoring &amp; Operations/)
  assert.match(html, /aria-haspopup="menu"/)
  assert.match(html, /Hosts &amp; assets/)
  assert.doesNotMatch(html, /href="\/alerts"/)
  assert.match(html, /Settings/)
  assert.doesNotMatch(html, /Mobile SOC/)
  assert.match(html, /title="Return to landing page"/)
  assert.match(html, /<a class="app-brand"[^>]*href="\/"/)
  assert.match(html, /project-logo-dark\.svg/)
  assert.match(html, /SIMULATION/)
  assert.match(html, /console content/)
  assert.ok(html.indexOf('Skip to main content') < html.indexOf('app-brand'))
})

test('the command palette exposes replay, navigation, and theme actions', () => {
  const html = render(<CommandPalette open onClose={() => {}} permissions={{ can_run_replay: true }} />)
  for (const label of ['Open live console', 'Open alert explorer', 'Open session reports', 'Start Golden Path replay', 'Switch to light theme']) {
    assert.match(html, new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
  assert.doesNotMatch(html, /mobile SOC|phone PWA/i)
  assert.match(html, /role="dialog" aria-modal="true"/)
  assert.match(html, /Search commands/)
})

test('shared disclosure sections keep a visible heading and native keyboard behavior', async () => {
  const { CollapsibleSection } = await import('./components.jsx')
  const html = render(<CollapsibleSection title="Recent events" meta="3 records"><p>event detail</p></CollapsibleSection>)
  assert.match(html, /<details class="disclosure">/)
  assert.match(html, /<summary><span>Recent events<\/span><small>3 records<\/small><\/summary>/)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { renderToStaticMarkup } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom/server.js'
import { AuthProvider } from './AuthContext.jsx'
import AppShell, { CommandPalette, ConsoleHandoff } from './AppShell.jsx'
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
  assert.match(html, /Alerts/)
  assert.match(html, /Hosts &amp; assets/)
  assert.match(html, /Audit log/)
  assert.match(html, /System health/)
  assert.match(html, /Settings/)
  assert.match(html, /Mobile SOC/)
  assert.match(html, /SIMULATION/)
  assert.match(html, /console content/)
})

test('the command palette exposes replay, navigation, and theme actions', () => {
  const html = render(<CommandPalette open onClose={() => {}} permissions={{ can_run_replay: true }} />)
  for (const label of ['Open live console', 'Open mobile SOC', 'Start Golden Path replay', 'Switch to light theme']) {
    assert.match(html, new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
  assert.match(html, /role="dialog" aria-modal="true"/)
  assert.match(html, /Search commands/)
})

test('the narrow console handoff retains the simulation label and mobile destination', () => {
  const html = render(<ConsoleHandoff />)
  assert.match(html, /SIMULATION/)
  assert.match(html, /Open mobile SOC/)
  assert.match(html, /1024 PX MINIMUM/)
})

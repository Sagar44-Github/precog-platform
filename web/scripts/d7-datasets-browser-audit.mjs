import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)))
const output = join(root, 'docs', 'audit', 'screenshots', 'phase-d7')
const port = 4174
const vite = join(root, 'web', 'node_modules', 'vite', 'bin', 'vite.js')
const server = spawn(process.execPath, [vite, 'preview', '--host', '127.0.0.1', '--port', String(port), '--strictPort'], { cwd: join(root, 'web'), stdio: 'ignore', windowsHide: true })
let browser
try {
  const base = `http://127.0.0.1:${port}`
  const deadline = Date.now() + 30000
  while (Date.now() < deadline) {
    try { if ((await fetch(base)).ok) break } catch {}
    await new Promise((done) => setTimeout(done, 200))
  }
  browser = await chromium.launch({ headless: true, args: ['--use-gl=angle', '--use-angle=swiftshader'] })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  let active = 'demo-6'
  const packs = [
    { id: 'demo-6', name: 'Precog six-host deterministic demo', version: '1.0.0', status: 'available', counts: { hosts: 6, edges: 11, events: 16, routes: 300 }, redistribution: 'project-owned', capabilities: { detection_labels: 'native', host_compromise: 'native', lateral_movement_routes: 'native', topology: 'native' } },
    { id: 'synth-enterprise-30', name: 'Synthetic enterprise 30-host pack', version: '1.0.0', status: 'available', counts: { hosts: 30, edges: 48, events: 1200, routes: 800 }, redistribution: 'synthetic', capabilities: { detection_labels: 'native', host_compromise: 'derived', lateral_movement_routes: 'derived', topology: 'derived' } },
    { id: 'lanl-cyber1', name: 'LANL Cyber1 authentication and system events', version: '0.0.0', status: 'unavailable', counts: { hosts: 0, edges: 0, events: 0, routes: 0 }, redistribution: 'builder-only-pending-release-review', capabilities: { detection_labels: 'native', host_compromise: 'derived', lateral_movement_routes: 'derived', topology: 'derived' } },
  ]
  const card = (item) => ({ id: item.id, name: item.name, summary: `${item.name}\nSource notes for this registered data workspace.`, source: { id: item.id, name: item.name, citation: 'Example project card citation.', licence: item.redistribution, terms_summary: item.redistribution }, redistribution: item.redistribution, capabilities: item.capabilities, limitations: item.status === 'unavailable' ? ['Pack is not installed in this local simulation.'] : ['Generated routes are simulation estimates.'] })
  await page.route('**/api/x/**', async (route) => {
    const url = new URL(route.request().url())
    const id = url.pathname.match(/\/workspaces\/([^/]+)\/card$/)?.[1]
    let body = {}
    if (url.pathname === '/api/x/me') body = { username: 'd7-reviewer', role: 'admin' }
    else if (url.pathname === '/api/x/workspaces') body = { active_workspace: active, workspaces: packs.map((item) => ({ ...item, status: item.id === active ? 'active' : item.status })) }
    else if (url.pathname === '/api/x/workspaces/active') body = { id: active }
    else if (id) body = card(packs.find((item) => item.id === decodeURIComponent(id)) || packs[0])
    else if (url.pathname.includes('/workspaces/') && route.request().method() === 'POST') {
      active = decodeURIComponent(url.pathname.split('/').at(-2))
      body = { id: active }
    } else if (url.pathname.startsWith('/api/x/incidents')) body = { items: [], total: 0 }
    else if (url.pathname.includes('/containment/governance')) body = { approvals: [], releases: [] }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  mkdirSync(output, { recursive: true })

  await page.goto(`${base}/app/datasets`, { waitUntil: 'networkidle' })
  await page.locator('.datasets-page h2').filter({ hasText: 'Dataset workspaces' }).waitFor()
  await page.once('dialog', (dialog) => dialog.accept())
  await page.locator('.app-top-actions select[aria-label="Active dataset workspace"]').selectOption('synth-enterprise-30')
  await page.waitForFunction(() => document.querySelector('.workspace-context b')?.textContent === 'Synthetic enterprise 30-host pack')

  const dimensions = [[390, 844], [820, 1180], [1440, 900]]
  const widths = []
  for (const [width, height] of dimensions) {
    await page.setViewportSize({ width, height })
    await page.goto(`${base}/app/datasets`, { waitUntil: 'networkidle' })
    await page.locator('.datasets-page h2').filter({ hasText: 'Dataset workspaces' }).waitFor()
    widths.push({ route: 'datasets', width, scrollWidth: await page.evaluate(() => document.documentElement.scrollWidth) })
    await page.screenshot({ path: join(output, `datasets-${width}x${height}.png`), fullPage: true })
  }
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${base}/app/datasets/synth-enterprise-30`, { waitUntil: 'networkidle' })
  await page.locator('.datasets-page h2').filter({ hasText: 'Synthetic enterprise 30-host pack' }).waitFor()
  await page.getByText('Derived for this simulation').first().waitFor()
  await page.screenshot({ path: join(output, 'dataset-detail-1440x900.png'), fullPage: true })
  await page.goto(`${base}/app/datasets/compare?left=demo-6&right=synth-enterprise-30`, { waitUntil: 'networkidle' })
  await page.locator('.datasets-page h2').filter({ hasText: 'Compare dataset workspaces' }).waitFor()
  await page.getByText('Capability comparison').waitFor()
  await page.screenshot({ path: join(output, 'dataset-compare-1440x900.png'), fullPage: true })
  if (errors.length) throw new Error(`Browser errors: ${JSON.stringify(errors)}`)
  if (widths.some((item) => item.width !== item.scrollWidth)) throw new Error(`Horizontal overflow: ${JSON.stringify(widths)}`)
  console.log(JSON.stringify({ activeAfterSwitch: active, widths, screenshots: 5, browserErrors: errors.length }, null, 2))
} finally {
  if (browser) await browser.close()
  server.kill()
}

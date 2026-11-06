import { chromium } from 'playwright'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { spawn } from 'node:child_process'
import { createServer } from 'node:net'
import { randomBytes } from 'node:crypto'
import { fileURLToPath } from 'node:url'

const repoRoot = resolve(fileURLToPath(new URL('../..', import.meta.url)))
const screenshotDir = join(repoRoot, 'docs', 'audit', 'screenshots', 'phase-d6')
const tempDir = mkdtempSync(join(tmpdir(), 'precog-d6-'))
const password = randomBytes(18).toString('hex')
const sizes = [
  { name: '390x844', width: 390, height: 844 },
  { name: '820x1180', width: 820, height: 1180 },
  { name: '1440x900', width: 1440, height: 900 },
]
const frameBudgetMs = 1000 / 30

async function freePort() {
  const probe = createServer()
  await new Promise((resolveListen, reject) => probe.once('error', reject).listen(0, '127.0.0.1', resolveListen))
  const { port } = probe.address()
  await new Promise((resolveClose) => probe.close(resolveClose))
  return port
}

function startBackend(port) {
  const db = join(tempDir, 'scale.sqlite').replaceAll('\\', '/')
  const env = {
    ...process.env,
    SECRET_KEY: randomBytes(32).toString('hex'),
    ADMIN_PASSWORD: password,
    DATABASE_URL: `sqlite:///${db}`,
    DATA_MODE: 'sample',
    PRECOG_DATA_DIR: join(tempDir, 'data'),
    HOST: '127.0.0.1',
    PORT: String(port),
    WEB_DIST: join(repoRoot, 'lead-core', 'backend', 'web_dist'),
    COOKIE_SECURE: '0',
    AUTO_TRAIN_MODEL: '1',
    VALIDATE_CONTRACTS: '1',
    PUSH_WATCHER: '0',
  }
  const python = process.env.PYTHON || join(repoRoot, '.venv', 'Scripts', 'python.exe')
  const child = spawn(python, ['lead-core/backend/run_app.py'], { cwd: repoRoot, env, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true })
  let output = ''
  child.stdout.on('data', (chunk) => { output = (output + chunk.toString()).slice(-12000) })
  child.stderr.on('data', (chunk) => { output = (output + chunk.toString()).slice(-12000) })
  return { child, getOutput: () => output }
}

async function waitForBackend(base, processInfo) {
  const deadline = Date.now() + 120000
  while (Date.now() < deadline) {
    if (processInfo.child.exitCode !== null) throw new Error(`Backend exited early:\n${processInfo.getOutput()}`)
    try {
      const response = await fetch(`${base}/api/x/health`)
      if (response.ok) return
    } catch {}
    await new Promise((resolveWait) => setTimeout(resolveWait, 500))
  }
  throw new Error(`Backend did not become ready:\n${processInfo.getOutput()}`)
}

async function stopBackend(child) {
  if (child.exitCode !== null) return
  child.kill()
  await Promise.race([new Promise((done) => child.once('exit', done)), new Promise((done) => setTimeout(done, 5000))])
}

function collectFrameProbe(page) {
  return page.evaluate(() => new Promise((resolveProbe) => {
    const times = []
    const started = performance.now()
    let previous = started
    function sample(now) {
      times.push(now - previous)
      previous = now
      if (now - started < 1600) requestAnimationFrame(sample)
      else {
        const frames = times.slice(1).sort((a, b) => a - b)
        const mean = frames.reduce((sum, value) => sum + value, 0) / Math.max(frames.length, 1)
        const percentile = (p) => frames[Math.min(frames.length - 1, Math.floor((frames.length - 1) * p))] || null
        resolveProbe({
          samples: frames.length,
          meanFrameMs: Number(mean.toFixed(2)),
          p95FrameMs: percentile(0.95) === null ? null : Number(percentile(0.95).toFixed(2)),
          maxFrameMs: frames.length ? Number(frames.at(-1).toFixed(2)) : null,
          framesOverBudget: frames.filter((value) => value > frameBudgetMs).length,
          observedFpsFromMean: Number((1000 / mean).toFixed(1)),
          frameBudgetMs: Number(frameBudgetMs.toFixed(2)),
          budgetPass: mean <= frameBudgetMs && percentile(0.95) <= frameBudgetMs,
          jsHeapUsedBytes: performance.memory?.usedJSHeapSize ?? null,
          jsHeapLimitBytes: performance.memory?.jsHeapSizeLimit ?? null,
          canvasPixels: Array.from(document.querySelectorAll('canvas')).reduce((sum, canvas) => sum + canvas.width * canvas.height, 0),
        })
      }
    }
    requestAnimationFrame(sample)
  }))
}

async function assertNoHorizontalOverflow(page, name) {
  const metrics = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }))
  if (metrics.scrollWidth > metrics.width) throw new Error(`${name} horizontal overflow: ${metrics.scrollWidth}px > ${metrics.width}px`)
  return metrics
}

const report = { workspace: 'synth-enterprise-300', browser: 'Playwright Chromium with SwiftShader software WebGL', screenshots: [], viewportChecks: [], errors: [], probes: {} }
let processInfo
let browser
let context
try {
  mkdirSync(screenshotDir, { recursive: true })
  const port = await freePort()
  const base = `http://127.0.0.1:${port}`
  processInfo = startBackend(port)
  await waitForBackend(base, processInfo)
  browser = await chromium.launch({ headless: true, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist', '--enable-precise-memory-info'] })
  context = await browser.newContext({ serviceWorkers: 'block' })
  const page = await context.newPage()
  page.on('pageerror', (error) => report.errors.push(`page: ${error.stack || error.message}`))
  page.on('console', (message) => { if (message.type() === 'error') report.errors.push(`console: ${message.text()}`) })
  page.on('response', (response) => { if (response.status() >= 400 && !(response.status() === 401 && response.url().includes('/api/x/me'))) report.errors.push(`HTTP ${response.status()}: ${response.url()}`) })

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${base}/app/login`, { waitUntil: 'domcontentloaded' })
  await page.locator('#login-username').fill('admin')
  await page.locator('#login-password').fill(password)
  await page.locator('button[type="submit"]').click()
  await page.waitForURL('**/app/console', { timeout: 15000 })
  const activation = await page.evaluate(async () => {
    const response = await fetch('/api/x/workspaces/synth-enterprise-300/activate', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Precog-Request': '1' }, body: JSON.stringify({ confirm: true }),
    })
    return { status: response.status, body: await response.json() }
  })
  if (activation.status !== 200) throw new Error(`Could not activate scale fixture: ${JSON.stringify(activation.body)}`)
  const inventory = await page.evaluate(async () => (await fetch('/api/x/topology/summary?limit=1')).json())
  if (inventory.total_hosts !== 300 || inventory.total_edges !== 2400) throw new Error(`Unexpected scale fixture summary: ${JSON.stringify({ hosts: inventory.total_hosts, edges: inventory.total_edges })}`)

  await page.goto(`${base}/app/console/topology`, { waitUntil: 'domcontentloaded' })
  await page.locator('.topology-page-heading h2').waitFor({ timeout: 20000 })
  await page.locator('.topology-canvas-wrap canvas').waitFor({ timeout: 20000 })
  await page.getByRole('status').filter({ hasText: 'Scale view' }).waitFor({ timeout: 10000 })
  report.probes.topology3d = await collectFrameProbe(page)
  if (!report.probes.topology3d.budgetPass) throw new Error(`Topology 3D exceeded the ${frameBudgetMs.toFixed(1)} ms mean/p95 frame budget.`)
  await page.screenshot({ path: join(screenshotDir, 'topology-3d-1440x900.png'), fullPage: true, animations: 'disabled' })
  report.screenshots.push('topology-3d-1440x900.png')
  await page.getByRole('button', { name: 'Lite' }).click()
  await page.getByRole('button', { name: /host cluster/ }).first().waitFor({ timeout: 8000 })
  await page.getByRole('button', { name: /host cluster/ }).first().click()
  await page.locator('.topology-scale-status').getByRole('button', { name: /^Collapse / }).waitFor({ timeout: 8000 })
  await page.screenshot({ path: join(screenshotDir, 'topology-lite-expanded-1440x900.png'), fullPage: true, animations: 'disabled' })
  report.screenshots.push('topology-lite-expanded-1440x900.png')

  await page.goto(`${base}/app/twin`, { waitUntil: 'domcontentloaded' })
  await page.locator('.twin-page-head h1').waitFor({ timeout: 20000 })
  await page.locator('.twin-map-viewport canvas').waitFor({ timeout: 20000 })
  await page.getByRole('status').filter({ hasText: 'Clustered scale view' }).waitFor({ timeout: 10000 })
  report.probes.twin3d = await collectFrameProbe(page)
  if (!report.probes.twin3d.budgetPass) throw new Error(`Network twin 3D exceeded the ${frameBudgetMs.toFixed(1)} ms mean/p95 frame budget.`)
  await page.screenshot({ path: join(screenshotDir, 'twin-3d-1440x900.png'), fullPage: true, animations: 'disabled' })
  report.screenshots.push('twin-3d-1440x900.png')
  await page.getByRole('button', { name: 'Preview' }).click()
  await page.locator('.twin-tools-grid > section').nth(1).locator('.twin-results').waitFor({ timeout: 10000 })
  report.segmentationPreview = 'active-workspace edge preview returned successfully'
  await page.getByRole('button', { name: 'Lite view' }).click()
  await page.getByRole('button', { name: /host zone cluster/ }).first().waitFor({ timeout: 8000 })
  await page.getByRole('button', { name: /host zone cluster/ }).first().click()
  await page.locator('.twin-scale-message').getByRole('button', { name: /^Collapse / }).waitFor({ timeout: 8000 })
  await page.screenshot({ path: join(screenshotDir, 'twin-lite-expanded-1440x900.png'), fullPage: true, animations: 'disabled' })
  report.screenshots.push('twin-lite-expanded-1440x900.png')

  for (const size of sizes) {
    await page.setViewportSize(size)
    await page.goto(`${base}/app/twin`, { waitUntil: 'domcontentloaded' })
    await page.locator('.twin-page-head h1').waitFor({ timeout: 15000 })
    if (size.width >= 760) await page.getByRole('button', { name: 'Lite view' }).click()
    await page.locator('.twin-lite-map:visible, .twin-lite-compact:visible').first().waitFor({ timeout: 15000 })
    report.viewportChecks.push({ page: 'twin-lite', viewport: size.name, ...(await assertNoHorizontalOverflow(page, `twin ${size.name}`)) })
    await page.screenshot({ path: join(screenshotDir, `twin-lite-${size.name}.png`), fullPage: true, animations: 'disabled' })
    report.screenshots.push(`twin-lite-${size.name}.png`)
  }

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext
    HTMLCanvasElement.prototype.getContext = function getContextWithoutWebGL(type, ...args) {
      if (['webgl', 'webgl2', 'experimental-webgl'].includes(String(type).toLowerCase())) return null
      return original.call(this, type, ...args)
    }
  })
  await page.goto(`${base}/app/twin?no-webgl=${Date.now()}`, { waitUntil: 'domcontentloaded' })
  await page.locator('.twin-page-head h1').waitFor({ timeout: 15000 })
  await page.locator('.twin-lite-map').waitFor({ timeout: 15000 })
  if (await page.locator('.twin-map-viewport canvas').count()) throw new Error('No-WebGL Twin rendered a canvas instead of the Lite view.')
  report.noWebGL = { renderedLite: true, canvasCount: 0 }
  await page.screenshot({ path: join(screenshotDir, 'twin-no-webgl-1440x900.png'), fullPage: true, animations: 'disabled' })
  report.screenshots.push('twin-no-webgl-1440x900.png')

  await page.goto(`${base}/app/hosts`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'Asset directory' }).waitFor({ timeout: 15000 })
  await page.locator('.virtual-table').waitFor({ timeout: 15000 })
  const rows = await page.locator('.twin-directory-row').count()
  if (rows > 25 || rows < 1) throw new Error(`Paged, virtual host list rendered an unexpected ${rows} visible rows.`)
  report.pagedHostList = { visibleRows: rows, rowPageSize: 60 }
  await page.getByLabel('Search hosts').fill('node-0025')
  await page.getByRole('link', { name: /node-0025/ }).waitFor({ timeout: 10000 })
  report.pagedHostList.serverSearch = 'found node-0025 by server-side search'
  await page.screenshot({ path: join(screenshotDir, 'host-directory-300-1440x900.png'), fullPage: true, animations: 'disabled' })
  report.screenshots.push('host-directory-300-1440x900.png')

  report.errors = [...new Set(report.errors)]
  if (report.errors.length) throw new Error(`Browser errors were detected:\n${report.errors.join('\n')}`)
  writeFileSync(join(screenshotDir, 'scale-probe.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  console.log(JSON.stringify(report, null, 2))
} catch (error) {
  report.errors.push(error.message)
  mkdirSync(screenshotDir, { recursive: true })
  writeFileSync(join(screenshotDir, 'scale-probe.failed.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  console.error(JSON.stringify(report, null, 2))
  process.exitCode = 1
} finally {
  await context?.close().catch(() => {})
  await browser?.close().catch(() => {})
  if (processInfo) await stopBackend(processInfo.child)
  rmSync(tempDir, { recursive: true, force: true })
}

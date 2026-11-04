import { chromium } from 'playwright'
import { PNG } from 'pngjs'
import { randomBytes } from 'node:crypto'
import { mkdirSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const repoRoot = resolve(fileURLToPath(new URL('../..', import.meta.url)))
const artifactsDir = process.env.AUDIT_OUTPUT_DIR
  ? resolve(repoRoot, process.env.AUDIT_OUTPUT_DIR)
  : join(repoRoot, 'docs', 'audit')
const screenshots = join(artifactsDir, 'screenshots')
const basePort = Number(process.env.AUDIT_PORT || 55120)
const password = randomBytes(18).toString('hex')
const sizes = [
  { name: '390x844', width: 390, height: 844 },
  { name: '820x1180', width: 820, height: 1180 },
  { name: '1440x900', width: 1440, height: 900 },
]
const routeSpecs = [
  ['mobile', '/app/mobile'],
  ['mobile-alerts', '/app/mobile/alerts'],
  ['mobile-alert-detail', null],
  ['mobile-forecast', '/app/mobile/forecast'],
  ['mobile-incidents', '/app/mobile/incidents'],
  ['mobile-incident-detail', null],
  ['mobile-history', '/app/mobile/history'],
  ['console', '/app/console'],
  ['alerts', '/app/alerts'],
  ['alert-detail', null],
  ['incidents', '/app/incidents'],
  ['incident-detail', null],
  ['reports', '/app/reports'],
  ['report-detail', null],
  ['forecasts', '/app/forecasts'],
  ['forecast-detail', null],
  ['analytics', '/app/analytics'],
  ['hosts', '/app/hosts'],
  ['host-detail', null],
  ['audit', '/app/audit'],
  ['system', '/app/system'],
  ['settings', '/app/settings'],
]
const report = { browser: 'Playwright Chromium (SwiftShader)', modes: {} }
const expectedEvents = []

function pythonExe() {
  const candidate = join(repoRoot, '.venv', 'Scripts', 'python.exe')
  return process.env.PYTHON || candidate
}

function startBackend(mode, port, dbDir) {
  const db = join(dbDir, `${mode}.sqlite`).replaceAll('\\', '/')
  const env = {
    ...process.env,
    SECRET_KEY: randomBytes(32).toString('hex'),
    ADMIN_PASSWORD: password,
    DATABASE_URL: `sqlite:///${db}`,
    DATA_MODE: mode,
    HOST: '127.0.0.1',
    PORT: String(port),
    WEB_DIST: join(repoRoot, 'web', 'dist'),
    COOKIE_SECURE: '0',
    AUTO_TRAIN_MODEL: '1',
    VALIDATE_CONTRACTS: '1',
    PUSH_WATCHER: '0',
  }
  const child = spawn(pythonExe(), ['lead-core/backend/run_app.py'], {
    cwd: repoRoot,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  let output = ''
  child.stdout.on('data', (chunk) => { output = (output + chunk.toString()).slice(-12000) })
  child.stderr.on('data', (chunk) => { output = (output + chunk.toString()).slice(-12000) })
  return { child, getOutput: () => output }
}

async function waitForBackend(url, processInfo) {
  const deadline = Date.now() + 120000
  while (Date.now() < deadline) {
    if (processInfo.child.exitCode !== null) throw new Error(`Backend exited early:\n${processInfo.getOutput()}`)
    try {
      const response = await fetch(`${url}/api/x/health`)
      if (response.ok) return await response.json()
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error(`Backend did not become ready:\n${processInfo.getOutput()}`)
}

async function stopBackend(child) {
  if (child.exitCode !== null) return
  child.kill()
  await Promise.race([
    new Promise((done) => child.once('exit', done)),
    new Promise((done) => setTimeout(done, 5000)),
  ])
}

async function checkViewport(page, mode, routeName, path, size) {
  await page.setViewportSize({ width: size.width, height: size.height })
  await page.goto(path, { waitUntil: 'domcontentloaded', timeout: 30000 })
  if (routeName === 'console' && size.width >= 1024) {
    await page.locator('.c-app').waitFor({ timeout: 8000 }).catch(() => {})
    await page.waitForFunction(() => document.querySelector('.c-scene canvas'), null, { timeout: 15000 }).catch(() => {})
  }
  await page.waitForTimeout(1800)
  const state = await page.evaluate(() => ({
    width: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    hasSimulationLabel: document.body.innerText.includes('SIMULATION'),
    title: document.title,
    bodyTextPreview: document.body.innerText.slice(0, 360),
    canvasCount: document.querySelectorAll('canvas').length,
    hasConsoleHandoff: Boolean(document.querySelector('.console-handoff')),
    hasCommandTrigger: Boolean(document.querySelector('.command-trigger')),
    mobileHeaderVisible: (() => {
      const header = document.querySelector('.m-top')
      if (!header) return false
      const rect = header.getBoundingClientRect()
      return rect.top >= -1 && rect.top < window.innerHeight && rect.bottom > 0
    })(),
    overflowElements: Array.from(document.querySelectorAll('body *')).map((element) => {
      const rect = element.getBoundingClientRect()
      return { tag: element.tagName.toLowerCase(), className: typeof element.className === 'string' ? element.className : '', left: Math.round(rect.left), right: Math.round(rect.right), width: Math.round(rect.width) }
    }).filter((element) => element.left < -1 || element.right > window.innerWidth + 1).slice(0, 8),
  }))
  const check = { mode, route: routeName, viewport: size.name, ...state, screenshot: `${mode}-${routeName}-${size.name}.png` }
  const failures = []
  if (state.scrollWidth > state.width) failures.push(`horizontal overflow ${state.scrollWidth}px > ${state.width}px`)
  if (!state.hasSimulationLabel) failures.push('SIMULATION label missing')
  if (routeName.startsWith('mobile') && !state.mobileHeaderVisible) failures.push('phone SOC header is outside the visible viewport')
  if (routeName === 'console' && size.width < 1024 && !state.hasConsoleHandoff) failures.push('narrow console handoff is missing')
  if (routeName === 'console' && size.width >= 1024 && !state.hasCommandTrigger) failures.push('desktop command palette trigger is missing')
  if (failures.length) check.failure = failures.join('; ')
  await page.screenshot({ path: join(screenshots, check.screenshot), animations: 'disabled' })
  return check
}

function capturePageErrors(page, mode, errors) {
  page.on('pageerror', (error) => errors.push(`${mode} page error: ${error.message}`))
  page.on('console', (message) => {
    if (message.type() === 'error') {
      if (/Failed to load resource: the server responded with a status of 401 \(UNAUTHORIZED\)/.test(message.text())) {
        expectedEvents.push(`${mode}: unauthenticated session check returned the expected 401 before login`)
      } else errors.push(`${mode} console error: ${message.text()}`)
    }
  })
  page.on('requestfailed', (request) => errors.push(`${mode} request failed: ${request.url()} (${request.failure()?.errorText || 'unknown'})`))
  page.on('response', (response) => {
    if (response.status() >= 400 && !(response.status() === 401 && response.url().includes('/api/x/me'))) {
      errors.push(`${mode} HTTP ${response.status()}: ${response.url()}`)
    }
  })
}

async function runMode(browser, mode, port, dbDir, errors) {
  const base = `http://127.0.0.1:${port}`
  const processInfo = startBackend(mode, port, dbDir)
  const checks = []
  let context
  let health
  let liveReplayStarted = false
  try {
    health = await waitForBackend(base, processInfo)
    if (health.data_mode !== mode) throw new Error(`Expected ${mode} mode; health reported ${health.data_mode}`)
    context = await browser.newContext({ serviceWorkers: 'block' })
    const page = await context.newPage()
    capturePageErrors(page, mode, errors)

    for (const size of sizes) checks.push(await checkViewport(page, mode, 'login', `${base}/app/login`, size))

    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(`${base}/app/login`, { waitUntil: 'domcontentloaded' })
    await page.locator('#login-username').fill('admin')
    await page.locator('#login-password').fill(password)
    await page.locator('button[type="submit"]').click()
    await page.waitForURL('**/app/console', { timeout: 15000 })
    await page.locator('.app-shell, .console-handoff').first().waitFor({ timeout: 15000 })

    if (mode === 'live') {
      try {
        const start = page.getByRole('button', { name: 'Start Golden Path' })
        await start.waitFor({ timeout: 15000 })
        await start.click()
        await page.waitForFunction(async () => {
          const response = await fetch('/api/x/state')
          if (!response.ok) return false
          const state = await response.json()
          return Boolean(state.forecast && state.forecast.status === 'pending')
        }, null, { timeout: 30000 })
        liveReplayStarted = true
      } catch (error) {
        report.liveReplayStart = { error: error.message, url: page.url(), bodyText: await page.locator('body').innerText().catch(() => '') }
        errors.push(`live replay could not start in browser audit: ${error.message}`)
      }
    }

    await page.waitForFunction(async () => {
      const response = await fetch('/api/x/alerts?limit=1')
      if (!response.ok) return false
      const alerts = await response.json()
      return Array.isArray(alerts) && alerts.length > 0
    }, null, { timeout: 15000 }).catch(() => {})
    const alerts = await page.evaluate(async () => {
      const response = await fetch('/api/x/alerts?limit=1')
      return response.ok ? response.json() : { error: `HTTP ${response.status}` }
    })
    const alertId = alerts[0]?.event_id
    if (!alertId) errors.push(`${mode} mode did not provide an alert id for the alert-detail route (${JSON.stringify(alerts).slice(0, 180)})`)
    const incidentReply = await page.evaluate(async () => {
      const response = await fetch('/api/x/incidents?limit=1')
      return response.ok ? response.json() : { error: `HTTP ${response.status}` }
    })
    const incidentId = incidentReply.items?.[0]?.incident_id
    const reportReply = await page.evaluate(async () => {
      const response = await fetch('/api/x/reports')
      return response.ok ? response.json() : { error: `HTTP ${response.status}` }
    })
    const sessionId = reportReply.items?.[0]?.session_id
    const forecastReply = await page.evaluate(async () => {
      const response = await fetch('/api/x/forecasts?include_archived=1')
      return response.ok ? response.json() : { error: `HTTP ${response.status}` }
    })
    let forecastId = forecastReply[0]?.forecast_id
    if (!incidentId) errors.push(`${mode} mode did not provide an incident id for the incident-detail route`)
    if (!sessionId) errors.push(`${mode} mode did not provide a session id for the report-detail route`)
    let forecastLookupFailed = false
    for (const size of sizes) {
      for (const [routeName, path] of routeSpecs) {
        if (routeName === 'forecast-detail' && !forecastId) {
          await page.waitForFunction(async () => {
            const response = await fetch('/api/x/forecasts?include_archived=1')
            if (!response.ok) return false
            const forecasts = await response.json()
            return Array.isArray(forecasts) && forecasts.length > 0
          }, null, { timeout: 90000 }).catch(() => {})
          const latestForecasts = await page.evaluate(async () => {
            const response = await fetch('/api/x/forecasts?include_archived=1')
            return response.ok ? response.json() : { error: `HTTP ${response.status}` }
          })
          forecastId = latestForecasts[0]?.forecast_id
          if (!forecastId && !forecastLookupFailed) {
            forecastLookupFailed = true
            errors.push(`${mode} mode did not provide a forecast id for the forecast-detail route (${JSON.stringify(latestForecasts).slice(0, 180)})`)
          }
        }
        const route = routeName === 'mobile-alert-detail'
          ? (alertId ? `/app/mobile/alerts/${encodeURIComponent(alertId)}` : '/app/mobile/alerts')
          : routeName === 'mobile-incident-detail'
            ? (incidentId ? `/app/mobile/incidents/${encodeURIComponent(incidentId)}` : '/app/mobile/incidents')
          : routeName === 'alert-detail'
            ? (alertId ? `/app/alerts/${encodeURIComponent(alertId)}` : '/app/alerts')
            : routeName === 'incident-detail'
              ? (incidentId ? `/app/incidents/${encodeURIComponent(incidentId)}` : '/app/incidents')
              : routeName === 'report-detail'
                ? (sessionId ? `/app/reports/${encodeURIComponent(sessionId)}` : '/app/reports')
            : routeName === 'forecast-detail'
              ? (forecastId ? `/app/forecasts/${encodeURIComponent(forecastId)}` : '/app/forecasts')
            : routeName === 'host-detail'
              ? '/app/hosts/host-a'
          : path
        const check = await checkViewport(page, mode, routeName, `${base}${route}`, size)
        const failures = check.failure ? [check.failure] : []
        if (routeName === 'console' && size.width >= 1024) {
          const canvas = page.locator('canvas').first()
          if (await canvas.count()) {
            const bounds = await canvas.boundingBox()
            const png = PNG.sync.read(await canvas.screenshot())
            const colors = new Set()
            let visibleSamples = 0
            for (let i = 0; i < png.data.length; i += 4 * 97) {
              const color = `${png.data[i]},${png.data[i + 1]},${png.data[i + 2]},${png.data[i + 3]}`
              colors.add(color)
              if (png.data[i + 3] > 0 && (png.data[i] || png.data[i + 1] || png.data[i + 2])) visibleSamples += 1
            }
            check.canvas = { width: png.width, height: png.height, sampledColors: colors.size, visibleSamples, nonBlank: colors.size > 2 && visibleSamples > 8, bounds }
            if (!check.canvas.nonBlank) failures.push('WebGL canvas screenshot is blank')
          } else {
            check.canvas = { rendered: false, bodyText: await page.locator('body').innerText() }
            failures.push('3D canvas is missing at desktop width')
          }
        } else if (routeName === 'console') {
          check.canvas = { rendered: false, reason: 'console handoff is shown below 1024px' }
        }
        if (failures.length) check.failure = failures.join('; ')
        checks.push(check)
      }
    }

    if (mode === 'sample') {
      await page.setViewportSize({ width: 1440, height: 900 })
      await page.goto(`${base}/app/console`, { waitUntil: 'domcontentloaded' })
      try {
        await page.getByRole('button', { name: /Search commands/ }).waitFor({ timeout: 10000 })
        await page.keyboard.press('Control+k')
        await page.getByRole('dialog', { name: 'Command palette' }).waitFor({ timeout: 5000 })
        await page.getByRole('textbox', { name: 'Search commands' }).fill('Open mobile SOC')
        await page.keyboard.press('Enter')
        await page.waitForURL('**/app/mobile')
        report.shellInteractions = { commandPaletteNavigation: 'Ctrl+K search and Enter opened Mobile SOC' }

        await page.goto(`${base}/app/console`, { waitUntil: 'domcontentloaded' })
        await page.getByRole('button', { name: /Search commands/ }).waitFor({ timeout: 10000 })
        await page.keyboard.press('Control+k')
        await page.getByRole('option', { name: /Switch to light theme/ }).click()
        await page.waitForFunction(() => document.documentElement.dataset.theme === 'light')
        await page.reload({ waitUntil: 'domcontentloaded' })
        await page.waitForFunction(() => document.documentElement.dataset.theme === 'light')
        await page.keyboard.press('Control+k')
        await page.getByRole('option', { name: /Switch to dark theme/ }).click()
        await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark')
        report.shellInteractions.themePersistence = 'light/dark switch and persisted reload verified'

        await page.goto(`${base}/app/settings`, { waitUntil: 'domcontentloaded' })
        const density = page.getByLabel('Row spacing')
        await density.selectOption('compact')
        await page.reload({ waitUntil: 'domcontentloaded' })
        await page.waitForFunction(() => document.documentElement.dataset.density === 'compact')
        report.shellInteractions.settingsPersistence = 'compact density saved and restored after reload'

        await page.goto(`${base}/app/alerts`, { waitUntil: 'domcontentloaded' })
        await page.locator('.ops-alert-filter .ops-search-field input').fill('Brute Force')
        await page.getByRole('button', { name: 'Apply filters' }).click()
        await page.waitForFunction(() => {
          const rows = Array.from(document.querySelectorAll('.ops-table tbody tr'))
          return rows.length > 0 && rows.every((row) => row.innerText.includes('Brute Force'))
        }, null, { timeout: 10000 })
        report.shellInteractions.alertSearch = 'search for Brute Force returned only matching alerts'

        const csvDownload = page.waitForEvent('download')
        await page.getByRole('button', { name: 'Export CSV' }).click()
        report.shellInteractions.csvExport = `downloaded ${(await csvDownload).suggestedFilename()}`
        const jsonDownload = page.waitForEvent('download')
        await page.getByRole('button', { name: 'Export JSON' }).click()
        report.shellInteractions.jsonExport = `downloaded ${(await jsonDownload).suggestedFilename()}`

        await page.goto(`${base}/app/incidents/${encodeURIComponent(incidentId)}`, { waitUntil: 'domcontentloaded' })
        await page.getByLabel('Incident status').selectOption('closed')
        await page.locator('.incident-note-form textarea').fill('Reviewed during the browser rehearsal.')
        await page.getByRole('button', { name: 'Add note' }).click()
        await page.getByText('Reviewed during the browser rehearsal.').waitFor({ timeout: 10000 })
        report.incidentWorkflow = 'status changed and analyst note persisted in the incident case'

        await page.goto(`${base}/app/mobile/incidents`, { waitUntil: 'domcontentloaded' })
        await page.locator('.m-case-link').first().click()
        await page.waitForURL('**/app/mobile/incidents/**')
        await page.getByLabel('Incident case status').selectOption('contained')
        await page.locator('.m-case-note-form textarea').fill('Reviewed in the phone PWA.')
        await page.getByRole('button', { name: 'Add note' }).click()
        await page.getByText('Reviewed in the phone PWA.').waitFor({ timeout: 10000 })
        report.mobileIncidentWorkflow = 'case navigation, status update, and note verified in the phone PWA'

        await page.goto(`${base}/app/reports/${encodeURIComponent(sessionId)}`, { waitUntil: 'domcontentloaded' })
        const reportJson = page.waitForEvent('download')
        await page.getByRole('button', { name: 'Export JSON' }).click()
        report.reportJsonExport = `downloaded ${(await reportJson).suggestedFilename()}`
        const reportCsv = page.waitForEvent('download')
        await page.getByRole('button', { name: 'Export timeline CSV' }).click()
        report.reportCsvExport = `downloaded ${(await reportCsv).suggestedFilename()}`
        await page.evaluate(() => { window.print = () => { window.__printCalled = true } })
        await page.getByRole('button', { name: 'Print report' }).click()
        await page.waitForFunction(() => window.__printCalled === true)
        report.printAction = 'print stylesheet entry point invoked'

        await page.goto(`${base}/app/forecasts`, { waitUntil: 'domcontentloaded' })
        await page.locator('.forecast-ledger-table').waitFor({ timeout: 10000 })
        await page.getByLabel('Compromised host').selectOption('host-a')
        await page.getByRole('button', { name: 'Preview forecast' }).click()
        await page.locator('.what-if-result').waitFor({ timeout: 10000 })
        await page.locator('.forecast-evidence-table tbody tr').first().waitFor({ timeout: 10000 })
        report.whatIfWorkflow = 'read-only preview displayed model counts and baseline ranks for a compromised host'

        await page.goto(`${base}/app/forecasts/${encodeURIComponent(forecastId)}`, { waitUntil: 'domcontentloaded' })
        await page.locator('.forecast-detail-evidence .forecast-evidence-table').waitFor({ timeout: 10000 })
        report.forecastExplainability = 'saved candidate set, transition counts, smoothing alpha, and baseline ranks displayed'

        await page.goto(`${base}/app/analytics`, { waitUntil: 'domcontentloaded' })
        await page.getByRole('heading', { name: 'Model and baseline results' }).waitFor({ timeout: 10000 })
        await page.getByRole('heading', { name: 'Detection model report' }).waitFor({ timeout: 10000 })
        report.analyticsWorkflow = 'held-out scores, calibration curve, session tally, and offline detection report displayed'
      } catch (error) {
        report.shellInteractions = {
          error: error.message,
          url: page.url(),
          bodyText: await page.locator('body').innerText().catch(() => ''),
        }
        errors.push(`${mode} shell interaction failed: ${error.message}`)
      }
    }

    if (mode === 'live' && liveReplayStarted) {
      await page.setViewportSize({ width: 1440, height: 900 })
      await page.goto(`${base}/app/console`, { waitUntil: 'domcontentloaded' })
      await page.getByRole('button', { name: /^Contain / }).click({ timeout: 15000 })
      await page.getByRole('dialog').getByRole('button', { name: 'Confirm' }).click()
      await page.waitForFunction(async () => {
        const response = await fetch('/api/x/graph')
        const graph = await response.json()
        return graph.hosts.some((host) => host.state === 'contained')
      }, null, { timeout: 15000 })
      report.containmentFlow = 'propose and confirm completed in live replay; host state changed to contained (simulation)'
    }
  } finally {
    if (context) await context.close()
    await stopBackend(processInfo.child)
  }
  return { health, checks }
}

async function main() {
  mkdirSync(screenshots, { recursive: true })
  const dbDir = mkdtempSync(join(tmpdir(), 'precog-browser-audit-'))
  const browser = await chromium.launch({
    headless: true,
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist', '--disable-dev-shm-usage'],
  })
  const errors = []
  try {
    for (const [index, mode] of ['sample', 'live'].entries()) {
      report.modes[mode] = await runMode(browser, mode, basePort + index, dbDir, errors)
    }
  } finally {
    await browser.close()
    rmSync(dbDir, { recursive: true, force: true })
  }
  report.errors = errors
  report.expectedEvents = expectedEvents
  report.failures = Object.values(report.modes).flatMap(({ checks }) => checks.filter((check) => check.failure))
  const reportFile = join(artifactsDir, 'browser-audit-results.json')
  await import('node:fs/promises').then(({ writeFile }) => writeFile(reportFile, `${JSON.stringify(report, null, 2)}\n`))
  console.log(JSON.stringify({
    report: reportFile,
    screenshots: screenshots,
    checks: Object.fromEntries(Object.entries(report.modes).map(([mode, data]) => [mode, data.checks.length])),
    failures: report.failures,
    errors,
    containmentFlow: report.containmentFlow,
  }, null, 2))
  if (report.failures.length || errors.length) process.exitCode = 1
}

main().catch((error) => {
  console.error(error.stack || error)
  process.exitCode = 1
})

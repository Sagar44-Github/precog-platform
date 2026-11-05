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
const screenshotOverride = process.env.AUDIT_SCREENSHOT_DIR ? resolve(repoRoot, process.env.AUDIT_SCREENSHOT_DIR) : screenshots
const basePort = Number(process.env.AUDIT_PORT || 55120)
const settleMs = Number(process.env.AUDIT_SETTLE_MS || 1800)
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
  ['mobile-history', '/app/mobile/history'],
  ['incidents', '/app/incidents'],
  ['incident-detail', null],
  ['replay-studio', '/app/replay'],
  ['scenario-library', '/app/scenarios'],
  ['scenario-builder', '/app/scenarios/new'],
  ['run-history', '/app/runs'],
  ['console', '/app/console'],
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
    PRECOG_DATA_DIR: join(dbDir, `${mode}-data`),
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
  await page.waitForTimeout(settleMs)
  const state = await page.evaluate(() => ({
    width: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    hasSimulationLabel: document.body.innerText.includes('SIMULATION'),
    title: document.title,
    bodyTextPreview: document.body.innerText.slice(0, 360),
    canvasCount: document.querySelectorAll('canvas').length,
    hasConsoleHandoff: Boolean(document.querySelector('.console-handoff')),
    hasCommandTrigger: Boolean(document.querySelector('.command-trigger')),
    overflowElements: Array.from(document.querySelectorAll('body *')).map((element) => {
      const rect = element.getBoundingClientRect()
      return { tag: element.tagName.toLowerCase(), className: typeof element.className === 'string' ? element.className : '', left: Math.round(rect.left), right: Math.round(rect.right), width: Math.round(rect.width) }
    }).filter((element) => element.left < -1 || element.right > window.innerWidth + 1).slice(0, 8),
  }))
  const check = { mode, route: routeName, viewport: size.name, ...state, screenshot: `${mode}-${routeName}-${size.name}.png` }
  const failures = []
  if (state.scrollWidth > state.width) failures.push(`horizontal overflow ${state.scrollWidth}px > ${state.width}px`)
  if (!state.hasSimulationLabel) failures.push('SIMULATION label missing')
  if (routeName === 'console' && size.width < 1024 && !state.hasConsoleHandoff) failures.push('narrow console handoff is missing')
  if (routeName === 'console' && size.width >= 1024 && !state.hasCommandTrigger) failures.push('desktop command palette trigger is missing')
  if (['incidents', 'incident-detail', 'replay-studio', 'scenario-library', 'scenario-builder', 'scenario-edit', 'run-history', 'run-detail', 'run-compare'].includes(routeName)) {
    await page.addScriptTag({ path: join(repoRoot, 'web', 'node_modules', 'axe-core', 'axe.min.js') })
    const accessibility = await page.evaluate(async () => {
      const result = await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] } })
      return { violations: result.violations.map((item) => ({
        id: item.id,
        impact: item.impact,
        count: item.nodes.length,
        nodes: item.nodes.map((node) => ({ target: node.target, html: node.html, summary: node.failureSummary })),
      })) }
    })
    check.accessibility = accessibility
    if (accessibility.violations.length) failures.push(`axe found ${accessibility.violations.length} accessibility violation(s)`)
  }
  if (failures.length) check.failure = failures.join('; ')
  await page.screenshot({ path: join(screenshotOverride, check.screenshot), animations: 'disabled' })
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
  let c2Flow = null
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

    const scenarioId = `user-browser-audit-${mode}`
    await page.goto(`${base}/app/scenarios/new`, { waitUntil: 'domcontentloaded' })
    await page.locator('#scenario-builder-title').waitFor({ timeout: 10000 })
    await page.locator('.scenario-meta-fields label input').first().fill(scenarioId)
    await page.locator('.scenario-meta-fields label input').nth(1).fill('Browser audit scripted replay')
    await page.getByRole('button', { name: /Traffic/ }).click()
    await page.getByRole('button', { name: /Technique/ }).click()
    await page.getByRole('button', { name: 'Validate scenario' }).click()
    await page.getByRole('heading', { name: 'Scenario valid' }).waitFor({ timeout: 10000 })
    await page.getByRole('button', { name: 'Dry-run estimate' }).click()
    await page.getByRole('heading', { name: 'Dry-run projection' }).waitFor({ timeout: 10000 })
    await page.getByRole('button', { name: 'Save scenario' }).click()
    await page.waitForURL('**/app/scenarios')

    async function postJson(path, payload) {
      const result = await page.evaluate(async ({ path, payload }) => {
        const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Precog-Request': '1' }, body: JSON.stringify(payload) })
        const body = await response.json().catch(() => ({}))
        const replay = response.status === 409 ? await fetch('/api/x/replay/studio/status').then((item) => item.json()).catch(() => null) : null
        return { status: response.status, body, replay }
      }, { path, payload })
      if (result.status < 200 || result.status >= 300) throw new Error(`${path} returned ${result.status}: ${JSON.stringify({ body: result.body, replay: result.replay })}`)
      return result.body
    }
    async function startAndFinish(withControls) {
      const started = await postJson('/api/x/replay/studio/start', { scenario_id: scenarioId, speed: 8 })
      const runId = started.active_run?.run_id
      if (!runId) throw new Error('Replay studio did not return an active run id.')
      if (withControls) {
        await postJson('/api/x/replay/breakpoints', { sequences: [2] })
        await postJson('/api/x/replay/step', {})
        await postJson('/api/x/replay/step', {})
        await postJson('/api/x/replay/breakpoints', { sequences: [] })
        await postJson('/api/x/replay/step', {})
      } else {
        await postJson('/api/x/replay/resume', {})
      }
      await page.waitForFunction(async () => {
        const response = await fetch(`/api/x/replay/studio/status?fresh=${Date.now()}`, { cache: 'no-store' })
        if (!response.ok) return false
        const value = await response.json()
        return value.status?.state === 'finished' && value.active_run === null
      }, null, { timeout: 15000 })
      await page.waitForFunction(async (id) => {
        const response = await fetch(`/api/x/runs?fresh=${Date.now()}`, { cache: 'no-store' })
        const runs = response.ok ? await response.json() : []
        return runs.some((run) => run.run_id === id)
      }, runId, { timeout: 10000 })
      return runId
    }
    const firstRunId = await startAndFinish(true)
    const secondRunId = firstRunId
    const comparisonResponse = await page.evaluate(async ({ a, b }) => {
      const response = await fetch(`/api/x/runs/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`)
      return { status: response.status, body: await response.json() }
    }, { a: firstRunId, b: secondRunId })
    if (comparisonResponse.status !== 200) throw new Error(`Run comparison returned ${comparisonResponse.status} for ${firstRunId} and ${secondRunId}: ${JSON.stringify(comparisonResponse.body)}`)
    c2Flow = { result: 'built, validated, dry-run, saved and stepped through a scripted scenario, then opened its report comparison', scenarioId, runIds: [firstRunId, secondRunId], comparisonIdentical: comparisonResponse.body.identical }
    if (!comparisonResponse.body.identical) errors.push(`${mode} replayed scenario did not compare as identical`)
    const c2Routes = [
      ['scenario-edit', `/app/scenarios/${encodeURIComponent(scenarioId)}/edit`],
      ['run-detail', `/app/runs/${encodeURIComponent(firstRunId)}`],
      ['run-compare', `/app/runs/compare?a=${encodeURIComponent(firstRunId)}&b=${encodeURIComponent(secondRunId)}`],
    ]

    if (mode === 'live') {
      try {
        await page.goto(`${base}/app/console`, { waitUntil: 'domcontentloaded' })
        await page.locator('.c-app').waitFor({ timeout: 8000 })
        await postJson('/api/x/replay/start', { scenario_id: 'golden-path', speed: 8 })
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

    const alerts = await page.evaluate(async () => {
      const response = await fetch('/api/x/alerts?limit=1')
      return response.ok ? response.json() : []
    })
    const alertId = alerts[0]?.event_id
    if (!alertId) errors.push(`${mode} mode did not provide an alert id for the alert-detail route`)
    const incidentId = await page.evaluate(async () => {
      const response = await fetch('/api/x/incidents?limit=1')
      const result = response.ok ? await response.json() : null
      return result?.items?.[0]?.incident_id || null
    })
    for (const size of sizes) {
      for (const [routeName, path] of [...routeSpecs, ...c2Routes]) {
        const route = routeName === 'mobile-alert-detail'
          ? (alertId ? `/app/mobile/alerts/${encodeURIComponent(alertId)}` : '/app/mobile/alerts')
          : routeName === 'incident-detail'
            ? (incidentId ? `/app/incidents/${encodeURIComponent(incidentId)}` : '/app/incidents')
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
      if (incidentId) {
        await page.setViewportSize({ width: 1440, height: 900 })
        await page.goto(`${base}/app/incidents/${encodeURIComponent(incidentId)}`, { waitUntil: 'domcontentloaded' })
        const note = `Browser audit note ${randomBytes(4).toString('hex')} · scripted simulation`
        await page.locator('#incident-note').fill(note)
        await page.getByRole('button', { name: 'Add note' }).click()
        await page.locator('.incident-notes-list').getByText(note, { exact: true }).waitFor({ timeout: 10000 })
        await page.getByText(note, { exact: true }).last().waitFor({ timeout: 10000 })
        report.incidentNoteFlow = 'note submitted on the detail route and shown in the refreshed timeline'
      } else {
        errors.push('sample mode did not provide an incident id for the note flow')
      }
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
  return { health, checks, c2Flow }
}

async function main() {
  mkdirSync(screenshots, { recursive: true })
  mkdirSync(screenshotOverride, { recursive: true })
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
    screenshots: screenshotOverride,
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

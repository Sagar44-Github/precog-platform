import { chromium } from 'playwright'
import { PNG } from 'pngjs'
import { gzipSync } from 'node:zlib'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { basename, join, resolve } from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const webRoot = resolve(fileURLToPath(new URL('..', import.meta.url)))
const repoRoot = resolve(webRoot, '..')
const output = join(repoRoot, 'docs', 'audit', 'screenshots', 'landing', 'interactive')
const distAssets = join(webRoot, 'dist', 'assets')
const origin = process.env.LANDING_AUDIT_ORIGIN || 'http://127.0.0.1:4173'
const sizes = [
  { name: '390x844', width: 390, height: 844 },
  { name: '820x1180', width: 820, height: 1180 },
  { name: '1440x900', width: 1440, height: 900 },
]
const errors = []
const report = { browser: 'Playwright Chromium with SwiftShader', viewports: [], interactions: {}, errors }

function startPreview() {
  const vite = join(webRoot, 'node_modules', 'vite', 'bin', 'vite.js')
  return spawn(process.execPath, [vite, 'preview', '--host', '127.0.0.1', '--port', '4173', '--strictPort'], { cwd: webRoot, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true })
}

async function waitForPreview(child) {
  const deadline = Date.now() + 30000
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error('Vite preview exited before it became ready.')
    try { if ((await fetch(`${origin}/app/`)).ok) return } catch {}
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
  throw new Error(`Vite preview was not ready at ${origin}/app/.`)
}

async function stopPreview(child) {
  if (child.exitCode !== null) return
  child.kill()
  await Promise.race([new Promise((done) => child.once('exit', done)), new Promise((done) => setTimeout(done, 3000))])
}

function recordErrors(page, name) {
  page.on('pageerror', (error) => errors.push(`${name} page: ${error.message}`))
  page.on('console', (message) => { if (message.type() === 'error') errors.push(`${name} console: ${message.text()}`) })
  page.on('requestfailed', (request) => errors.push(`${name} request failed: ${request.url()} (${request.failure()?.errorText || 'unknown'})`))
  page.on('response', (response) => { if (response.status() >= 400) errors.push(`${name} HTTP ${response.status()}: ${response.url()}`) })
}

function canvasSummary(bytes) {
  const image = PNG.sync.read(bytes)
  const colors = new Set()
  let lit = 0
  for (let i = 0; i < image.data.length; i += 4 * 29) {
    const rgb = `${image.data[i]},${image.data[i + 1]},${image.data[i + 2]}`
    colors.add(rgb)
    if (image.data[i] + image.data[i + 1] + image.data[i + 2] > 18) lit += 1
  }
  return { width: image.width, height: image.height, sampledColors: colors.size, litSamples: lit, nonBlank: colors.size > 12 && lit > 18 }
}

function imageDifference(left, right) {
  const a = PNG.sync.read(left)
  const b = PNG.sync.read(right)
  if (a.width !== b.width || a.height !== b.height) return 1
  let changed = 0
  let samples = 0
  for (let i = 0; i < a.data.length; i += 4 * 37) {
    if (Math.abs(a.data[i] - b.data[i]) > 12 || Math.abs(a.data[i + 1] - b.data[i + 1]) > 12 || Math.abs(a.data[i + 2] - b.data[i + 2]) > 12) changed += 1
    samples += 1
  }
  return samples ? changed / samples : 0
}

async function addMockAuth(page) {
  await page.route('**/api/x/me', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{"username":null}' }))
}

async function run() {
  mkdirSync(output, { recursive: true })
  const preview = startPreview()
  let browser
  try {
    await waitForPreview(preview)
    browser = await chromium.launch({ headless: true, args: ['--enable-webgl', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] })
    for (const size of sizes) {
      const context = await browser.newContext({ viewport: { width: size.width, height: size.height } })
      await context.addInitScript(() => localStorage.setItem('precog-landing-mode', 'full'))
      const page = await context.newPage()
      recordErrors(page, size.name)
      await addMockAuth(page)
      await page.goto(`${origin}/app/`, { waitUntil: 'domcontentloaded' })
      await page.getByRole('heading', { level: 1 }).waitFor()
      await page.locator('.landing-canvas').waitFor({ timeout: 30000 })
      await page.waitForTimeout(700)
      const result = {
        name: size.name,
        horizontalOverflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
        firstContentfulPaintMs: await page.evaluate(() => Math.round(performance.getEntriesByName('first-contentful-paint')[0]?.startTime || 0)),
        cumulativeLayoutShift: await page.evaluate(() => performance.getEntriesByType('layout-shift').reduce((sum, entry) => sum + (entry.hadRecentInput ? 0 : entry.value), 0)),
        steps: [],
      }
      if (result.horizontalOverflow) errors.push(`${size.name}: horizontal overflow.`)
      if (result.cumulativeLayoutShift > 0.1) errors.push(`${size.name}: cumulative layout shift ${result.cumulativeLayoutShift.toFixed(3)}.`)

      if (size.name === '1440x900') {
        const jsResources = await page.evaluate(() => performance.getEntriesByType('resource').map(({ name }) => name).filter((name) => name.includes('/assets/') && name.endsWith('.js')))
        const lazy3d = [...new Set(jsResources.map((url) => basename(new URL(url).pathname)).filter((name) => /LandingStage|three\.module|OrbitControls/.test(name)))]
        const pre3d = [...new Set(jsResources.map((url) => basename(new URL(url).pathname)).filter((name) => !lazy3d.includes(name)))]
        const pre3dGzip = pre3d.reduce((sum, name) => sum + gzipSync(readFileSync(join(distAssets, name))).length, 0)
        const lazy3dGzip = lazy3d.reduce((sum, name) => sum + gzipSync(readFileSync(join(distAssets, name))).length, 0)
        report.performance = { pre3dFiles: pre3d, pre3dGzipBytes: pre3dGzip, pre3dGzipKB: Number((pre3dGzip / 1024).toFixed(1)), lazy3dFiles: lazy3d, lazy3dGzipBytes: lazy3dGzip, lazy3dGzipKB: Number((lazy3dGzip / 1024).toFixed(1)) }
        if (pre3dGzip > 120 * 1024) errors.push(`Landing scripts before the 3D chunk exceed 120 KB gzip (${report.performance.pre3dGzipKB} KB).`)
      }

      let previous
      for (let step = 0; step < 5; step += 1) {
        await page.locator('.landing-step-list button').nth(step).click()
        await page.waitForTimeout(200)
        const canvas = await page.locator('.landing-canvas').screenshot({ animations: 'disabled' })
        const summary = canvasSummary(canvas)
        const screenshot = `${size.name}-step-${String(step + 1).padStart(2, '0')}.png`
        await page.locator('.landing-stage-wrap').screenshot({ path: join(output, screenshot), animations: 'disabled' })
        if (!summary.nonBlank) errors.push(`${size.name} step ${step + 1}: 3D canvas is blank.`)
        if (previous && imageDifference(previous, canvas) < 0.001) errors.push(`${size.name} step ${step + 1}: the 3D scene did not respond to the new replay step.`)
        previous = canvas
        result.steps.push({ label: await page.locator('.landing-step-list button').nth(step).innerText(), canvas: summary, screenshot })
      }
      result.geometryCount = await page.locator('.landing-canvas').getAttribute('data-geometry-count')
      result.textureCount = await page.locator('.landing-canvas').getAttribute('data-texture-count')
      result.quality = await page.locator('.landing-canvas').getAttribute('data-quality')
      const max = await page.evaluate(() => document.documentElement.scrollHeight - innerHeight)
      for (let cycle = 0; cycle < 50; cycle += 1) {
        await page.evaluate((top) => window.scrollTo({ top, behavior: 'instant' }), cycle % 2 ? 0 : max)
        await page.waitForTimeout(15)
      }
      await page.waitForTimeout(300)
      result.endGeometryCount = await page.locator('.landing-canvas').getAttribute('data-geometry-count')
      result.endTextureCount = await page.locator('.landing-canvas').getAttribute('data-texture-count')
      if (result.geometryCount !== result.endGeometryCount) errors.push(`${size.name}: geometry count changed after scrolling.`)
      if (result.textureCount !== result.endTextureCount) errors.push(`${size.name}: texture count changed after scrolling.`)
      await page.locator('.landing-step-list button').nth(3).click()
      await page.waitForTimeout(250)
      await page.screenshot({ path: join(output, `${size.name}-full-page.png`), fullPage: true, animations: 'disabled' })
      report.viewports.push(result)
      await context.close()
    }

    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    await context.addInitScript(() => localStorage.setItem('precog-landing-mode', 'full'))
    const page = await context.newPage()
    recordErrors(page, 'interaction')
    await addMockAuth(page)
    await page.goto(`${origin}/app/`, { waitUntil: 'domcontentloaded' })
    await page.getByRole('heading', { level: 1 }).waitFor()
    await page.keyboard.press('Tab')
    report.interactions.skipLinkFocused = await page.evaluate(() => document.activeElement?.textContent.includes('Skip to content'))
    const canvas = page.locator('.landing-canvas')
    const bounds = await canvas.boundingBox()
    await canvas.click({ position: { x: bounds.width * 0.232, y: bounds.height * 0.35 } })
    report.interactions.pointerHostSelection = await page.locator('.landing-stage-caption').innerText()
    const beforeOrbit = await canvas.screenshot()
    await page.mouse.move(bounds.x + bounds.width * 0.55, bounds.y + bounds.height * 0.48)
    await page.mouse.down()
    await page.mouse.move(bounds.x + bounds.width * 0.75, bounds.y + bounds.height * 0.34, { steps: 8 })
    await page.mouse.up()
    await page.waitForTimeout(250)
    report.interactions.orbitSceneChange = imageDifference(beforeOrbit, await canvas.screenshot())
    if (report.interactions.orbitSceneChange < 0.001) errors.push('Dragging the 3D scene did not orbit the topology.')
    await page.locator('#landing-host-select').selectOption('file-server')
    report.interactions.hostSelection = await page.locator('.landing-stage-caption').innerText()
    await page.locator('.landing-step-list button').nth(4).click()
    report.interactions.containmentSimulation = await page.getByText(/was blocked in this simulation/).isVisible()
    await page.getByRole('button', { name: 'Reduced version' }).click()
    report.interactions.liteFallback = await page.locator('.landing-lite-diagram').isVisible()
    await page.screenshot({ path: join(output, '1440x900-reduced-version.png'), fullPage: true, animations: 'disabled' })
    await page.getByRole('button', { name: '3D version' }).click()
    report.interactions.manual3DRestore = await page.locator('.landing-canvas').count() === 1
    await page.getByRole('button', { name: 'Open the SOC console' }).click()
    await page.waitForURL('**/app/login', { timeout: 5000 })
    report.interactions.enterDestination = new URL(page.url()).pathname
    await context.close()

    const reducedContext = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' })
    const reducedPage = await reducedContext.newPage()
    recordErrors(reducedPage, 'reduced-motion')
    await reducedPage.route('**/api/x/me', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{"username":null}' }))
    await reducedPage.goto(`${origin}/app/`, { waitUntil: 'domcontentloaded' })
    await reducedPage.locator('.landing-lite-diagram').waitFor()
    report.interactions.reducedMotionUsesDesignedFallback = await reducedPage.locator('.landing-lite-diagram').isVisible()
    await reducedPage.screenshot({ path: join(output, '390x844-reduced-motion.png'), fullPage: true, animations: 'disabled' })
    await reducedContext.close()

    writeFileSync(join(repoRoot, 'docs', 'audit', 'landing-browser-report.json'), `${JSON.stringify(report, null, 2)}\n`)
    console.log(JSON.stringify({ performance: report.performance, viewports: report.viewports.map(({ name, horizontalOverflow, cumulativeLayoutShift, geometryCount, endGeometryCount, textureCount, endTextureCount, quality }) => ({ name, horizontalOverflow, cumulativeLayoutShift, geometryCount, endGeometryCount, textureCount, endTextureCount, quality })), interactions: report.interactions, errors }, null, 2))
    if (errors.length) process.exitCode = 1
  } finally {
    await browser?.close()
    await stopPreview(preview)
  }
}

await run()

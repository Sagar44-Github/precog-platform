import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)))
const output = join(root, 'docs', 'audit', 'screenshots', 'phase-d8')
const port = 4175
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
  await page.route('**/api/x/**', async (route) => {
    const url = new URL(route.request().url())
    let body = {}
    if (url.pathname === '/api/x/me') body = { username: 'd8-reviewer', role: 'admin' }
    else if (url.pathname === '/api/x/workspaces/active') body = { id: 'demo-6' }
    else if (url.pathname === '/api/x/workspaces/upload/preview') body = {
      job_id: 'upload-0123456789abcdef0123456789abcdef', filename: 'flows.csv', state: 'preview', bytes_received: 44,
      size_limit: 52428800, progress: 0.1, message: 'Format inspected. Confirm the licence acknowledgement and mapping before building.',
      preview: { format: 'csv', columns: ['timestamp', 'src', 'dst', 'label'], sample_rows: [{ timestamp: '0', src: '10.0.0.1', dst: '10.0.0.2', label: 'benign' }], row_estimate: 1, warnings: [] },
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()) })
  mkdirSync(output, { recursive: true })
  const dimensions = [[390, 844], [820, 1180], [1440, 900]]
  const widths = []
  for (const [width, height] of dimensions) {
    await page.setViewportSize({ width, height })
    await page.goto(`${base}/app/datasets/upload`, { waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: 'Upload a dataset' }).waitFor()
    widths.push({ width, scrollWidth: await page.evaluate(() => document.documentElement.scrollWidth) })
    await page.screenshot({ path: join(output, `upload-${width}x${height}.png`), fullPage: true })
  }
  await page.getByLabel('Dataset file').setInputFiles({ name: 'flows.csv', mimeType: 'text/csv', buffer: Buffer.from('timestamp,src,dst,label\n0,10.0.0.1,10.0.0.2,benign\n') })
  await page.getByText(/I have permission to process this file\./).first().click()
  await page.getByRole('button', { name: 'Inspect file' }).click()
  await page.getByRole('heading', { name: 'Review format and map columns' }).waitFor()
  await page.screenshot({ path: join(output, 'upload-preview-1440x900.png'), fullPage: true })
  if (errors.length) throw new Error(`Browser errors: ${JSON.stringify(errors)}`)
  if (widths.some((item) => item.width !== item.scrollWidth)) throw new Error(`Horizontal overflow: ${JSON.stringify(widths)}`)
  console.log(JSON.stringify({ widths, screenshots: 4, previewFlow: 'PASS', browserErrors: errors.length }, null, 2))
} finally {
  if (browser) await browser.close()
  server.kill()
}

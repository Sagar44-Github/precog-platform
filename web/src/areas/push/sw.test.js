import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { fileURLToPath } from 'node:url'

// Runs the real service-worker file with a fake "self", so the notification code is tested without a browser.
function loadWorker() {
  const handlers = {}
  const shown = []
  const opened = []
  const self = {
    addEventListener: (type, fn) => { handlers[type] = fn },
    registration: { showNotification: (title, options) => { shown.push({ title, options }); return Promise.resolve() } },
    clients: { matchAll: () => Promise.resolve([]), openWindow: (url) => { opened.push(url); return Promise.resolve() } },
  }
  const file = fileURLToPath(new URL('../../../public/push/push-sw.js', import.meta.url))
  vm.runInNewContext(readFileSync(file, 'utf8'), { self })
  return { handlers, shown, opened }
}

const pushEvent = (payload) => { const waits = []; return { data: { json: () => payload, text: () => '' }, waitUntil: (p) => waits.push(p), waits } }

test('a data message becomes a notification with title, body, tag and link', async () => {
  const { handlers, shown } = loadWorker()
  const event = pushEvent({ data: { title: 'High alert: Workstation A', body: 'Workstation A sent a packet.', event_id: 'evt-000001', url: '/app/mobile/alerts/evt-000001' } })
  handlers.push(event)
  await Promise.all(event.waits)
  assert.equal(shown.length, 1)
  assert.equal(shown[0].title, 'High alert: Workstation A')
  assert.equal(shown[0].options.body, 'Workstation A sent a packet.')
  assert.equal(shown[0].options.tag, 'evt-000001')
  assert.equal(shown[0].options.data.url, '/app/mobile/alerts/evt-000001')
})

test('a message with missing parts still shows something sensible', async () => {
  const { handlers, shown } = loadWorker()
  const event = pushEvent({})
  handlers.push(event)
  await Promise.all(event.waits)
  assert.equal(shown[0].title, 'Precog SOC')
  assert.equal(shown[0].options.data.url, '/app/mobile/')
})

test('an unreadable message does not crash the worker', async () => {
  const { handlers, shown } = loadWorker()
  const event = { data: { json: () => { throw new Error('bad') }, text: () => 'plain words' }, waitUntil: (p) => event.waits.push(p), waits: [] }
  handlers.push(event)
  await Promise.all(event.waits)
  assert.equal(shown[0].options.body, 'plain words')
})

test('tapping the notification closes it and opens the alert', async () => {
  const { handlers, opened } = loadWorker()
  let closed = false
  const event = { notification: { close: () => { closed = true }, data: { url: '/app/mobile/alerts/evt-000001' } }, waitUntil: (p) => event.waits.push(p), waits: [] }
  handlers.notificationclick(event)
  await Promise.all(event.waits)
  assert.equal(closed, true)
  assert.deepEqual(opened, ['/app/mobile/alerts/evt-000001'])
})

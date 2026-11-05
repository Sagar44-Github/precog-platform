// Shows push notifications when the app is closed (owner: VIZ). The lead's service worker (public/sw.js) loads this file.
// The backend sends "data only" messages: { title, body, event_id, url }. Tapping a notification opens that alert.

function buildNotification(payload) {
  const data = (payload && payload.data) || payload || {}
  return {
    title: data.title || 'Precog SOC',
    options: { body: data.body || '', tag: data.event_id || 'precog-alert', data: { url: data.url || '/app/alerts' }, requireInteraction: true },
  }
}

self.addEventListener('push', (event) => {
  let payload = {}
  try { payload = event.data ? event.data.json() : {} } catch (e) { payload = { data: { body: event.data ? event.data.text() : '' } } }
  const { title, options } = buildNotification(payload)
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/app/alerts'
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
    for (const client of windows) {
      if (client.url.includes('/app/') && 'focus' in client) { if ('navigate' in client) client.navigate(url); return client.focus() }
    }
    return self.clients.openWindow(url)
  }))
})

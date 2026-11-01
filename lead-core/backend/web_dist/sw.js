// Service worker for the Precog web app (owner: LEAD-CORE).
// It makes the app installable. It does not cache API calls, so data is never out of date.
// VIZ's push-notification code lives in /app/push/push-sw.js and is loaded below.
try {
  importScripts('/app/push/push-sw.js')
} catch (error) {
  // The push file is optional. The app works without it.
}

self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

// A fetch handler must exist for the browser to offer "install". We simply let every request go to the network.
self.addEventListener('fetch', () => {})

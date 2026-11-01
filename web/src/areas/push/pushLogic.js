// The decisions of the push-notification code as plain functions (owner: VIZ), so they can be tested without a browser.

/** The status the rest of the app sees: not_built | unsupported | prompt | enabled | denied. */
export function decidePushStatus({ supported, configured, permission, registered }) {
  if (!supported || !configured) return 'unsupported'
  if (permission === 'denied') return 'denied'
  if (permission === 'granted' && registered) return 'enabled'
  return 'prompt'
}

export function isPushSupported(win) {
  return Boolean(win && 'Notification' in win && win.navigator && 'serviceWorker' in win.navigator && 'PushManager' in win)
}

/** Reads the (public) Firebase web settings from Vite's environment. Returns null if any is missing. */
export function readFirebaseConfig(env) {
  const config = { apiKey: env.VITE_FIREBASE_API_KEY, authDomain: env.VITE_FIREBASE_AUTH_DOMAIN, projectId: env.VITE_FIREBASE_PROJECT_ID,
                   messagingSenderId: env.VITE_FIREBASE_MESSAGING_SENDER_ID, appId: env.VITE_FIREBASE_APP_ID }
  const vapidKey = env.VITE_FIREBASE_VAPID_KEY
  if (!vapidKey || Object.values(config).some((v) => !v)) return null
  return { config, vapidKey }
}

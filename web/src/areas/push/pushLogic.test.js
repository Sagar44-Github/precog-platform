import test from 'node:test'
import assert from 'node:assert/strict'
import { decidePushStatus, isPushSupported, readFirebaseConfig } from './pushLogic.js'

const full = { VITE_FIREBASE_API_KEY: 'k', VITE_FIREBASE_AUTH_DOMAIN: 'd', VITE_FIREBASE_PROJECT_ID: 'p', VITE_FIREBASE_MESSAGING_SENDER_ID: 's', VITE_FIREBASE_APP_ID: 'a', VITE_FIREBASE_VAPID_KEY: 'v' }

test('status: unsupported without browser support or settings', () => {
  assert.equal(decidePushStatus({ supported: false, configured: true, permission: 'default', registered: false }), 'unsupported')
  assert.equal(decidePushStatus({ supported: true, configured: false, permission: 'default', registered: false }), 'unsupported')
})

test('status: prompt, enabled and denied', () => {
  assert.equal(decidePushStatus({ supported: true, configured: true, permission: 'default', registered: false }), 'prompt')
  assert.equal(decidePushStatus({ supported: true, configured: true, permission: 'granted', registered: false }), 'prompt')
  assert.equal(decidePushStatus({ supported: true, configured: true, permission: 'granted', registered: true }), 'enabled')
  assert.equal(decidePushStatus({ supported: true, configured: true, permission: 'denied', registered: true }), 'denied')
})

test('browser support needs notifications, a service worker and the push manager', () => {
  assert.equal(isPushSupported({ Notification: {}, PushManager: {}, navigator: { serviceWorker: {} } }), true)
  assert.equal(isPushSupported({ Notification: {}, navigator: { serviceWorker: {} } }), false)
  assert.equal(isPushSupported(null), false)
})

test('the Firebase settings are read from the environment, or null when anything is missing', () => {
  assert.deepEqual(readFirebaseConfig(full), { config: { apiKey: 'k', authDomain: 'd', projectId: 'p', messagingSenderId: 's', appId: 'a' }, vapidKey: 'v' })
  assert.equal(readFirebaseConfig({ ...full, VITE_FIREBASE_VAPID_KEY: '' }), null)
  assert.equal(readFirebaseConfig({}), null)
})

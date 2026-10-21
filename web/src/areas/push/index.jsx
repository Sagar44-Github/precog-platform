import { useCallback, useEffect, useState } from 'react'
import { api } from '../../shared/api.js'
import { decidePushStatus, isPushSupported, readFirebaseConfig } from './pushLogic.js'

// Push notifications in the browser (owner: VIZ). GRAPH's screens call usePushRegistration() and read { status, enable }.
//   status: 'unsupported' | 'prompt' | 'enabled' | 'denied'   ('not_built' was the placeholder's value)
// Firebase is loaded only when the person turns alerts on, so it never slows the first screen.

const KEY = 'precog-push-registered'
const remembered = () => { try { return window.localStorage.getItem(KEY) === 'yes' } catch (e) { return false } }
const remember = () => { try { window.localStorage.setItem(KEY, 'yes') } catch (e) { /* storage may be blocked */ } }

export function usePushRegistration() {
  const firebase = readFirebaseConfig(import.meta.env || {})
  const [status, setStatus] = useState('unsupported')

  useEffect(() => {
    setStatus(decidePushStatus({ supported: isPushSupported(window), configured: Boolean(firebase),
                                permission: typeof Notification === 'undefined' ? 'default' : Notification.permission, registered: remembered() }))
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  const enable = useCallback(async () => {
    if (!firebase) return
    try {
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') { setStatus(decidePushStatus({ supported: true, configured: true, permission, registered: false })); return }
      const [{ initializeApp }, { getMessaging, getToken }] = await Promise.all([import('firebase/app'), import('firebase/messaging')])
      const registration = await navigator.serviceWorker.ready
      const token = await getToken(getMessaging(initializeApp(firebase.config)), { vapidKey: firebase.vapidKey, serviceWorkerRegistration: registration })
      await api.registerPush(token)
      remember()
      setStatus('enabled')
    } catch (error) {
      setStatus('prompt')   // something failed: let the person try again
    }
  }, [firebase])

  return { status, enable }
}

import { createContext, useContext, useEffect, useMemo, useState } from 'react'

const STORAGE_KEY = 'precog-ui-preferences'
const DEFAULTS = { density: 'comfortable', defaultAlertSeverity: '' }
const UiPreferencesContext = createContext(null)

function readSaved() {
  if (typeof window === 'undefined') return DEFAULTS
  try {
    const value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{}')
    return {
      density: value.density === 'compact' ? 'compact' : DEFAULTS.density,
      defaultAlertSeverity: ['', 'HIGH', 'MEDIUM', 'LOW', 'NORMAL'].includes(value.defaultAlertSeverity) ? value.defaultAlertSeverity : '',
    }
  } catch {
    return DEFAULTS
  }
}

export function UiPreferencesProvider({ children }) {
  const [preferences, setPreferences] = useState(readSaved)
  useEffect(() => {
    document.documentElement.dataset.density = preferences.density
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences))
  }, [preferences])
  const value = useMemo(() => ({
    preferences,
    setPreference(name, next) {
      setPreferences((current) => ({ ...current, [name]: next }))
    },
  }), [preferences])
  return <UiPreferencesContext.Provider value={value}>{children}</UiPreferencesContext.Provider>
}

export function useUiPreferences() {
  const value = useContext(UiPreferencesContext)
  if (!value) throw new Error('useUiPreferences must be used inside UiPreferencesProvider')
  return value
}

export { DEFAULTS as DEFAULT_UI_PREFERENCES, STORAGE_KEY as UI_PREFERENCES_STORAGE_KEY }

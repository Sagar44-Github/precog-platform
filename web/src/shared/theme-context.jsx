import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState } from 'react'
import { Icon } from './icons.jsx'

const ThemeContext = createContext({ theme: 'dark', toggleTheme: () => {} })
const STORAGE_KEY = 'precog-color-theme'
const useBrowserLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect

function savedTheme() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(savedTheme)
  const toggleTheme = useCallback(() => setTheme((value) => value === 'dark' ? 'light' : 'dark'), [])

  useBrowserLayoutEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    const logoPath = `/app/brand/project-logo-${theme}.svg`
    document.querySelectorAll('[data-theme-icon]').forEach((element) => { element.href = logoPath })
    const themeColor = document.querySelector('meta[name="theme-color"]')
    if (themeColor) themeColor.content = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()
    try { window.localStorage.setItem(STORAGE_KEY, theme) } catch { /* Theme still works without storage. */ }
  }, [theme])

  const value = useMemo(() => ({ theme, toggleTheme }), [theme, toggleTheme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export const useTheme = () => useContext(ThemeContext)

export function ThemeToggle({ className = '' }) {
  const { theme, toggleTheme } = useTheme()
  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button
      type="button"
      className={`theme-toggle ${className}`.trim()}
      onClick={toggleTheme}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
    >
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={18} />
      <span>{theme === 'dark' ? 'Light' : 'Dark'} theme</span>
    </button>
  )
}

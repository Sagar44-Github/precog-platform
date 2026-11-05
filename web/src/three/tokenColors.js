import { Color } from 'three'

const TOKEN_NAMES = {
  background: '--bg',
  text: '--text',
  muted: '--text-muted',
  normal: '--state-normal',
  compromised: '--state-compromised',
  contained: '--state-contained',
  forecast: '--forecast',
  border: '--border',
  surface: '--surface-sunken',
}

export function readThreeTokenColors(getVariable) {
  return Object.fromEntries(Object.entries(TOKEN_NAMES).map(([key, token]) => {
    const value = String(getVariable(token) || '').trim()
    if (!value) throw new Error(`Required design token ${token} is missing.`)
    return [key, new Color().setStyle(value)]
  }))
}

export function readBrowserTokenStyles() {
  if (typeof document === 'undefined') throw new Error('Design tokens can only be read in a browser.')
  const probe = document.createElement('span')
  probe.setAttribute('aria-hidden', 'true')
  probe.style.position = 'absolute'
  probe.style.visibility = 'hidden'
  document.documentElement.append(probe)
  try {
    return Object.fromEntries(Object.entries(TOKEN_NAMES).map(([key, token]) => {
      probe.style.color = `var(${token})`
      const value = getComputedStyle(probe).color
      if (!value || value === 'transparent') throw new Error(`Required design token ${token} is missing.`)
      return [key, value]
    }))
  } finally {
    probe.remove()
  }
}

export const readBrowserTokenColors = () => {
  const styles = readBrowserTokenStyles()
  return readThreeTokenColors((token) => {
    const entry = Object.entries(TOKEN_NAMES).find(([, name]) => name === token)
    return entry ? styles[entry[0]] : ''
  })
}

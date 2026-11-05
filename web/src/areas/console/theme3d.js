// The 3D scene needs real colour values, but the code may not contain colour codes. So the colours are read from the
// CSS variables in theme.css while the app runs. getVar is injectable so this can be tested.

export const SCENE_VARS = {
  bg: '--bg', text: '--text', muted: '--text-muted', normal: '--state-normal', compromised: '--state-compromised',
  contained: '--state-contained', forecast: '--forecast', accent: '--accent', high: '--severity-high', medium: '--severity-medium', low: '--severity-low',
}

export function readSceneColors(getVar) {
  const colors = {}
  for (const [name, variable] of Object.entries(SCENE_VARS)) colors[name] = (getVar(variable) || '').trim() || 'white'
  return colors
}

export function browserVar(name, documentRef = globalThis.document, getStyle = globalThis.getComputedStyle) {
  if (!documentRef?.documentElement || typeof getStyle !== 'function') return ''
  const value = getStyle(documentRef.documentElement).getPropertyValue(name).trim()
  if (!value) return ''
  const context = documentRef.createElement?.('canvas')?.getContext?.('2d')
  if (!context) return value
  context.fillStyle = value
  return context.fillStyle || value
}

export const prefersReducedMotion = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

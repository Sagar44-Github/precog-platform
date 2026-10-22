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

export const browserVar = (name) => (typeof document === 'undefined' ? '' : getComputedStyle(document.documentElement).getPropertyValue(name))

export const prefersReducedMotion = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

export const CAMERA_PRESETS = Object.freeze({
  isometric: { label: 'Isometric', position: { x: 0, y: 110, z: 300 } },
  top: { label: 'Top', position: { x: 0, y: 390, z: 0.01 } },
  side: { label: 'Side', position: { x: 390, y: 30, z: 0 } },
})

export function supportsWebGL(documentRef = globalThis.document) {
  if (!documentRef?.createElement) return false
  try {
    const canvas = documentRef.createElement('canvas')
    const context = canvas.getContext('webgl2') || canvas.getContext('webgl')
    if (!context) return false
    context.getExtension?.('WEBGL_lose_context')?.loseContext?.()
    return true
  } catch {
    return false
  }
}

export function autoViewMode({ width, reducedMotion, webgl }) {
  return width < 1024 || reducedMotion || !webgl ? 'lite' : '3d'
}

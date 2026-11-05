export const QUALITY = {
  high: { name: 'high', maxDpr: 1.75, maxHostSegments: 20, shadows: true, frameBudget: 16.7 },
  balanced: { name: 'balanced', maxDpr: 1.35, maxHostSegments: 14, shadows: false, frameBudget: 25 },
  lite: { name: 'lite', maxDpr: 1, maxHostSegments: 10, shadows: false, frameBudget: 33.3 },
}
const ORDER = ['high', 'balanced', 'lite']

export function initialQuality({ phone = false, lowPower = false, saveData = false, reducedMotion = false, renderer = '' } = {}) {
  if (phone || lowPower || saveData || reducedMotion || /swiftshader|software/i.test(renderer)) return 'lite'
  return 'high'
}

export function createQualityManager(options = {}) {
  const tier = initialQuality(options)
  return { tier, samples: [], slowFrames: 0, peakDpr: Math.min(Number(options.devicePixelRatio) || 1, QUALITY[tier].maxDpr) }
}

/** Quality only moves down. A deliberate page reload is required to opt back into a higher tier. */
export function recordFrame(manager, frameMs) {
  const samples = [...manager.samples, Math.max(0, Number(frameMs) || 0)].slice(-30)
  if (samples.length < 30) return { ...manager, samples }
  const average = samples.reduce((sum, value) => sum + value, 0) / samples.length
  const budget = QUALITY[manager.tier].frameBudget
  const slowFrames = average > budget * 1.25 ? manager.slowFrames + 1 : Math.max(0, manager.slowFrames - 1)
  let tier = manager.tier
  if (slowFrames >= 3) tier = ORDER[Math.min(ORDER.length - 1, ORDER.indexOf(tier) + 1)]
  return { ...manager, tier, samples: [], slowFrames: tier === manager.tier ? slowFrames : 0 }
}

export const qualitySettings = (manager, devicePixelRatio = 1) => ({
  ...QUALITY[manager.tier],
  pixelRatio: Math.min(Math.max(1, Number(devicePixelRatio) || 1), QUALITY[manager.tier].maxDpr),
})

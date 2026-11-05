export const DEMO_STEPS = [
  { id: 'network', label: 'Network', title: 'Six hosts in three zones.', body: 'The view begins with the demo topology loaded from the project host and connection data.' },
  { id: 'detect', label: 'Detect', title: 'A scripted event compromises Workstation A.', body: 'The host changes shape when the replay reaches its compromise event.' },
  { id: 'reconstruct', label: 'Reconstruct', title: 'The attempted path is drawn.', body: 'The red route connects the compromised host to the scripted target.' },
  { id: 'forecast', label: 'Forecast', title: 'Three feasible destinations are ranked.', body: 'Violet paths show the model’s next-host distribution from its repository transition counts.' },
  { id: 'contain', label: 'Contain', title: 'An analyst confirms the simulated response.', body: 'The target changes to a contained host. No real network is changed.' },
]

export function normalizeDemoStep(step) {
  const value = Number(step)
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(DEMO_STEPS.length - 1, Math.round(value)))
}

export function demoState(step) {
  const activeStep = normalizeDemoStep(step)
  return {
    activeStep,
    step: DEMO_STEPS[activeStep],
    detected: activeStep >= 1,
    reconstructed: activeStep >= 2,
    forecast: activeStep >= 3,
    contained: activeStep >= 4,
  }
}

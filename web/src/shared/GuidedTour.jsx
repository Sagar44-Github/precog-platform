import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from './AuthContext.jsx'
import { api } from './api.js'
import { Icon } from './icons.jsx'

const STEPS = [
  { path: '/console/topology', title: 'Start with the network', copy: 'Inspect the three simulated zones. Select a host to review its state and synthetic risk profile. Lite mode keeps this view usable without WebGL.', action: 'Open topology explorer' },
  { path: '/alerts', title: 'Review detection events', copy: 'The replay feeds scripted packets through the NIDS detector. Open an alert to review its host, severity, and technique context.', action: 'Open alerts' },
  { path: '/forecasts', title: 'Inspect the forecast', copy: 'Review the recorded candidate set and each prediction outcome. A forecast is a ranked guess for this replay, not a guarantee.', action: 'Open forecasts' },
  { path: '/containment', title: 'Propose, then confirm', copy: 'Containment changes only simulated in-memory host state. Review the target list and confirm explicitly; the tour never confirms an action for you.', action: 'Open containment' },
  { path: '/replay', title: 'Step through the replay', copy: 'Pause, advance one event, scrub read-only snapshots, or compare two finished sessions. Session scores are not overall model accuracy.', action: 'Open Replay Studio' },
  { path: '/reports', title: 'Close with a report', copy: 'Review and export the completed session. Keep the distinction between held-out evaluation and this replay’s counters clear.', action: 'Open reports' },
]

function stepUrl(step) { return `${step.path}?tour=golden-path&step=${STEPS.indexOf(step)}` }

export default function GuidedTour() {
  const { permissions } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const dialog = useRef(null)
  const focusable = useRef(null)
  const [message, setMessage] = useState('')
  const isOpen = params.get('tour') === 'golden-path'
  const stepIndex = Math.max(0, Math.min(STEPS.length - 1, Number(params.get('step')) || 0))
  const step = STEPS[stepIndex]

  useEffect(() => {
    if (!isOpen) return undefined
    focusable.current?.focus()
    const onKeyDown = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); navigate(location.pathname, { replace: true }) }
      if (event.key !== 'Tab') return
      const controls = dialog.current?.querySelectorAll('button:not(:disabled)')
      if (!controls?.length) return
      const first = controls[0]
      const last = controls[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isOpen, location.pathname, navigate])

  if (!isOpen) return null

  async function startReplay() {
    setMessage('')
    try {
      const status = await api.replayStatus()
      if (['running', 'paused', 'waiting_for_decision'].includes(status.state)) {
        setMessage('A replay is already active. Continue with the existing session.')
        return
      }
      await api.startReplay('golden-path', 1)
      setMessage('Golden Path started. All events and responses are simulated.')
    } catch (error) { setMessage(error.message || 'Replay could not start.') }
  }

  function advance() {
    if (stepIndex >= STEPS.length - 1) {
      try { localStorage.setItem('precog-guided-tour-completed', '1') } catch {}
      navigate('/help', { replace: true })
    } else navigate(stepUrl(STEPS[stepIndex + 1]))
  }

  return <div className="tour-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) navigate(location.pathname, { replace: true }) }}>
    <section ref={dialog} className="tour-dialog" role="dialog" aria-modal="true" aria-labelledby="tour-title" aria-describedby="tour-copy">
      <div className="tour-topline"><span>GUIDED GOLDEN PATH · STEP {stepIndex + 1} OF {STEPS.length}</span><button type="button" className="icon-button" aria-label="Close guided tour" onClick={() => navigate(location.pathname, { replace: true })}><Icon name="close" size={17} /></button></div>
      <div className="tour-progress" role="progressbar" aria-label="Guided tour progress" aria-valuemin="1" aria-valuemax={STEPS.length} aria-valuenow={stepIndex + 1}><span style={{ width: `${((stepIndex + 1) / STEPS.length) * 100}%` }} /></div>
      <p className="ops-eyebrow">{step.action.toUpperCase()}</p><h2 id="tour-title" ref={focusable} tabIndex="-1">{step.title}</h2><p id="tour-copy" className="tour-copy">{step.copy}</p>
      {stepIndex === 0 && permissions?.can_run_replay && <button type="button" className="ops-button tour-start-button" onClick={startReplay}>Start Golden Path</button>}
      {message && <p className="tour-message" role="status">{message}</p>}
      <div className="tour-actions"><button type="button" className="ops-button ops-button-secondary" onClick={() => navigate(location.pathname, { replace: true })}>Close tour</button><button type="button" className="ops-button" onClick={advance}>{stepIndex === STEPS.length - 1 ? 'Finish tour' : 'Next step'}</button></div>
    </section>
  </div>
}

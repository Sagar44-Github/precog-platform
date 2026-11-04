import { useState } from 'react'
import { api } from './api.js'

/** One clear entry into the safe, repeatable demo replay. */
export default function DemoStart({ className = '', hostCount = 6 }) {
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState('')

  async function start() {
    setBusy(true)
    setProblem('')
    try {
      await api.startReplay('golden-path', 1)
    } catch (error) {
      setProblem(error.message || 'The replay could not be started. Try again.')
      setBusy(false)
    }
  }

  return (
    <section className={`demo-launch ${className}`.trim()} aria-labelledby="demo-launch-title" aria-busy={busy}>
      <div className="demo-launch-topline"><span className="demo-launch-orbit" aria-hidden="true">◈</span><span>REPLAY ENVIRONMENT READY</span><span className="demo-launch-hosts">{hostCount} HOSTS · 3 ZONES</span></div>
      <div className="demo-launch-copy">
        <p className="demo-launch-kicker">THE GOLDEN PATH · ABOUT 15 SECONDS</p>
        <h2 id="demo-launch-title">See the next move<br /><span>before it happens.</span></h2>
        <p className="demo-launch-description">Watch detection, the attack path and Precog’s forecast unfold. You choose whether to contain the predicted target.</p>
      </div>
      <div className="demo-launch-flow" aria-label="Demo stages">
        <div><span>01</span><b>DETECT</b><small>Replay flags suspicious traffic</small></div>
        <i aria-hidden="true">→</i>
        <div><span>02</span><b>PREDICT</b><small>Precog ranks likely targets</small></div>
        <i aria-hidden="true">→</i>
        <div><span>03</span><b>RESPOND</b><small>You confirm simulated containment</small></div>
      </div>
      <button type="button" className="demo-launch-button" onClick={start} disabled={busy}>
        <span>{busy ? 'Starting replay…' : 'Start Golden Path'}</span><b aria-hidden="true">↗</b>
      </button>
      <p className="demo-launch-footnote">SIMULATION ONLY <span>·</span> No live traffic or real enforcement</p>
      {problem && <p className="demo-launch-error" role="alert">{problem}</p>}
    </section>
  )
}

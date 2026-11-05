import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../shared/AuthContext.jsx'
import { api } from '../shared/api.js'
import { ThemeToggle, useTheme } from '../shared/theme-context.jsx'
import ThemeLogo from '../shared/ThemeLogo.jsx'
import data from './data.generated.json'
import { DEMO_STEPS, demoState, normalizeDemoStep } from './demoState.js'
import './landing.css'

const LandingStage = lazy(() => import('../three/LandingStage.jsx'))
const MODE_KEY = 'precog-landing-mode'

function webgl2Available() {
  try {
    const canvas = document.createElement('canvas')
    const context = canvas.getContext('webgl2')
    const available = Boolean(context)
    context?.getExtension('WEBGL_lose_context')?.loseContext()
    return available
  } catch { return false }
}

function preferredMode() {
  if (typeof window === 'undefined') return 'lite'
  try {
    const saved = localStorage.getItem(MODE_KEY)
    if (saved === 'full' || saved === 'lite') return saved
  } catch {}
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const connection = navigator.connection
  return reduced || connection?.saveData || !webgl2Available() ? 'lite' : 'full'
}

function LiteDiagram({ activeStep }) {
  const state = demoState(activeStep)
  const points = useMemo(() => Object.fromEntries(data.simulation.hosts.map((host) => [host.host_id, {
    x: 390 + host.position[0] * 43,
    y: 225 + host.position[1] * 59,
  }])), [])
  const entry = points[data.simulation.entryHost]
  const target = points[data.simulation.attemptedTo]
  return <svg className="landing-lite-diagram" viewBox="0 0 780 460" role="img" aria-label={`Isometric view of ${data.simulation.hostsCount} simulated hosts in ${data.simulation.zones.join(', ')}. Current step: ${state.step.label}.`}>
    <g className="lite-zones" aria-hidden="true">
      <polygon points="52,112 180,60 286,104 158,158" /><polygon points="300,200 410,156 516,200 406,246" /><polygon points="488,294 614,244 726,290 600,340" />
      {data.simulation.zones.map((zone, index) => <text key={zone} x={[75, 322, 510][index]} y={[100, 188, 282][index]}>{zone.toUpperCase()}</text>)}
    </g>
    <g className="lite-edges" aria-hidden="true">{data.simulation.edges.map((edge) => <line key={edge.key} x1={points[edge.from].x} y1={points[edge.from].y} x2={points[edge.to].x} y2={points[edge.to].y} />)}</g>
    {state.forecast && data.forecast.candidates.map((candidate) => {
      const at = points[candidate.hostId]
      return <path key={candidate.hostId} className="lite-forecast" style={{ '--path-width': `${1.5 + candidate.confidence * 5}px` }} d={`M ${entry.x} ${entry.y} Q ${(entry.x + at.x) / 2} ${(entry.y + at.y) / 2 - 26} ${at.x} ${at.y}`} />
    })}
    {state.reconstructed && <path className="lite-attack-path" d={`M ${entry.x} ${entry.y} Q ${(entry.x + target.x) / 2} ${(entry.y + target.y) / 2 - 38} ${target.x} ${target.y}`} />}
    {state.contained && <g className="lite-lattice" transform={`translate(${target.x} ${target.y})`} aria-hidden="true"><path d="M-23-23h46v46h-46zM-23-8h46M-23 8h46M-8-23v46M8-23v46" /></g>}
    <g className="lite-hosts">{data.simulation.hosts.map((host) => {
      const at = points[host.host_id]
      const compromised = host.host_id === data.simulation.entryHost && state.detected
      const contained = host.host_id === data.simulation.attemptedTo && state.contained
      return <g key={host.host_id} className="lite-host-group">
        {compromised
          ? <polygon className="lite-host compromised" points={`${at.x},${at.y - 14} ${at.x + 14},${at.y} ${at.x},${at.y + 14} ${at.x - 14},${at.y}`} />
          : contained
            ? <rect className="lite-host contained" x={at.x - 12} y={at.y - 12} width="24" height="24" />
            : <circle className="lite-host" cx={at.x} cy={at.y} r="11" />}
        <text x={at.x} y={at.y + 30}>{host.name}</text>
      </g>
    })}</g>
  </svg>
}

function ForecastReadout() {
  return <ol className="landing-forecast-readout" aria-label="Predicted next hosts">
    {data.forecast.candidates.map((candidate, index) => <li key={candidate.hostId}>
      <span>{String(index + 1).padStart(2, '0')}</span><b>{candidate.name}</b><strong>{candidate.percent}%</strong>
      <i style={{ '--confidence': `${candidate.percent}%` }} />
    </li>)}
  </ol>
}

function EvidenceTable() {
  const values = [
    ['Precog Markov model', data.evaluation.top1],
    ['Rule based baseline', data.evaluation.ruleBased],
    ['Uniform baseline', data.evaluation.uniform],
  ]
  return <div className="landing-evidence-table" role="table" aria-label="Held-out precision at one comparison">
    {values.map(([name, result]) => <div className="landing-evidence-row" role="row" key={name}>
      <span role="cell">{name}</span><b role="cell">{result.percent}%</b><small role="cell">± {result.standardErrorPercent} pp</small>
      <i style={{ '--confidence': `${result.percent}%` }} aria-hidden="true" />
    </div>)}
  </div>
}

export default function LandingPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { username } = useAuth()
  const { theme } = useTheme()
  const [mode, setMode] = useState(preferredMode)
  const [activeStep, setActiveStep] = useState(3)
  const [playing, setPlaying] = useState(false)
  const [selectedHostId, setSelectedHostId] = useState(data.simulation.entryHost)
  const [message, setMessage] = useState('')
  const [entering, setEntering] = useState(false)
  const timerRef = useRef(0)
  const stageState = demoState(activeStep)
  const selectedHost = data.simulation.hosts.find((host) => host.host_id === selectedHostId) || data.simulation.hosts[0]

  useEffect(() => {
    try { localStorage.setItem(MODE_KEY, mode) } catch {}
    return () => { if (timerRef.current) window.clearTimeout(timerRef.current) }
  }, [mode])

  useEffect(() => {
    if (!playing) return undefined
    if (activeStep >= DEMO_STEPS.length - 1) {
      setPlaying(false)
      return undefined
    }
    timerRef.current = window.setTimeout(() => setActiveStep((step) => normalizeDemoStep(step + 1)), 1050)
    return () => window.clearTimeout(timerRef.current)
  }, [playing, activeStep])

  useEffect(() => {
    if (!location.hash) return
    document.getElementById(location.hash.slice(1))?.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }, [location.hash])

  const onFailure = useCallback((error) => {
    setMode('lite')
    setMessage(`The 3D scene could not start (${error?.message || 'WebGL unavailable'}). The reduced scene is ready.`)
  }, [])

  const setStep = (step) => {
    setPlaying(false)
    setActiveStep(normalizeDemoStep(step))
    setMessage('')
  }

  function playScenario() {
    setMessage('')
    setActiveStep(0)
    setPlaying(true)
  }

  function enter() {
    const requested = '/console'
    setEntering(true)
    window.setTimeout(() => navigate(username ? requested : '/login', username ? undefined : { state: { from: requested } }), window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 260)
  }

  async function runBackendReplay() {
    if (!username) {
      navigate('/login', { state: { from: '/console' } })
      return
    }
    setMessage('Starting the scripted Golden Path…')
    try {
      await api.startReplay(data.simulation.scenarioId, 1)
      navigate('/console')
    } catch (error) {
      setMessage(error.message || 'Open the console and start the Golden Path there.')
    }
  }

  return <div className={`landing-page${entering ? ' is-entering' : ''}`}>
    <a className="landing-skip" href="#main-content">Skip to content</a>
    <header className="landing-header">
      <a className="landing-brand" href="/app/" aria-label="Precog SOC home"><ThemeLogo className="landing-brand-logo" /><span className="landing-brand-copy">PRECOG <i>/ SOC</i></span></a>
      <nav className="landing-nav" aria-label="Main navigation">
        <a href="#demonstration">Demonstration</a><a href="#evidence">Evidence</a><a href="#method">Method</a>
      </nav>
      <span className="landing-simulation">SIMULATION</span>
      <div className="landing-header-controls"><ThemeToggle className="landing-theme-toggle" /><button className="landing-mode-toggle" type="button" onClick={() => setMode((current) => current === 'full' ? 'lite' : 'full')}>{mode === 'full' ? 'Reduced version' : '3D version'}</button></div>
    </header>

    <main id="main-content" tabIndex="-1">
      <section className="landing-hero" aria-labelledby="landing-title">
        <figure className={`landing-stage-wrap mode-${mode}`} id="demonstration" aria-label="Interactive 3D network replay">
          <div className="landing-stage-visual">
            {mode === 'full'
              ? <Suspense fallback={<LiteDiagram activeStep={activeStep} />}><LandingStage key={theme} activeStep={activeStep} onSelectHost={(host) => setSelectedHostId(host.host_id)} onFailure={onFailure} /></Suspense>
              : <LiteDiagram activeStep={activeStep} />}
            <div className="landing-scene-atmosphere" aria-hidden="true" />
            <div className="landing-stage-heading">
              <span>LIVE NETWORK MODEL <i /> {data.simulation.hostsCount} demo hosts · {data.simulation.zones.length} network zones</span>
              <span>DRAG TO ORBIT <b>↗</b></span>
            </div>
            <div className="landing-intro">
              <p className="landing-kicker">PRECOG / GOLDEN PATH SIMULATION</p>
              <h1 id="landing-title">Predict the next move.</h1>
              <p className="landing-summary">Replay an intrusion path, inspect the forecast, and review simulated containment in an interactive 3D network. Everything shown here is a simulation.</p>
              <div className="landing-intro-actions">
                <button className="landing-primary" type="button" onClick={playScenario}>Play the scenario <span>↗</span></button>
                <button className="landing-secondary" type="button" onClick={() => enter()}>Open the SOC console</button>
              </div>
              {message && <p className="landing-message" role="status">{message}</p>}
            </div>
            <aside className="landing-forecast-panel" aria-label="Predicted next hosts">
              <div className="landing-panel-heading"><span>PRECOG ENGINE</span><span>TOP {data.forecast.candidates.length}</span></div>
              <p className="landing-panel-title">Most likely next hosts</p>
              <ForecastReadout />
              <p className="landing-panel-foot">Markov transitions · simulated scenario</p>
            </aside>
            <figcaption className="landing-stage-caption">
              <span>SIMULATION · {data.simulation.zones.map((zone) => zone.toUpperCase()).join(' / ')}</span>
              <span>{selectedHost.name} · {selectedHost.address}</span>
            </figcaption>
            <div className="landing-hud-bottom">
              <div className="landing-current-step" aria-live="polite">
                <p className="landing-kicker"><span className="landing-live-dot" /> {String(activeStep + 1).padStart(2, '0')} / {stageState.step.label.toUpperCase()}</p>
                <h2>{stageState.step.title}</h2>
                <p>{stageState.step.body}</p>
                {stageState.contained && <p className="landing-contained-note">The move toward {data.simulation.hosts.find((host) => host.host_id === data.simulation.attemptedTo)?.name} was blocked in this simulation.</p>}
              </div>
              <div className="landing-scene-description" aria-live="polite">
                <span className="landing-scene-state" aria-hidden="true">HOST DETAIL</span>
                <p><b>{selectedHost.name}</b> · {selectedHost.role}. {stageState.detected && selectedHost.host_id === data.simulation.entryHost ? 'Compromised in the replay.' : stageState.contained && selectedHost.host_id === data.simulation.attemptedTo ? 'Contained in the replay.' : 'Select a host in the scene to inspect it.'}</p>
              </div>
              <div className="landing-controls" aria-label="Golden Path replay controls">
                <ol className="landing-step-list">{DEMO_STEPS.map((step, index) => <li key={step.id}>
                  <button type="button" aria-pressed={activeStep === index} onClick={() => setStep(index)}><span>{String(index + 1).padStart(2, '0')}</span>{step.label}</button>
                </li>)}</ol>
                <div className="landing-control-row">
                  <button type="button" className="landing-play" onClick={playing ? () => setPlaying(false) : playScenario} aria-label={playing ? 'Pause scenario' : 'Replay Golden Path'}>{playing ? 'Pause' : 'Replay Golden Path'}</button>
                  <label className="landing-step-range-label" htmlFor="landing-step-range">SCRUB REPLAY</label>
                  <input id="landing-step-range" type="range" min="0" max={DEMO_STEPS.length - 1} step="1" value={activeStep} aria-label="Scrub the replay" aria-valuetext={stageState.step.label} onChange={(event) => setStep(Number(event.target.value))} />
                  <button type="button" className="landing-reset" onClick={() => setStep(0)}>Reset</button>
                  <label className="landing-inspect-label" htmlFor="landing-host-select">Inspect</label>
                  <select id="landing-host-select" aria-label="Inspect host" value={selectedHostId} onChange={(event) => setSelectedHostId(event.target.value)}>{data.simulation.hosts.map((host) => <option key={host.host_id} value={host.host_id}>{host.name}</option>)}</select>
                  <button type="button" className="landing-soc-launch" onClick={runBackendReplay}>Start Golden Path in SOC</button>
                </div>
              </div>
            </div>
          </div>
        </figure>
      </section>

      <section id="evidence" className="landing-section landing-evidence" aria-labelledby="evidence-title">
        <div className="landing-section-intro">
          <p className="landing-kicker">RESULTS / HELD-OUT SEQUENCES</p>
          <h2 id="evidence-title">The numbers stay attached to their limits.</h2>
          <p>Precog’s precision@1 is compared with two baselines on {data.evaluation.heldOutForecasts} sequences generated for this demo network.</p>
        </div>
        <div className="landing-evidence-content">
          <EvidenceTable />
          <p className="landing-evidence-note">Precision@3 is uninformative on this {data.simulation.hostsCount}-host network: at most {data.evaluation.maxCandidates} destinations are reachable, so every method lists them. This is scripted held-out data, not evidence about real attackers.</p>
          <div className="landing-detection-note">
            <p className="landing-kicker">DETECTOR / OFFLINE REPORT</p>
            <p>{data.detection.model} · F1 {data.detection.f1Percent}% on {data.detection.dataset}.</p>
            <p>In separate runs with each attack type omitted from training, examples were flagged at {data.detection.unseenRateMinPercent}–{data.detection.unseenRateMaxPercent}%. The split was {data.detection.split.toLowerCase()}, so it does not test future traffic or establish live detection.</p>
            <ul>{data.detection.unseenAttackRates.map((item) => <li key={item.attack}>{item.attack} <b>{item.percent}%</b></li>)}</ul>
          </div>
        </div>
      </section>

      <section id="method" className="landing-section landing-method" aria-labelledby="method-title">
        <div className="landing-section-intro">
          <p className="landing-kicker">METHOD / CLOSED LOOP</p>
          <h2 id="method-title">From observed event to reviewed response.</h2>
          <p>The demonstration uses the same scripted scenario and project data as the local replay.</p>
        </div>
        <ol className="landing-method-list">{[
          ['Detect', 'The scripted packet events reach the detector and mark a compromised host.'],
          ['Reconstruct', 'The graph records the observed host and the attempted move.'],
          ['Forecast', 'The Markov model ranks reachable hosts from transition counts.'],
          ['Confirm', 'An analyst reviews a proposed response before the simulated host changes state.'],
        ].map(([title, body], index) => <li key={title}><span>{String(index + 1).padStart(2, '0')}</span><div><h3>{title}</h3><p>{body}</p></div></li>)}</ol>
      </section>
    </main>

    <footer className="landing-footer">
      <p>{data.credits.institution} · {data.credits.course}</p>
      <p>{data.attribution.nids} {data.attribution.attackgraph} {data.attribution.networkx} {data.attribution.three} {data.attribution.mitreNotice} Guide: {data.credits.guide}.</p>
      {data.credits.team?.length > 0 && <ul>{data.credits.team.map((member) => <li key={member.name}>{member.name} · {member.role}</li>)}</ul>}
    </footer>
  </div>
}

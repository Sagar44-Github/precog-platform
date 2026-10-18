import { useEffect, useReducer, useRef, useState } from 'react'
import { api } from '../../shared/api.js'
import {
  accuracyText, attackPath, clamp01, containReducer, formatTime, forecastRows, hostName, hostStateMeta, initialContain, mitreUrl,
  outcomeText, severityMeta, sliderComplete, threatLevel,
} from './logic.js'

// Phone-screen building blocks (owner: GRAPH). Colours only come from CSS variables (see mobile.css and shared/theme.css).

export function SeverityBadge({ severity }) {
  const meta = severityMeta(severity)
  return (
    <span className="m-pill" style={{ borderColor: meta.color }}>
      <span className="m-icon" style={{ color: meta.color }} aria-hidden="true">{meta.icon}</span>{meta.word}
    </span>
  )
}

export function StateChip({ state }) {
  const meta = hostStateMeta(state)
  return (
    <span className="m-pill" style={{ borderColor: meta.color }}>
      <span className="m-icon" style={{ color: meta.color }} aria-hidden="true">{meta.icon}</span>{meta.word}
    </span>
  )
}

export function ThreatLevelCard({ state, stale }) {
  const level = threatLevel(state)
  if (!level) return null
  return (
    <section className="m-card m-threat" style={{ borderLeftColor: level.color }} data-level={level.key} data-stale={stale ? 'true' : 'false'} aria-live="polite">
      <p className="m-threat-word" style={{ color: stale ? undefined : level.color }}><span aria-hidden="true">{level.icon} </span>{level.word}</p>
      <p className="m-caption">{level.caption}</p>
    </section>
  )
}

export function AlertCard({ alert, onOpen }) {
  const technique = alert.technique_id ? `${alert.technique_name} · ${alert.technique_id}` : null
  return (
    <button type="button" className="m-alert" onClick={() => onOpen && onOpen(alert)} aria-label={`${severityMeta(alert.severity).word} alert on ${alert.host}`}>
      <span className="m-row"><SeverityBadge severity={alert.severity} /><span className="m-mono m-caption">{formatTime(alert.ts)}</span></span>
      <p>{alert.explanation}</p>
      <span className="m-row">
        <span className="m-chip-tech">{technique}{alert.source === 'scripted' ? (technique ? ' · ' : '') + 'scripted' : ''}</span>
        <span className="m-mono m-caption">{alert.host} ›</span>
      </span>
    </button>
  )
}

export function ForecastBars({ state }) {
  const rows = forecastRows(state)
  const hint = state && state.forecast && state.forecast.technique_hint
  return (
    <div>
      <div className="m-forecast-head"><span className="m-dashed-ring" aria-hidden="true" />Precog predicts the next target</div>
      {rows.length === 0 ? (
        <p className="m-caption">No forecast right now. Precog predicts the next target after a host is compromised.</p>
      ) : (
        <div className="m-bars">
          {rows.map((row) => (
            <div className="m-bar-row" key={row.hostId}>
              <span className="m-mono">{row.rank}</span>
              <div className="m-bar-track" role="img" aria-label={`${row.name} ${row.percent} percent`}><div className="m-bar-fill" style={{ width: `${row.percent}%` }} /></div>
              <span className="m-mono m-bar-pct">{row.percent} %</span>
              <span className="m-bar-name">{row.name}</span>
            </div>
          ))}
        </div>
      )}
      {hint && <p className="m-caption">Likely next technique: {hint.technique_name}</p>}
    </div>
  )
}

export function AccuracyCounter({ metrics }) {
  return (
    <div>
      <p className="m-caption" style={{ margin: 0 }}>Precog accuracy this session</p>
      <p className="m-mono" style={{ margin: '4px 0', fontSize: 18 }}>{accuracyText(metrics)}</p>
      <p className="m-caption" style={{ margin: 0 }}>Session counter, not the model's overall accuracy.</p>
    </div>
  )
}

export function AttackPath2D({ state }) {
  const { steps, next } = attackPath(state)
  if (!steps.length) return <p className="m-caption">No host is compromised.</p>
  return (
    <div className="m-path" aria-label="Attack path">
      {steps.map((step, i) => (
        <span key={step.hostId} className="m-row" style={{ gap: 8 }}>
          {i > 0 && <span className="m-arrow" aria-hidden="true">→</span>}
          <StateChip state="compromised" /><span>{step.name}</span>
        </span>
      ))}
      {next && <span className="m-row" style={{ gap: 8 }}><span className="m-arrow-next" aria-hidden="true">⇢</span><span className="m-pill" style={{ borderStyle: 'dashed' }}>{next.name} predicted, {next.percent} %</span></span>}
    </div>
  )
}

export function OutcomeCard({ forecast, state }) {
  const outcome = outcomeText(forecast, state)
  if (!outcome) return null
  return <section className="m-card m-outcome" data-tone={outcome.tone}><p style={{ margin: 0 }}>{outcome.text}</p></section>
}

export { mitreUrl }

/** The "slide to confirm" control. A keyboard user gets the Confirm button instead (UI/UX brief 6.7). */
export function SlideToConfirm({ onConfirm, disabled }) {
  const track = useRef(null)
  const [progress, setProgress] = useState(0)
  const dragging = useRef(false)

  const move = (clientX) => {
    const box = track.current.getBoundingClientRect()
    setProgress(clamp01((clientX - box.left - 24) / Math.max(1, box.width - 48)))
  }
  const release = () => {
    if (!dragging.current) return
    dragging.current = false
    setProgress((p) => { if (sliderComplete(p)) onConfirm(); return 0 })
  }
  return (
    <div>
      <div className="m-slider" ref={track}
           onPointerDown={(e) => { if (disabled) return; dragging.current = true; e.currentTarget.setPointerCapture(e.pointerId); move(e.clientX) }}
           onPointerMove={(e) => dragging.current && move(e.clientX)} onPointerUp={release} onPointerCancel={release}>
        <div className="m-slider-label">Slide to confirm</div>
        <div className="m-slider-knob" style={{ transform: `translateX(${progress * ((track.current ? track.current.clientWidth : 300) - 48)}px)` }} aria-hidden="true">›</div>
      </div>
      <button type="button" className="m-btn m-btn-text" onClick={onConfirm} disabled={disabled}>Confirm without sliding</button>
    </div>
  )
}

/** Contain button + confirmation sheet. api is injectable so it can be tested. */
export function ContainFlow({ state, client = api, onDone }) {
  const [flow, dispatch] = useReducer(containReducer, initialContain)
  const rows = forecastRows(state)
  const target = rows[0]
  const forecastId = state && state.forecast ? state.forecast.forecast_id : null

  useEffect(() => {
    if (flow.step !== 'proposing' || !target) return
    client.proposeContainment(target.hostId, forecastId, 'mobile')
      .then((action) => dispatch({ type: 'proposed', action }))
      .catch((error) => dispatch({ type: 'error', message: error.message }))
  }, [flow.step])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (flow.step !== 'confirming') return undefined
    const timer = setInterval(() => dispatch({ type: 'tick' }), 1000)
    return () => clearInterval(timer)
  }, [flow.step])

  const confirm = () => {
    dispatch({ type: 'confirm' })
    client.confirmContainment(flow.action.action_id)
      .then((action) => { dispatch({ type: 'confirmed', action }); if (onDone) onDone(`${target.name} contained (simulated)`) })
      .catch((error) => dispatch({ type: 'error', message: error.message }))
  }
  const cancel = () => {
    if (flow.action) client.cancelContainment(flow.action.action_id).catch(() => {})
    dispatch({ type: 'cancel' })
  }

  if (!target) return null
  const open = flow.step === 'confirming' || flow.step === 'sending'
  return (
    <div>
      <button type="button" className="m-btn m-btn-contain" onClick={() => dispatch({ type: 'tap' })} disabled={flow.step === 'proposing' || open}>
        {flow.step === 'proposing' ? 'Asking…' : `Contain ${target.name}`}
      </button>
      <div className="m-error" role="alert">{flow.step === 'error' || flow.step === 'expired' ? flow.message : ''}</div>
      {open && (
        <>
          <div className="m-sheet-backdrop" />
          <div className="m-sheet" role="dialog" aria-modal="true" aria-label={`Contain ${target.name}?`}>
            <h2 style={{ margin: 0 }}>Contain {target.name}?</h2>
            <p style={{ margin: 0 }}>This marks the host as contained. It is a SIMULATION: nothing on a real network changes.</p>
            <SlideToConfirm onConfirm={confirm} disabled={flow.step === 'sending'} />
            <button type="button" className="m-btn m-btn-text" onClick={cancel} disabled={flow.step === 'sending'}>Cancel</button>
            <p className="m-caption m-mono" style={{ margin: 0 }}>{flow.secondsLeft} s left</p>
          </div>
        </>
      )}
    </div>
  )
}

import { accuracyText, attackPath, forecastRows, hostName, hostStateMeta, outcomeText, severityMeta } from './soc-logic.js'

const severityClass = (severity) => String(severity || 'normal').toLowerCase()
const stateClass = (state) => String(state || 'normal').toLowerCase()

export function SeverityBadge({ severity }) {
  const meta = severityMeta(severity)
  return <span className={`soc-status-badge soc-severity-${severityClass(severity)}`}><span aria-hidden="true">{meta.icon}</span>{meta.word}</span>
}

export function StateChip({ state }) {
  const meta = hostStateMeta(state)
  return <span className={`soc-status-badge soc-host-${stateClass(state)}`}><span aria-hidden="true">{meta.icon}</span>{meta.word}</span>
}

export function ForecastBars({ state }) {
  const rows = forecastRows(state)
  const hint = state?.forecast?.technique_hint
  return <section className="soc-forecast" aria-label="Precog forecast">
    <div className="soc-forecast-title"><span aria-hidden="true">◌</span>Precog predicts the next target</div>
    {rows.length === 0 ? <p className="soc-supporting-text">No forecast right now. Precog predicts the next target after a host is compromised.</p> : <ol className="soc-forecast-list">
      {rows.map((row) => <li className="soc-forecast-item" key={row.hostId}>
        <span className="soc-forecast-rank">{row.rank}</span>
        <span className="soc-forecast-track" role="img" aria-label={`${row.name} ${row.percent} percent`}><span style={{ width: `${row.percent}%` }} /></span>
        <span className="soc-forecast-percent">{row.percent}%</span>
        <span className="soc-forecast-host">{row.name}</span>
      </li>)}
    </ol>}
    {hint && <p className="soc-supporting-text">Likely next technique: {hint.technique_name}</p>}
  </section>
}

export function AccuracyCounter({ metrics }) {
  return <div className="soc-accuracy"><span className="soc-supporting-text">Precog accuracy this session</span><strong>{accuracyText(metrics)}</strong><span className="soc-supporting-text">Session counter, not the model’s overall accuracy.</span></div>
}

export function AttackPath2D({ state }) {
  const { steps, next } = attackPath(state)
  if (!steps.length) return <p className="soc-supporting-text">No host is compromised.</p>
  return <ol className="soc-attack-path" aria-label="Attack path">
    {steps.map((step, index) => <li key={step.hostId}>{index > 0 && <span className="soc-path-arrow" aria-hidden="true">→</span>}<StateChip state="compromised" /><span>{step.name}</span></li>)}
    {next && <li><span className="soc-path-arrow soc-path-predicted" aria-hidden="true">⇢</span><span className="soc-path-prediction">{next.name} predicted, {next.percent}%</span></li>}
  </ol>
}

export function OutcomeCard({ forecast, state }) {
  const outcome = outcomeText(forecast, state)
  if (!outcome) return null
  return <section className={`soc-outcome soc-outcome-${outcome.tone}`}><p>{outcome.text}</p></section>
}

export function hostLabel(state, hostId) {
  return hostName(state, hostId)
}

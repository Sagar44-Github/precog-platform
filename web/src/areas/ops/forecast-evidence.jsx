export function ForecastTargets({ targets, attemptedHost }) {
  return <ol className="forecast-target-list">{targets.map((target) => {
    const outcome = attemptedHost ? (target.host_id === attemptedHost ? 'outcome-hit' : 'outcome-not-hit') : ''
    return <li className={outcome} key={target.host_id}>
      <span className="forecast-rank">{target.rank}</span>
      <span className="forecast-target-name">{target.host_id}</span>
      <span className="forecast-confidence">{(target.confidence * 100).toFixed(1)}%</span>
      {attemptedHost && <span className="forecast-target-result">{target.host_id === attemptedHost ? 'Observed attempt' : 'Not attempted'}</span>}
    </li>
  })}</ol>
}

export function CandidateEvidence({ explanation }) {
  if (!explanation?.candidate_set?.length) return <div className="forecast-legacy-note">This older record has no saved candidate explanation.</div>
  return <section className="forecast-evidence" aria-label="Forecast candidate evidence">
    <div className="forecast-model-summary">
      <span>Model <b>{explanation.model.name === 'markov' ? 'Markov transition model' : 'Rule-based fallback'}</b></span>
      <span>Smoothing α <b>{explanation.model.alpha ?? 'not applicable'}</b></span>
      <span>Technique hint table <b>{explanation.technique_hint_source}</b></span>
      <span>Feasible candidates <b>{explanation.candidate_count}</b></span>
    </div>
    <div className="ops-table-wrap"><table className="ops-table forecast-evidence-table"><thead><tr><th>Candidate</th><th>Training transitions</th><th>Predicted probability</th><th>Model rank</th><th>Rule-based rank</th><th>Uniform rank</th></tr></thead><tbody>
      {explanation.candidate_set.map((candidate) => <tr key={candidate.host_id}>
        <td data-label="Candidate" className="ops-mono">{candidate.host_id}</td>
        <td data-label="Training transitions" className="cell-mono">{candidate.transition_count}</td>
        <td data-label="Predicted probability" className="forecast-confidence">{(candidate.model_probability * 100).toFixed(2)}%</td>
        <td data-label="Model rank">#{candidate.model_rank}</td>
        <td data-label="Rule-based rank">#{candidate.rule_based_rank}</td>
        <td data-label="Uniform rank">#{candidate.uniform_rank}</td>
      </tr>)}
    </tbody></table></div>
  </section>
}

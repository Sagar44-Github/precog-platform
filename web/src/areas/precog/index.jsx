import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { EmptyState, LoadingState } from '../../shared/components.jsx'
import './precog.css'

function PageHeader({ eyebrow, title, copy, action }) {
  return <header className="precog-page-head"><div><p className="precog-eyebrow">{eyebrow}</p><h1>{title}</h1><p>{copy}</p></div>{action}</header>
}

function ErrorNote({ children }) { return children ? <p className="precog-error" role="alert">{children}</p> : null }
function Metric({ label, value, note }) { return <article className="precog-metric"><span>{label}</span><b>{value}</b>{note && <small>{note}</small>}</article> }
function Confidence({ value }) { return <span className="precog-confidence"><i style={{ '--confidence': `${Math.max(0, Math.min(100, value * 100))}%` }} /><b>{(value * 100).toFixed(1)}%</b></span> }

export function ForecastsPage() {
  const [forecasts, setForecasts] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    Promise.all([api.forecasts(), api.precogMetrics().catch(() => null)])
      .then(([items, live]) => { if (active) { setForecasts(items); setMetrics(live) } })
      .catch((cause) => { if (active) setError(cause.message) })
    return () => { active = false }
  }, [])
  if (!forecasts && !error) return <LoadingState />
  const resolved = (forecasts || []).filter((item) => item.status === 'hit' || item.status === 'miss')
  return <main className="precog-page">
    <PageHeader eyebrow="PRECOG / FORECAST QUEUE" title="Predicted next moves" copy="Inspect each model estimate, compare it with what the replay did next, and open the inputs behind the ranking." action={<Link className="precog-button" to="/lab">Open what-if lab ↗</Link>} />
    <ErrorNote>{error}</ErrorNote>
    <div className="precog-metrics"><Metric label="FORECASTS IN SESSION" value={forecasts?.length ?? '—'} note="Current replay" /><Metric label="RESOLVED" value={resolved.length} note="Observed next move available" /><Metric label="PRECISION @ 1" value={metrics?.precision_at_1 == null ? '—' : `${(metrics.precision_at_1 * 100).toFixed(1)}%`} note="Live session estimate" /><Metric label="PRECISION @ 3" value={metrics?.precision_at_3 == null ? '—' : `${(metrics.precision_at_3 * 100).toFixed(1)}%`} note="Trivial with at most 3 candidates" /></div>
    <section className="precog-section"><div className="precog-section-head"><div><p className="precog-eyebrow">REPLAY EVIDENCE</p><h2>Forecast history</h2></div><span>{forecasts?.length || 0} records</span></div>
      {!forecasts?.length ? <EmptyState>No forecasts in this replay yet. Start a scripted scenario to create model estimates.</EmptyState> : <div className="precog-forecast-list">{[...forecasts].reverse().map((item) => <Link className="precog-forecast-card" key={item.forecast_id} to={`/forecasts/${encodeURIComponent(item.forecast_id)}`}>
        <span className={`precog-status status-${item.status}`}>{item.status}</span><div className="precog-forecast-main"><b>{item.forecast_id} <span>from {item.from_host}</span></b><div className="precog-targets">{item.targets.map((target) => <span key={target.host_id}><i>#{target.rank}</i>{target.host_id}<Confidence value={target.confidence} /></span>)}</div>{item.outcome && <small className="precog-outcome">Observed: {item.outcome.rank_hit ? `rank ${item.outcome.rank_hit} hit` : 'miss'}{item.outcome.blocked ? ' · move blocked' : ''} · attempted {item.outcome.attempted_host}</small>}</div><span className="precog-card-arrow" aria-hidden="true">↗</span>
      </Link>)}</div>}
    </section>
    <p className="precog-honesty">Model-based estimate from scripted replay data on a six-host demo network. It is not a guarantee of real-world protection.</p>
  </main>
}

export function ForecastDetailPage() {
  const { id } = useParams()
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { let active = true; api.forecastExplanation(id).then((value) => active && setDetail(value)).catch((cause) => active && setError(cause.message)); return () => { active = false } }, [id])
  if (!detail && !error) return <LoadingState />
  if (error) return <main className="precog-page"><ErrorNote>{error}</ErrorNote><Link to="/forecasts">← Forecast queue</Link></main>
  return <main className="precog-page">
    <PageHeader eyebrow="PRECOG / MODEL TRACE" title={`Forecast ${detail.forecast_id}`} copy={`Ranked from ${detail.from_host}; status is ${detail.outcome.status}. Each probability is a model estimate from the candidates feasible at that replay moment.`} action={<Link className="precog-button" to="/forecasts">← All forecasts</Link>} />
    <div className="precog-metrics"><Metric label="SMOOTHING ALPHA" value={detail.alpha ?? 'Rule fallback'} note="Used by the node transition model" /><Metric label="CANDIDATES" value={detail.candidate_set.length} note="Feasible at forecast time" /><Metric label="P@1 STANDARD ERROR" value={`${(detail.metric_standard_error * 100).toFixed(1)}%`} note="Held-out estimate uncertainty" /><Metric label="TECHNIQUE TABLE" value={detail.technique_table.toUpperCase()} note={detail.technique_hint?.technique_name || 'No technique hint available'} /></div>
    <div className="precog-detail-grid">
      <section className="precog-section"><div className="precog-section-head"><div><p className="precog-eyebrow">CANDIDATE RANKING</p><h2>Why these hosts</h2></div></div><p className="precog-formula">{detail.formula}</p><p className="precog-muted">P(target | source) = (transition count + α) / (counts for feasible candidates + α × candidate count)</p>
        {detail.context_source === 'reconstructed' && <p className="precog-muted">This shipped sample forecast predates the live recorder. Candidate context is reconstructed from the sample graph state; replay forecasts capture it at creation.</p>}
        <div className="precog-ranking">{detail.target_arithmetic.map((item) => <article key={item.host_id}><div><b>#{detail.target_arithmetic.findIndex((row) => row.host_id === item.host_id) + 1} · {item.host_id}</b><Confidence value={item.confidence} /></div><span>{item.transition_count} observed transitions in training · recomputed model probability {(item.model_probability * 100).toFixed(1)}%</span><code>{item.formula}</code></article>)}</div>
        <div className="precog-subgrid"><div><h3>Available candidates</h3>{detail.candidate_set.map((host) => <span className="precog-chip" key={host}>{host} · {detail.transition_counts.find((item) => item.host_id === host)?.count ?? 0} moves</span>)}</div><div><h3>Excluded at that moment</h3>{detail.excluded.length ? detail.excluded.map((item) => <span className="precog-chip" key={item.host_id}>{item.host_id} · {item.reason}</span>) : <span className="precog-muted">No linked hosts were excluded.</span>}</div></div>
      </section>
      <section className="precog-section"><div className="precog-section-head"><div><p className="precog-eyebrow">BASELINE CHECK</p><h2>Same candidates, other rankings</h2></div></div><RankingList title="Rule-based" items={detail.baseline_rule_based} /><RankingList title="Uniform" items={detail.baseline_uniform} />
        <div className="precog-calibration"><h3>Calibration bin for the top score</h3>{detail.calibration_bin ? <><div className="precog-cal-bars"><span style={{ height: `${Math.max(4, detail.calibration_bin.mean_confidence * 100)}%` }} /><span style={{ height: `${Math.max(4, detail.calibration_bin.observed_rate * 100)}%` }} /></div><p>Mean confidence {(detail.calibration_bin.mean_confidence * 100).toFixed(1)}% · observed rate {(detail.calibration_bin.observed_rate * 100).toFixed(1)}% · {detail.calibration_bin.count} held-out predictions in bin</p></> : <p className="precog-muted">No shipped calibration bin matches this score.</p>}</div>
      </section>
    </div>
    {detail.outcome.result && <section className="precog-outcome-panel"><b>OBSERVED OUTCOME · {detail.outcome.status.toUpperCase()}</b><span>{detail.outcome.result.rank_hit ? `The attempted host ${detail.outcome.result.attempted_host} was ranked #${detail.outcome.result.rank_hit}.` : `The move to ${detail.outcome.result.attempted_host} was a forecast miss.`}{detail.outcome.result.blocked ? ' The scripted move was blocked.' : ''}</span></section>}
    <ModelNote card={detail.model_card} />
  </main>
}

function RankingList({ title, items }) { return <div className="precog-baseline"><h3>{title}</h3>{items.map((item) => <div key={item.host_id}><span>#{item.rank} {item.host_id}</span><Confidence value={item.confidence} /></div>)}</div> }
function ModelNote({ card }) { return <aside className="precog-model-note"><b>ESTIMATE BASIS</b><p>{card.data_source} · {card.training_sequences} scripted training sequences · {card.network_hosts} demo hosts · {card.held_out_forecasts} held-out forecasts. P@3 is trivial here because each step has at most three candidates.</p><small>{card.limitations.join(' ')}</small></aside> }

export function WhatIfPage() {
  const [topology, setTopology] = useState(null)
  const [source, setSource] = useState('host-a')
  const [contain, setContain] = useState([])
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { api.topology().then(setTopology).catch((cause) => setError(cause.message)) }, [])
  const candidates = useMemo(() => topology?.feasible_edges.filter((edge) => edge.from_host === source).map((edge) => edge.to_host) || [], [source, topology])
  useEffect(() => { setContain((selected) => selected.filter((id) => candidates.includes(id))); setResult(null) }, [candidates.join('|')])
  const run = async (event) => {
    event.preventDefault(); setBusy(true); setError(''); setResult(null)
    try { setResult(await api.whatIf({ from_host: source, host_states: { [source]: 'compromised' }, contain_hosts: contain })) }
    catch (cause) { setError(cause.message) } finally { setBusy(false) }
  }
  return <main className="precog-page">
    <PageHeader eyebrow="PRECOG / COUNTERFACTUAL SANDBOX" title="What changes if we contain?" copy="Try a hypothetical response against the same transition model. This request is read-only and does not alter the active replay or forecast." />
    <div className="precog-lab-layout"><form className="precog-section precog-lab-form" onSubmit={run}><div className="precog-section-head"><div><p className="precog-eyebrow">SCENARIO INPUT</p><h2>Choose a compromised source</h2></div><span>SIMULATION ONLY</span></div>
      <label>Hypothetical attacker host<select value={source} onChange={(event) => setSource(event.target.value)}>{(topology?.hosts || []).map((host) => <option key={host.host_id} value={host.host_id}>{host.name} · {host.host_id}</option>)}</select></label>
      <fieldset><legend>Hosts to hypothetically contain</legend>{candidates.length ? candidates.map((hostId) => { const host = topology.hosts.find((item) => item.host_id === hostId); return <label className="precog-check-row" key={hostId}><input type="checkbox" checked={contain.includes(hostId)} onChange={(event) => setContain((value) => event.target.checked ? [...value, hostId] : value.filter((item) => item !== hostId))} /><span><b>{host.name}</b><small>{hostId}</small></span></label> }) : <p className="precog-muted">No one-hop candidates for this host.</p>}</fieldset>
      <button className="precog-button precog-button-primary" disabled={busy || !topology}>{busy ? 'Calculating…' : 'Compare hypothetical forecasts'}</button><ErrorNote>{error}</ErrorNote><p className="precog-muted">Projections renormalize over remaining feasible hosts. Containment interrupts legitimate use in the simulation too.</p>
    </form>
    <section className="precog-section precog-lab-result"><div className="precog-section-head"><div><p className="precog-eyebrow">COUNTERFACTUAL RESULT</p><h2>Forecast before and after</h2></div></div>
      {!result ? <EmptyState>Choose a source and optional targets to see how the ranked estimate changes.</EmptyState> : <><div className="precog-removal"><b>{(result.removed_probability_share * 100).toFixed(1)}%</b><span>of the original model probability was assigned to the contained targets</span></div><div className="precog-compare-forecasts"><ForecastProjection title="Before hypothetical containment" data={result.before} /><ForecastProjection title="After hypothetical containment" data={result.after} /></div><p className="precog-muted">Live forecast remains {result.live_forecast?.forecast_id || 'unchanged'}; this sandbox did not update it.</p><p className="precog-honesty">{result.basis}</p></>}
    </section></div>
  </main>
}

function ForecastProjection({ title, data }) { return <article className="precog-projection"><h3>{title}</h3>{data.targets.length ? data.targets.map((item) => <div key={item.host_id}><span>#{item.rank} {item.host_id}</span><Confidence value={item.confidence} /></div>) : <p className="precog-muted">No candidates remain.</p>}<small>Candidates: {data.candidates.join(', ') || 'none'}</small></article> }

export function AnalyticsPage() {
  const [overview, setOverview] = useState(null)
  const [experiments, setExperiments] = useState([])
  const [experiment, setExperiment] = useState(null)
  const [seed, setSeed] = useState('0')
  const [fraction, setFraction] = useState('0.2')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [role, setRole] = useState(null)
  useEffect(() => { Promise.all([api.modelOverview(), api.precogExperiments(), api.me()]).then(([model, runs, me]) => { setOverview(model); setExperiments(runs); setRole(me.role) }).catch((cause) => setError(cause.message)) }, [])
  const evaluate = async (event) => { event.preventDefault(); setBusy(true); setError(''); try { const record = await api.evaluatePrecog({ seed: Number(seed), test_fraction: Number(fraction) }); setExperiment(record); setExperiments((items) => [record, ...items.filter((item) => item.experiment_id !== record.experiment_id)]) } catch (cause) { setError(cause.message) } finally { setBusy(false) } }
  if (!overview && !error) return <LoadingState />
  const shipped = overview?.evaluation
  const report = experiment?.result || shipped
  return <main className="precog-page">
    <PageHeader eyebrow="PRECOG / EVALUATION LAB" title="Can we defend the estimate?" copy="Review held-out results, calibration and baseline comparisons. New runs evaluate the shipped scripted sequences and never retrain or replace the production model." />
    <ErrorNote>{error}</ErrorNote>
    {shipped && <><div className="precog-metrics"><Metric label="HELD-OUT FORECASTS" value={shipped.node_model.forecasts} note="Scripted generator test split" /><Metric label="PRECISION @ 1" value={`${(shipped.node_model.precision_at_1 * 100).toFixed(2)}%`} note={`± ${(shipped.node_model.precision_at_1_std_error * 100).toFixed(2)} pp standard error`} /><Metric label="RULE-BASED BASELINE" value={`${(shipped.baseline_rule_based.precision_at_1 * 100).toFixed(2)}%`} note="Simulated edge likelihood ranking" /><Metric label="UNIFORM BASELINE" value={`${(shipped.baseline_uniform.precision_at_1 * 100).toFixed(2)}%`} note={`ECE ${(shipped.node_model.expected_calibration_error * 100).toFixed(2)}% · P@3 is trivial`} /></div>
      <div className="precog-detail-grid"><section className="precog-section"><div className="precog-section-head"><div><p className="precog-eyebrow">RELIABILITY</p><h2>Calibration by confidence bin</h2></div></div><div className="precog-calibration-table"><div className="precog-cal-table-head"><span>Confidence</span><span>Observed</span><span>Predictions</span><span>Gap</span></div>{shipped.node_model.calibration_bins.map((bin) => <div key={bin.bin_low}><span>{Math.round(bin.bin_low * 100)}–{Math.round(bin.bin_high * 100)}%</span><span>{(bin.observed_rate * 100).toFixed(1)}%</span><span>{bin.count}</span><span>{Math.abs(bin.mean_confidence - bin.observed_rate).toFixed(3)}</span><i style={{ '--confidence': `${bin.mean_confidence * 100}%` }} /></div>)}</div><p className="precog-muted">Expected calibration error: {shipped.node_model.expected_calibration_error.toFixed(4)}. Lower is closer on this held-out scripted sample.</p></section>
      <section className="precog-section"><div className="precog-section-head"><div><p className="precog-eyebrow">NEW EXPERIMENT</p><h2>Run deterministic evaluation</h2></div></div><form className="precog-eval-form" onSubmit={evaluate}><label>Split seed<input type="number" min="-1000000" max="1000000" value={seed} onChange={(event) => setSeed(event.target.value)} /></label><label>Held-out fraction<select value={fraction} onChange={(event) => setFraction(event.target.value)}><option value="0.2">20%</option><option value="0.25">25%</option><option value="0.3">30%</option><option value="0.4">40%</option><option value="0.5">50%</option></select></label><button className="precog-button precog-button-primary" disabled={busy || role === 'viewer'}>{busy ? 'Evaluating…' : 'Run evaluation'}</button>{role === 'viewer' && <small>Analyst or admin access is required to run evaluations.</small>}</form>{experiment && <div className="precog-experiment-result"><b>{experiment.experiment_id} {experiment.cached ? '· CACHED' : '· COMPLETE'}</b><span>Seed {experiment.parameters.seed} · {experiment.runtime_ms} ms · {experiment.result.split.test_forecasts} held-out forecasts</span><p>Precision@1 {(experiment.result.node_model.precision_at_1 * 100).toFixed(2)}% · SE {(experiment.result.node_model.precision_at_1_std_error * 100).toFixed(2)} pp · Rule {(experiment.result.baseline_rule_based.precision_at_1 * 100).toFixed(2)}%</p></div>}<div className="precog-experiment-log"><h3>Recent experiments</h3>{experiments.slice(0, 5).map((item) => <div key={item.experiment_id}><b>{item.experiment_id}</b><span>seed {item.parameters.seed} · {(item.result.node_model.precision_at_1 * 100).toFixed(1)}% P@1</span></div>)}{!experiments.length && <p className="precog-muted">No experiments yet.</p>}</div></section></div>
      <section className="precog-section precog-profiles"><div className="precog-section-head"><div><p className="precog-eyebrow">PROFILE BREAKDOWN</p><h2>Held-out attacker styles</h2></div><span>scripted profiles</span></div><div className="precog-profile-grid">{Object.entries(report.by_profile || {}).map(([name, profile]) => <article key={name}><b>{name.replaceAll('-', ' ')}</b><strong>{(profile.precision_at_1 * 100).toFixed(1)}%</strong><span>{profile.forecasts} forecasts · SE {(profile.precision_at_1_std_error * 100).toFixed(1)} pp</span></article>)}</div></section>
      <ModelNote card={overview.model_card} />
      {overview.detection_report && <details className="precog-section precog-detection"><summary>Separate offline detector report</summary><p>{overview.detection_report.model}</p><span>Lab dataset: {overview.detection_report.dataset} · Precision {overview.detection_report.precision} · F1 {overview.detection_report.f1}</span><small>This is a separate offline CICIDS2017 experiment; it does not describe live NIDS performance.</small></details>}
    </>}
  </main>
}

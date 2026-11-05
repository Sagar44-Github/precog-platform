import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, PageFrame, PageHeader } from './shared.jsx'
import './help-about.css'

const shortcuts = [
  ['Ctrl / Cmd + K', 'Open the command palette'],
  ['Escape', 'Close the command palette or guided tour'],
  ['Tab / Shift + Tab', 'Move through controls in page order'],
  ['Enter / Space', 'Activate focused controls and map markers'],
]

const glossary = [
  ['Attack path', 'The ordered hosts the scripted replay compromised.'],
  ['Forecast', 'A ranked prediction of reachable hosts for the current simulated attack.'],
  ['Precision@1 / @3', 'Session-level forecast hit rates. They do not measure general model accuracy.'],
  ['Simulated weakness', 'Invented DEMO data used to rank hosts; no vulnerability scan is run.'],
  ['Time travel', 'Read-only snapshots of previous world versions. It never rewinds the live replay.'],
  ['Containment', 'A simulated state change that takes effect only after proposal and confirmation.'],
]

export default function HelpPage() {
  const navigate = useNavigate()
  const [tourDone, setTourDone] = useState(false)
  useEffect(() => { try { setTourDone(localStorage.getItem('precog-guided-tour-completed') === '1') } catch {} }, [])

  return <PageFrame className="help-about-page">
    <PageHeader eyebrow="REFERENCE / OPERATOR GUIDE" title="Help & walkthrough" description="A short route through the simulated response loop, page guides, keyboard shortcuts, and SOC terminology." actions={<Button type="button" onClick={() => navigate('/console/topology?tour=golden-path&step=0')}>{tourDone ? 'Restart guided tour' : 'Start guided tour'}</Button>} />
    <div className="help-simulation-note"><b>Simulation only.</b> The guided tour uses scripted events. It does not generate real traffic or contain a real host.</div>
    <section className="ops-card help-quickstart"><div className="ops-card-header"><div><h3>Golden Path quickstart</h3><p>Follow the same detect → forecast → propose → confirm → re-evaluate sequence as the demo rehearsal.</p></div><span className="help-card-tag">6 STEPS</span></div>
      <ol className="help-steps"><li><b>Start a replay.</b><span>Open Replay Studio or use the guided tour to start the deterministic Golden Path.</span></li><li><b>Review detection.</b><span>Open Alerts to see scripted packets labelled by the detector.</span></li><li><b>Inspect the prediction.</b><span>Open Forecasts and check the candidate list and explanation.</span></li><li><b>Propose a response.</b><span>In Containment, review the exact host list before confirming.</span></li><li><b>Re-evaluate.</b><span>Replay resumes, resolves the forecast, and reports the resulting path.</span></li><li><b>Review the record.</b><span>Use Replay Studio, Incidents, and Reports to inspect the finished session.</span></li></ol>
    </section>
    <div className="help-reference-grid">
      <section className="ops-card help-reference-card"><div className="ops-card-header"><div><h3>Keyboard shortcuts</h3><p>Navigation and dialog controls</p></div></div><dl className="help-shortcuts">{shortcuts.map(([key, description]) => <div key={key}><dt><kbd>{key}</kbd></dt><dd>{description}</dd></div>)}</dl></section>
      <section className="ops-card help-reference-card"><div className="ops-card-header"><div><h3>Operator links</h3><p>Open a workspace directly</p></div></div><nav className="help-links" aria-label="Operator workspace links"><button type="button" onClick={() => navigate('/console/topology')}>Topology explorer</button><button type="button" onClick={() => navigate('/replay')}>Replay Studio</button><button type="button" onClick={() => navigate('/containment')}>Containment</button><button type="button" onClick={() => navigate('/mobile')}>Mobile SOC</button></nav></section>
    </div>
    <section className="ops-card help-glossary"><div className="ops-card-header"><div><h3>Glossary</h3><p>Terms used throughout the simulated SOC</p></div></div><dl>{glossary.map(([term, definition]) => <div key={term}><dt>{term}</dt><dd>{definition}</dd></div>)}</dl></section>
  </PageFrame>
}

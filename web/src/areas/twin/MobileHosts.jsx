import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { LoadingState } from '../../shared/components.jsx'

export default function MobileHostsPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [topology, setTopology] = useState(null)
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    Promise.all([api.topology(), id ? api.host(id) : Promise.resolve(null)])
      .then(([map, item]) => { if (alive) { setTopology(map); setDetail(item) } })
      .catch((reason) => { if (alive) setError(reason.message || 'Could not load demo hosts.') })
    return () => { alive = false }
  }, [id])

  if (!topology && !error) return <div className="m-screen"><LoadingState /></div>
  if (error) return <div className="m-screen"><Link className="m-back" to="/mobile">‹ Mobile SOC</Link><p role="alert">{error}</p></div>

  if (detail) {
    const host = detail.host
    return <div className="m-screen">
      <button type="button" className="m-back" onClick={() => navigate('/mobile/hosts')}>‹ Back to hosts</button>
      <p className="m-caption m-mono">NETWORK TWIN · SIMULATED ASSET</p>
      <h1 className="m-title">{host.name}</h1>
      <section className="m-card"><div className="m-row"><span>{host.zone.toUpperCase()}</span><span>{host.state.toUpperCase()}</span></div><p>{host.role}</p><p className="m-caption m-mono">Criticality {Math.round(host.criticality * 100)}% · Estimated risk {host.risk}/10 · Exposure {host.exposure}</p></section>
      <section className="m-card"><h2>Services</h2>{host.services.length ? <ul>{host.services.map((service) => <li key={service}>{service}</li>)}</ul> : <p>No service markers.</p>}</section>
      <section className="m-card"><h2>Simulated weaknesses</h2>{host.weaknesses.map((item) => <article key={item.weakness_id}><b>{item.weakness_id} · {item.service}</b><p>{item.description}</p><span className="m-caption">Simulated demo data · CVSS {item.cvss}</span></article>)}</section>
      <section className="m-card"><h2>Related incidents</h2>{detail.incidents.length ? detail.incidents.map((incident) => <p key={incident.incident_id}><Link to={`/incidents/${incident.incident_id}`}>{incident.title}</Link> · {incident.status}</p>) : <p>No related incidents in the current or recorded simulation.</p>}</section>
      <section className="m-card"><h2>Related forecasts and actions</h2><p>{detail.forecasts.length} forecast records · {detail.actions.length} simulated actions</p></section>
    </div>
  }

  return <div className="m-screen">
    <p className="m-caption m-mono">NETWORK TWIN · SIX DEMO HOSTS</p>
    <h1 className="m-title">Hosts</h1>
    <p className="m-caption">Read-only inventory. Risk, exposure and weaknesses are estimates from the scripted demo network.</p>
    {topology.hosts.map((host) => <Link className="m-card m-host-card" key={host.host_id} to={`/mobile/hosts/${encodeURIComponent(host.host_id)}`}>
      <div className="m-row"><b>{host.name}</b><span>{host.state}</span></div>
      <p className="m-caption">{host.zone.toUpperCase()} · {host.services.length} services · estimated risk {host.risk}/10</p>
    </Link>)}
    <Link className="m-back" to="/mobile">Return to Mobile SOC</Link>
  </div>
}

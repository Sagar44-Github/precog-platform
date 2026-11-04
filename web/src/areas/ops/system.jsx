import { useCallback } from 'react'
import { api } from '../../shared/api.js'
import { Button, PageFrame, PageHeader, ResourceNotice, useResource } from './shared.jsx'

function Check({ name, value }) {
  return <div className="ops-module"><span>{name}</span><b className={value ? 'ops-check-ok' : 'ops-check-warn'}>{value ? 'Available' : 'Check'}</b></div>
}

export default function SystemPage() {
  const load = useCallback(() => api.system(), [])
  const { data, loading, error, refresh } = useResource(load, 'system-status')
  const modules = data ? Object.entries(data.modules) : []

  return <PageFrame>
    <PageHeader eyebrow="PLATFORM / RUNTIME INSPECTION" title="System health" description="Loaded modules, registration hooks, application versions, and the active simulation data mode." actions={<Button className="ops-button-secondary" type="button" onClick={refresh}>Refresh status</Button>} />
    <ResourceNotice loading={loading} error={error} data={data} onRetry={refresh} />
    {data && <>
      <div className="ops-stat-grid">
        <div className="ops-stat"><span>Backend status</span><strong className="ops-system-ok">{data.status.toUpperCase()}</strong></div>
        <div className="ops-stat"><span>Data mode</span><strong>{data.data_mode.toUpperCase()}</strong></div>
        <div className="ops-stat"><span>World version</span><strong>{data.world_version}</strong></div>
        <div className="ops-stat"><span>Registered hooks</span><strong>{data.hooks.length} / 6</strong></div>
      </div>
      <div className="ops-detail-grid">
        <section className="ops-card"><div className="ops-card-header"><div><h3>Role modules</h3><p>Registration status reported by the Flask add-on loader</p></div></div><div className="ops-card-body"><div className="ops-module-grid">
          {modules.map(([name, status]) => <div className="ops-module" key={name}><span>{name}</span><b className={status === 'registered' ? 'ops-check-ok' : 'ops-check-warn'}>{status}</b></div>)}
        </div></div></section>
        <section className="ops-card"><div className="ops-card-header"><div><h3>Runtime versions</h3><p>Read from the local process</p></div></div><div className="ops-card-body"><dl className="ops-detail-list">
          <div><dt>Python</dt><dd className="ops-mono">{data.versions.python}</dd></div>
          <div><dt>Flask</dt><dd className="ops-mono">{data.versions.flask}</dd></div>
          <div><dt>SQLite</dt><dd className="ops-mono">{data.versions.sqlite}</dd></div>
          <div><dt>Hooks</dt><dd>{data.hooks.join(', ') || 'None registered'}</dd></div>
        </dl></div></section>
      </div>
      <section className="ops-card ops-system-checks"><div className="ops-card-header"><div><h3>Readiness checks</h3><p>Local demo configuration and supporting files</p></div></div><div className="ops-card-body"><div className="ops-module-grid">
        <Check name="Contract validation" value={data.checks.contract_validation} />
        <Check name="Audit log path" value={data.checks.audit_log_available} />
      </div><p className="ops-simulated-note ops-system-note">This is a local simulation platform. No live packet capture, scanning, or network enforcement is performed.</p></div></section>
    </>}
  </PageFrame>
}

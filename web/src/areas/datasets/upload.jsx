import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../shared/api.js'
import { useAuth } from '../../shared/AuthContext.jsx'
import { Button, ErrorMessage, PageFrame, PageHeader } from '../ops/shared.jsx'
import './upload.css'

function suggested(columns, tests, fallback = '') {
  const byLower = new Map(columns.map((column) => [column.toLowerCase().replaceAll(/[^a-z0-9]/g, ''), column]))
  return tests.map((test) => byLower.get(test)).find(Boolean) || fallback
}

export default function DatasetUploadPage() {
  const { role } = useAuth()
  const [file, setFile] = useState(null)
  const [job, setJob] = useState(null)
  const [name, setName] = useState('')
  const [mapping, setMapping] = useState({})
  const [semantics, setSemantics] = useState('none')
  const [licenseAck, setLicenseAck] = useState(false)
  const [pseudonymize, setPseudonymize] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const preview = job?.preview
  const columns = preview?.columns || []
  const rawFormat = preview && preview.format !== 'pack-zip'

  useEffect(() => {
    if (!job || !['queued', 'building'].includes(job.state)) return undefined
    let alive = true
    const timer = window.setTimeout(async () => {
      try { const update = await api.uploadStatus(job.job_id); if (alive) setJob(update) }
      catch (reason) { if (alive) setError(reason.message || 'Could not refresh upload status.') }
    }, 700)
    return () => { alive = false; window.clearTimeout(timer) }
  }, [job])

  const available = useMemo(() => columns, [columns])

  async function inspect(event) {
    event.preventDefault()
    if (!file) { setError('Choose a pack ZIP, CSV, TSV, or JSON events file.'); return }
    if (!licenseAck) { setError('Confirm that you have rights to process this data locally.'); return }
    setBusy(true); setError(''); setJob(null)
    try {
      const result = await api.previewUpload(file)
      setJob(result)
      setName(result.preview?.pack_name || file.name.replace(/\.[^.]+$/, '').slice(0, 100))
      const cols = result.preview?.columns || []
      const timeColumn = suggested(cols, ['time', 'timestamp', 't', 'datetime'])
      const srcColumn = suggested(cols, ['srchost', 'source', 'src', 'sourceip', 'sourcecomputer'])
      const dstColumn = suggested(cols, ['dsthost', 'destination', 'dst', 'destinationip', 'destinationcomputer'])
      const labelColumn = suggested(cols, ['label', 'attack', 'class', 'category'])
      setMapping({ time_column: timeColumn, src_column: srcColumn, dst_column: dstColumn,
        ...(labelColumn ? { label_column: labelColumn } : {}) })
    } catch (reason) { setError(reason.message || 'File preview failed.') }
    finally { setBusy(false) }
  }

  async function build(event) {
    event.preventDefault()
    if (!job || !licenseAck) return
    setBusy(true); setError('')
    try {
      const result = await api.buildUpload(job.job_id, { name, mapping, compromise_semantics: semantics, pseudonymize, license_ack: licenseAck })
      setJob(result)
    } catch (reason) { setError(reason.message || 'Pack build could not start.') }
    finally { setBusy(false) }
  }

  async function cancel() {
    if (!job) return
    setBusy(true); setError('')
    try { setJob(await api.cancelUpload(job.job_id)) }
    catch (reason) { setError(reason.message || 'Upload could not be cancelled.') }
    finally { setBusy(false) }
  }

  return <PageFrame className="datasets-page upload-page">
    <PageHeader eyebrow="DATA / SECURE INGESTION" title="Upload a dataset" description="Import a validated pack or convert a small flow/event file into a local-only workspace. Uploads are size-capped, validated, pseudonymized by default, and never executed." actions={<Link className="ops-button ops-button-secondary" to="/datasets">Back to datasets</Link>} />
    {role !== 'admin' && <div className="upload-role-note" role="status">Dataset uploads are restricted to administrators. Your current role is read only here.</div>}
    <form className="upload-form" onSubmit={job?.state === 'preview' ? build : inspect}>
      {!job && <section className="upload-step"><span className="upload-step-index">01</span><div><h3>Select and inspect a file</h3><p>Accepted: validated pack ZIP, UTF-8 CSV/TSV, or a JSON array/object containing event rows. No PCAP or executable files.</p></div>
        <label className="upload-file-label">Dataset file<input type="file" accept=".zip,.csv,.tsv,.json,application/zip,text/csv,text/tab-separated-values,application/json" disabled={role !== 'admin' || busy} onChange={(event) => { setFile(event.target.files?.[0] || null); setJob(null); setError('') }} /><small>{file ? `${file.name} · ${file.size.toLocaleString()} bytes` : 'Local maximum 1 GiB; hosted maximum 50 MiB. Pack output is capped at 25 MiB.'}</small></label>
        <label className="upload-checkbox"><input type="checkbox" checked={licenseAck} disabled={role !== 'admin'} onChange={(event) => setLicenseAck(event.target.checked)} /><span>I have permission to process this file. I understand the source remains local and will not be redistributed.</span></label>
        <Button type="submit" disabled={role !== 'admin' || busy || !licenseAck}>{busy ? 'Inspecting…' : 'Inspect file'}</Button>
      </section>}

      {job && preview && <section className="upload-step"><span className="upload-step-index">02</span><div><h3>Review format and map columns</h3><p>Detected <b>{preview.format}</b>{preview.row_estimate != null ? ` · ${preview.row_estimate.toLocaleString()} rows` : ''}. Raw uploads are converted into a new local pack; the original temporary file is discarded after the job ends.</p></div>
        <div className="upload-preview-meta"><span>Upload size <b>{job.bytes_received.toLocaleString()} bytes</b></span><span>Configured limit <b>{job.size_limit.toLocaleString()} bytes</b></span>{preview.expanded_bytes != null && <span>Expanded pack <b>{preview.expanded_bytes.toLocaleString()} bytes</b></span>}</div>
        {preview.format === 'pack-zip' ? <p className="upload-honesty">Pack: {preview.pack_name || 'validated dataset pack'}. ZIP paths, links, entry count, compression ratio, content hash and pack contracts are checked before installation.</p> : <>
          <label>Workspace name<input value={name} maxLength={200} disabled={role !== 'admin' || busy} onChange={(event) => setName(event.target.value)} /></label>
          <div className="upload-mapping-grid">
            {[['time_column', 'Event time', true], ['src_column', 'Source host', true], ['dst_column', 'Destination host', true], ['label_column', 'Label column', false], ['zone_column', 'Zone column', false], ['protocol_column', 'Protocol', false], ['port_column', 'Destination port', false], ['bytes_column', 'Bytes', false]].map(([key, label, required]) => <label key={key}>{label}{required && <b aria-hidden="true"> *</b>}<select value={mapping[key] || ''} required={required} disabled={role !== 'admin' || busy} onChange={(event) => setMapping((current) => ({ ...current, [key]: event.target.value }))}><option value="">{required ? 'Choose a column' : 'Not mapped'}</option>{available.map((column) => <option value={column} key={column}>{column}</option>)}</select></label>)}
          </div>
          <label>Label semantics<select value={semantics} disabled={role !== 'admin' || busy || !mapping.label_column} onChange={(event) => setSemantics(event.target.value)}><option value="none">No compromise inference</option><option value="access-attempt">Access attempt · derived compromise estimate</option><option value="lateral-movement">Lateral movement · derived compromise estimate</option><option value="command-and-control">Command and control · derived estimate</option><option value="impact-only">Impact only · no compromise</option><option value="reconnaissance">Reconnaissance · no compromise</option></select><small>Imported rows do not create native routes. Forecasting remains unsupported without ordered compromise routes.</small></label>
          <label className="upload-checkbox"><input type="checkbox" checked={pseudonymize} disabled={role !== 'admin' || busy} onChange={(event) => setPseudonymize(event.target.checked)} /><span>Pseudonymize endpoint names (recommended). The preview shows at most five rows.</span></label>
          <div className="upload-sample-wrap"><table className="upload-sample"><caption>Sample rows (text only)</caption><thead><tr>{columns.slice(0, 8).map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{(preview.sample_rows || []).map((row, index) => <tr key={index}>{columns.slice(0, 8).map((column) => <td key={column}>{String(row[column] ?? '').slice(0, 120)}</td>)}</tr>)}</tbody></table></div>
        </>}
        <label className="upload-checkbox"><input type="checkbox" checked={licenseAck} disabled={role !== 'admin'} onChange={(event) => setLicenseAck(event.target.checked)} /><span>I have permission to process this file locally and accept responsibility for source terms.</span></label>
        <div className="upload-actions"><Button type="submit" disabled={role !== 'admin' || busy || !licenseAck}>{busy ? 'Starting build…' : 'Build and validate pack'}</Button><Button type="button" className="ops-button-secondary" disabled={busy || job.state !== 'preview'} onClick={cancel}>Cancel upload</Button></div>
      </section>}
    </form>

    {job && <section className="upload-job" aria-live="polite"><div className="upload-job-heading"><span>JOB {job.job_id}</span><b>{job.state.replaceAll('_', ' ').toUpperCase()}</b></div><p>{job.message}</p>{['queued', 'building'].includes(job.state) && <progress max="1" value={job.progress || 0} aria-label="Upload build progress" />}{job.pack_id && <p>Installed as <Link to={`/datasets/${encodeURIComponent(job.pack_id)}`}>{job.pack_id}</Link>. Select it from the workspace switcher to activate it.</p>}</section>}
    {error && <ErrorMessage message={error} />}
    <p className="dataset-honesty">Raw events are converted to a local-only pack; labels are not proof of compromise. Uploaded packs are not independently evaluated, and generated topology is an estimate. No uploaded data is executed.</p>
  </PageFrame>
}

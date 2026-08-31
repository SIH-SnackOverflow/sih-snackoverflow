import { useEffect, useMemo, useRef, useState } from 'react'

// During local development Vite proxies /api to FastAPI, avoiding browser CORS
// and IPv4/IPv6 localhost mismatches. Set VITE_API_URL for a deployed API.
const API_URL = import.meta.env.VITE_API_URL || ''
const OUTCOME_META = {
  PASS: { label: 'Ready to review', tone: 'pass', description: 'No configured issue was detected.' },
  POSSIBLE_VIOLATION: { label: 'Possible violation', tone: 'fail', description: 'One or more declarations need human attention.' },
  NEEDS_REVIEW: { label: 'Needs review', tone: 'review', description: 'The image did not provide enough reliable evidence.' },
  EXEMPT: { label: 'Exempt', tone: 'exempt', description: 'The package matches a configured exemption.' },
}
const DISPLAY_STATUS = { PASS: 'Pass', POSSIBLE_VIOLATION: 'Possible violation', NEEDS_REVIEW: 'Needs review', EXEMPT: 'Exempt', SKIPPED: 'Not assessed' }

function Badge({ status }) {
  return <span className={`badge ${OUTCOME_META[status]?.tone || 'skipped'}`}>{DISPLAY_STATUS[status] || status}</span>
}

function App() {
  const inputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState('')
  const [report, setReport] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('findings')

  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview])

  function chooseFile(nextFile) {
    if (!nextFile) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(nextFile.type)) {
      setError('Choose a JPEG, PNG, or WebP image.'); return
    }
    if (nextFile.size > 10 * 1024 * 1024) {
      setError('Choose an image smaller than 10 MB.'); return
    }
    if (preview) URL.revokeObjectURL(preview)
    setFile(nextFile); setPreview(URL.createObjectURL(nextFile)); setReport(null); setError('')
  }

  async function analyze() {
    if (!file) return
    setLoading(true); setError(''); setReport(null)
    try {
      const formData = new FormData(); formData.append('image', file)
      const response = await fetch(`${API_URL}/api/reviews`, { method: 'POST', body: formData })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Analysis failed. Try again.')
      setReport(data)
    } catch (err) {
      setError(err.message || 'Could not reach the review service.')
    } finally { setLoading(false) }
  }

  const visibleFindings = useMemo(() => (report?.findings || []).filter(item => activeTab === 'findings' || item.outcome === activeTab), [report, activeTab])
  const meta = report && (OUTCOME_META[report.outcome] || OUTCOME_META.NEEDS_REVIEW)

  return <main>
    <nav><div className="brand"><span className="brand-mark">L</span><span>LabelLens</span></div><div className="nav-note"><span className="dot" /> AI-assisted label review</div></nav>
    <section className="hero">
      <p className="eyebrow">Package compliance workspace</p>
      <h1>Turn a label photo into a <em>clearer review.</em></h1>
      <p className="subhead">Upload a product label to extract visible declarations and check them against configured rules. Results are a review aid—not legal advice.</p>
    </section>

    <section className="workspace">
      <div className="upload-panel">
        <div className="panel-heading"><div><p className="eyebrow">01 / Input</p><h2>Package label image</h2></div>{file && <button className="text-button" onClick={() => inputRef.current?.click()}>Replace</button>}</div>
        <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" onChange={e => chooseFile(e.target.files?.[0])} hidden />
        {!preview ? <button className="dropzone" onClick={() => inputRef.current?.click()} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); chooseFile(e.dataTransfer.files?.[0]) }}><span className="upload-icon">↑</span><strong>Drop your label image here</strong><small>or browse files · JPG, PNG or WebP · up to 10 MB</small></button> : <div className="image-preview"><img src={preview} alt="Selected package label" /><div className="file-info"><span>{file.name}</span><small>{(file.size / 1024 / 1024).toFixed(2)} MB</small></div></div>}
        <button className="primary" disabled={!file || loading} onClick={analyze}>{loading ? <><span className="spinner" /> Reading label…</> : 'Analyze label'}</button>
        {error && <div className="error">{error}</div>}
        <p className="privacy">Images are sent only for this analysis and are not retained by this service.</p>
      </div>

      <div className="results-panel">
        {!report ? <div className="empty-state"><div className="empty-icon">⌁</div><p className="eyebrow">02 / Results</p><h2>Your review will appear here</h2><p>We’ll organize extracted facts, checks, and follow-up items into one focused report.</p></div> : <>
          <div className="result-header"><div><p className="eyebrow">02 / Review outcome</p><h2>{meta.label}</h2><p>{meta.description}</p></div><Badge status={report.outcome} /></div>
          <div className="score-grid"><Metric label="Passed" value={report.counts.PASS} type="pass" /><Metric label="Needs review" value={report.counts.NEEDS_REVIEW} type="review" /><Metric label="Possible issues" value={report.counts.POSSIBLE_VIOLATION} type="fail" /><Metric label="Not assessed" value={report.counts.SKIPPED} type="skipped" /></div>
          <div className="tabs">{[['findings', 'All checks'], ['POSSIBLE_VIOLATION', 'Issues'], ['NEEDS_REVIEW', 'Review'], ['PASS', 'Passed']].map(([id, label]) => <button key={id} className={activeTab === id ? 'active' : ''} onClick={() => setActiveTab(id)}>{label}</button>)}</div>
          <div className="finding-list">{visibleFindings.map((finding, index) => <article className="finding" key={`${finding.rule_id}-${index}`}><div className="finding-top"><span className="rule">{finding.rule_id}</span><Badge status={finding.outcome} /></div><p>{finding.message}</p>{finding.observed && <code>{typeof finding.observed === 'object' ? JSON.stringify(finding.observed) : finding.observed}</code>}</article>)}{visibleFindings.length === 0 && <p className="no-findings">Nothing in this category.</p>}</div>
          <details className="extraction"><summary>View extracted label data</summary><pre>{JSON.stringify(report.extraction, null, 2)}</pre></details>
        </>}
      </div>
    </section>
    <footer>LabelLens evaluates configured checks only. Always have findings reviewed by a qualified professional.</footer>
  </main>
}

function Metric({ label, value, type }) { return <div className={`metric ${type}`}><strong>{value ?? 0}</strong><span>{label}</span></div> }
export default App

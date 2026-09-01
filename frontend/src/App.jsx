import { useEffect, useMemo, useRef, useState } from 'react'

// During local development Vite proxies /api to FastAPI.
// Set VITE_API_URL for a deployed API.
const API_URL = import.meta.env.VITE_API_URL || ''

const OUTCOME_META = {
  PASS: {
    label: 'Ready to review',
    tone: 'pass',
    description: 'No configured issue was detected.',
  },
  POSSIBLE_VIOLATION: {
    label: 'Possible violation',
    tone: 'fail',
    description: 'One or more declarations need human attention.',
  },
  NEEDS_REVIEW: {
    label: 'Needs review',
    tone: 'review',
    description: 'The image did not provide enough reliable evidence.',
  },
  EXEMPT: {
    label: 'Exempt',
    tone: 'exempt',
    description: 'The package matches a configured exemption.',
  },
}

const DISPLAY_STATUS = {
  PASS: 'Pass',
  POSSIBLE_VIOLATION: 'Possible violation',
  NEEDS_REVIEW: 'Needs review',
  EXEMPT: 'Exempt',
  SKIPPED: 'Not assessed',
}

const RULE_DETAILS = {
  // MANDATORY DECLARATIONS
  'MD-01': {
    title: 'Manufacturer/Packer details',
    requirement: 'Rule 6(1)(a): Manufacturer or packer name and complete postal address must be visible.',
  },
  'MD-02': {
    title: 'Importer & Origin',
    requirement: 'Rule 6(1)(a) & (b): For imported goods, the name/address of the importer and the country of origin must be declared.',
  },
  'MD-03': {
    title: 'Generic commodity name',
    requirement: 'Rule 6(1)(b): The common or generic name of the commodity must be clearly declared.',
  },
  'MD-04': {
    title: 'Standard Net Quantity',
    requirement: 'Rule 6(1)(c): Net quantity must be declared in recognized standard units (g, kg, ml, l, m, or count).',
  },
  'MD-05': {
    title: 'Manufacture / Packing date',
    requirement: 'Rule 6(1)(d): The month and year of manufacture, packing, or import must be clearly stated.',
  },
  'MD-06': {
    title: 'Best-before / Use-by date',
    requirement: 'Rule 6(1)(d) Proviso: For commodities that may become unfit for consumption, the best-before or use-by date is required.',
  },
  'MD-07': {
    title: 'MRP declaration',
    requirement: 'Rule 6(1)(e): Maximum Retail Price (MRP) must be declared and include the phrase "inclusive of all taxes".',
  },
  'MD-08': {
    title: 'Consumer-care information',
    requirement: 'Rule 6(1)(f): Name, address, telephone number, and email of the person/office for consumer complaints must be present.',
  },
  'MD-09': {
    title: 'Declaration language',
    requirement: 'Rule 9(1): All mandatory declarations must be in Hindi (Devanagari) or English.',
  },
  'MD-10': {
    title: 'Unit Sale Price (USP)',
    requirement: 'Rule 6(1)(g): Unit Sale Price must be declared on every package (e.g., Rs. per g or Rs. per ml).',
  },

  // VIOLATIONS / FORMATTING
  'VIO-01': {
    title: 'Non-standard count units',
    requirement: 'Rules prohibit the use of non-standard units like dozen, score, or gross for quantity declarations.',
  },
  'VIO-02': {
    title: 'Sub-threshold Unit Usage',
    requirement: 'Quantities less than 1 kg/L/m must be expressed in g/ml/cm to prevent consumer confusion.',
  },
  'VIO-03': {
    title: 'Misleading modifiers',
    requirement: 'Modifiers like "minimum", "approximately", or "about" are prohibited in net quantity declarations.',
  },
  'VIO-04': {
    title: 'MRP Sticker Overwriting',
    requirement: 'Rule 18(2): No person shall alter or mask the MRP printed by the manufacturer by using a sticker.',
  },
  'VIO-05': {
    title: 'Schedule II Standard Sizes',
    requirement: 'Specific commodities (tea, biscuits, etc.) must be packed in sizes rationalized under Schedule II.',
  },

  // TYPOGRAPHY / PLACEMENT
  'TYP-01': {
    title: 'Principal Display Panel (PDP)',
    requirement: 'Rule 7: Mandatory declarations must be grouped together on the Principal Display Panel.',
  },
  'TYP-02': {
    title: 'Numeral Font Height',
    requirement: 'Schedule I: Numerals in declarations must meet minimum height requirements based on the display area.',
  },
  'TYP-03': {
    title: 'Character Aspect Ratio',
    requirement: 'Rule 8: Numerals and letters must have a width of at least one-third of their height.',
  },
  'TYP-04': {
    title: 'Legibility & Contrast',
    requirement: 'Rule 9(2): Declarations must be clearly legible and provide distinct contrast with the background.',
  },
  'TYP-05': {
    title: 'Surrounding Clear Space',
    requirement: 'Rule 9(3): Net quantity numerals must have adequate clear space to avoid being obscured by other print.',
  },

  // EXEMPTIONS & SPECIAL CASES
  'EX-01': {
    title: 'Large Package Exemption',
    requirement: 'Rule 3(a): Packages larger than 25kg/25L are exempt (except cement/fertilizer up to 50kg).',
  },
  'EX-02': {
    title: 'Consignment Exemption',
    requirement: 'Manual verification required for specialized industrial wholesale distributor consignments.',
  },
  'EX-03': {
    title: 'Industrial/Institutional Exemption',
    requirement: 'Rule 3(b): Packages sold exclusively to industrial or institutional consumers are exempt.',
  },
  'EX-04': {
    title: 'Specialty Exemption',
    requirement: 'Rule 3(c/d): Exemptions for fast food packed by hotels or drug formulations under DPCO.',
  },
};

function Badge({ status }) {
  return (
    <span
      className={`badge ${
        OUTCOME_META[status]?.tone || 'skipped'
      }`}
    >
      {DISPLAY_STATUS[status] || status}
    </span>
  )
}

function Metric({ label, value, type }) {
  return (
    <div className={`metric ${type}`}>
      <strong>{value ?? 0}</strong>
      <span>{label}</span>
    </div>
  )
}

/* =========================================================
   PDP VISUALIZER
   ========================================================= */

function PDPVisualizer({ image, evidence }) {
  if (!image) {
    return (
      <div className="empty-state">
        <div className="empty-icon">▧</div>

        <p className="eyebrow">PDP visualizer</p>

        <h2>No image available</h2>

        <p>
          Upload and analyze a package label first.
        </p>
      </div>
    )
  }

  const validEvidence = (evidence || []).filter(
    (item) =>
      Array.isArray(item.box_2d) &&
      item.box_2d.length === 4,
  )

  return (
    <section className="pdp-section">
      <div className="result-header">
        <div>
          <p className="eyebrow">
            PDP visualizer
          </p>

          <h2>Evidence map</h2>

          <p>
            Highlighted regions show where the
            extractor found visible declarations.
          </p>
        </div>
      </div>

      <div className="pdp-layout">
        <div className="pdp-image-container">
  <div className="pdp-image-wrapper">
    <img
      src={image}
      alt="Package label with detected evidence"
      className="pdp-image"
    />

    {validEvidence.map((item, index) => {
      const [
        ymin,
        xmin,
        ymax,
        xmax,
      ] = item.box_2d

      const top = `${ymin / 10}%`
      const left = `${xmin / 10}%`
      const width =
        `${(xmax - xmin) / 10}%`
      const height =
        `${(ymax - ymin) / 10}%`

      return (
        <div
          key={`${item.field}-${index}`}
          className="evidence-box"
          style={{
            top,
            left,
            width,
            height,
          }}
          title={`${item.field}: ${item.text}`}
        >
          <span className="evidence-label">
            {item.field}
          </span>
        </div>
      )
    })}
  </div>
</div>

        <div className="pdp-legend">
          <p className="eyebrow">
            Detected evidence
          </p>

          {validEvidence.length === 0 ? (
            <p className="no-findings">
              No visual evidence boxes were returned.
            </p>
          ) : (
            validEvidence.map(
              (item, index) => (
                <article
                  className="legend-item"
                  key={`${item.field}-${index}`}
                >
                  <span className="legend-number">
                    {index + 1}
                  </span>

                  <div>
                    <strong>
                      {item.field}
                    </strong>

                    <p>
                      {item.text ||
                        'No text detected'}
                    </p>

                    <span
                      className={`confidence ${
                        item.confidence ||
                        'low'
                      }`}
                    >
                      {item.confidence ||
                        'unknown'}
                    </span>
                  </div>
                </article>
              ),
            )
          )}
        </div>
      </div>

      <div className="pdp-note">
        <strong>Evidence visualization</strong>

        <p>
          The highlighted regions represent
          Gemini's normalized evidence boxes.
          They are visual references only and
          do not represent physical millimetre
          measurements.
        </p>
      </div>
    </section>
  )
}

/* =========================================================
   EXTRACTOR / EVIDENCE VIEW
   ========================================================= */

function EvidenceView({
  extraction,
  image,
}) {
  if (!extraction) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          ⌁
        </div>

        <p className="eyebrow">
          Evidence
        </p>

        <h2>No extraction yet</h2>

        <p>
          Analyze a package label first to
          view extracted declarations.
        </p>
      </div>
    )
  }

  const fields = [
    [
      'Manufacturer',
      extraction.manufacturer?.name,
    ],
    [
      'Generic name',
      extraction.generic_name,
    ],
    [
      'Net quantity',
      extraction.net_quantity,
    ],
    [
      'Manufacture date',
      extraction.manufacture_month_year,
    ],
    [
      'Best before / use by',
      extraction.best_before_or_use_by,
    ],
    [
      'MRP declaration',
      extraction.mrp_declaration,
    ],
    [
      'Country of origin',
      extraction.country_of_origin,
    ],
  ]

  return (
    <section className="evidence-view">
      {/* PDP VISUALIZER */}

      <PDPVisualizer
        image={image}
        evidence={extraction.evidence}
      />

      {/* EXTRACTED INFORMATION */}

      <div className="result-header evidence-heading">
        <div>
          <p className="eyebrow">
            Extractor declaration
          </p>

          <h2>
            Extracted label information
          </h2>

          <p>
            Information below was extracted
            from visible image evidence. The
            extractor does not make legal
            conclusions.
          </p>
        </div>
      </div>

      <div className="declaration-grid">
        {fields.map(
          ([label, value]) => (
            <article
              className="declaration-card"
              key={label}
            >
              <span>{label}</span>

              <strong>
                {value ||
                  'Not reliably detected'}
              </strong>
            </article>
          ),
        )}
      </div>

      {/* CONFIDENCE */}

      <div className="confidence-section">
        <p className="eyebrow">
          Evidence confidence
        </p>

        {(extraction.evidence || []).map(
          (item, index) => (
            <article
              className="evidence-item"
              key={`${item.field}-${index}`}
            >
              <div>
                <strong>
                  {item.field}
                </strong>

                <p>
                  {item.text ||
                    'No text detected'}
                </p>
              </div>

              <span
                className={`confidence ${
                  item.confidence ||
                  'low'
                }`}
              >
                {item.confidence ||
                  'unknown'}
              </span>
            </article>
          ),
        )}

        {(!extraction.evidence ||
          extraction.evidence.length === 0) && (
          <p className="no-findings">
            No evidence entries were
            returned.
          </p>
        )}
      </div>

      {/* FULL TRANSCRIPTION */}

      <details className="extraction">
        <summary>
          View full transcription
        </summary>

        <pre>
          {extraction.full_text ||
            'No transcription available.'}
        </pre>
      </details>

      {/* AI NOTICE */}

      <div className="extractor-notice">
        <strong>
          AI-assisted extraction
        </strong>

        <p>
          Extracted information is based on
          visible image evidence. Unclear
          information may require human
          verification.
        </p>
      </div>
    </section>
  )
}

/* =========================================================
   MAIN APP
   ========================================================= */

function App() {
  const inputRef = useRef(null)

  const [file, setFile] =
    useState(null)

  const [preview, setPreview] =
    useState('')

  const [report, setReport] =
    useState(null)

  const [error, setError] =
    useState('')

  const [loading, setLoading] =
    useState(false)

  const [activeTab, setActiveTab] =
    useState('findings')

  const [activePage, setActivePage] =
    useState('inspect')

  const [showOfficer, setShowOfficer] =
    useState(false)

  const [officer, setOfficer] =
  useState({
    name: '',
    id: '',
    jurisdiction: '',
  })

const [history, setHistory] =
  useState(() => {
    try {
      return JSON.parse(
        localStorage.getItem(
          'labellens_history',
        ) || '[]',
      )
    } catch {
      return []
    }
  })

useEffect(() => {
  return () => {
    if (preview) {
      URL.revokeObjectURL(preview)
    }
  }
}, [preview])

  function chooseFile(nextFile) {
    if (!nextFile) return

    if (
      ![
        'image/jpeg',
        'image/png',
        'image/webp',
      ].includes(nextFile.type)
    ) {
      setError(
        'Choose a JPEG, PNG, or WebP image.',
      )
      return
    }

    if (
      nextFile.size >
      10 * 1024 * 1024
    ) {
      setError(
        'Choose an image smaller than 10 MB.',
      )
      return
    }

    if (preview) {
      URL.revokeObjectURL(preview)
    }

    setFile(nextFile)

    setPreview(
      URL.createObjectURL(nextFile),
    )

    setReport(null)
    setError('')
    setActivePage('inspect')
  }

  async function analyze() {
    if (!file) return

    setLoading(true)
    setError('')
    setReport(null)

    try {
      const formData =
        new FormData()

      formData.append(
        'image',
        file,
      )

      const response =
        await fetch(
          `${API_URL}/api/reviews`,
          {
            method: 'POST',
            body: formData,
          },
        )

      const data =
        await response.json()

      if (!response.ok) {
        throw new Error(
          data.detail ||
            'Analysis failed. Try again.',
        )
      }

      setReport(data)

const inspection = {
  id: `LL-${Date.now()}`,
  date: new Date().toISOString(),
  filename: file.name,
  officer: officer.name || 'Not provided',
  officerId: officer.id || 'Not provided',
  jurisdiction:
    officer.jurisdiction || 'Not provided',
  outcome: data.outcome,
  counts: data.counts,
  extraction: data.extraction,
}

setHistory((previous) => {
  const updated = [
    inspection,
    ...previous,
  ].slice(0, 25)

  localStorage.setItem(
    'labellens_history',
    JSON.stringify(updated),
  )

  return updated
})

setActivePage('inspect')
    } catch (err) {
      setError(
        err.message ||
          'Could not reach the review service.',
      )
    } finally {
      setLoading(false)
    }
  }

  const visibleFindings =
    useMemo(
      () =>
        (
          report?.findings ||
          []
        ).filter(
          (item) =>
            activeTab ===
              'findings' ||
            item.outcome ===
              activeTab,
        ),
      [report, activeTab],
    )

  const meta =
    report &&
    (OUTCOME_META[
      report.outcome
    ] ||
      OUTCOME_META.NEEDS_REVIEW)

  return (
    <main>
      {/* ================= NAVIGATION ================= */}

      <nav>
        <div className="brand">
          <span className="brand-mark">
            L
          </span>

          <span>
            LabelLens
          </span>
        </div>

        <div className="nav-links">
          {[
            ['inspect', 'Inspect'],
            ['findings', 'Findings'],
            ['evidence', 'Evidence'],
            ['dossier', 'Dossier'],
            ['history', 'History'],
          ].map(
            ([id, label]) => (
              <button
                key={id}
                className={
                  activePage === id
                    ? 'nav-link active'
                    : 'nav-link'
                }
                onClick={() =>
                  setActivePage(id)
                }
              >
                {label}
              </button>
            ),
          )}
        </div>

        <div className="nav-actions">
          <div className="nav-note">
            <span className="dot" />
            AI-assisted label review
          </div>

          <button
            className="officer-button"
            onClick={() =>
              setShowOfficer(
                !showOfficer,
              )
            }
          >
            <span className="officer-icon">
              ○
            </span>

            Officer
          </button>
        </div>
      </nav>

      {/* ================= OFFICER ================= */}

      {showOfficer && (
        <section className="officer-panel">
          <div className="officer-panel-header">
            <div>
              <p className="eyebrow">
                Inspection details
              </p>

              <h3>
                Inspection Officer
              </h3>
            </div>

            <button
              className="text-button"
              onClick={() =>
                setShowOfficer(
                  false,
                )
              }
            >
              Close
            </button>
          </div>

          <div className="officer-fields">
            <label>
              Officer name

              <input
                type="text"
                value={
                  officer.name
                }
                onChange={(e) =>
                  setOfficer({
                    ...officer,
                    name:
                      e.target.value,
                  })
                }
                placeholder="Enter officer name"
              />
            </label>

            <label>
              Officer ID

              <input
                type="text"
                value={
                  officer.id
                }
                onChange={(e) =>
                  setOfficer({
                    ...officer,
                    id:
                      e.target.value,
                  })
                }
                placeholder="e.g. LM-INSP-001"
              />
            </label>

            <label>
              Jurisdiction

              <input
                type="text"
                value={
                  officer.jurisdiction
                }
                onChange={(e) =>
                  setOfficer({
                    ...officer,
                    jurisdiction:
                      e.target.value,
                  })
                }
                placeholder="Inspection jurisdiction"
              />
            </label>
          </div>
        </section>
      )}

      {/* ================= INSPECT ================= */}

      {activePage === 'inspect' && (
        <>
          <section className="hero">
            <p className="eyebrow">
              Package compliance workspace
            </p>

            <h1>
              Turn a label photo into a{' '}
              <em>
                clearer review.
              </em>
            </h1>

            <p className="subhead">
              Upload a product label to
              extract visible declarations
              and check them against
              configured rules. Results are
              a review aid—not legal advice.
            </p>
          </section>

          <section className="workspace">
            {/* UPLOAD */}

            <div className="upload-panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">
                    01 / Input
                  </p>

                  <h2>
                    Package label image
                  </h2>
                </div>

                {file && (
                  <button
                    className="text-button"
                    onClick={() =>
                      inputRef.current?.click()
                    }
                  >
                    Replace
                  </button>
                )}
              </div>

              <input
                ref={inputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(e) =>
                  chooseFile(
                    e.target.files?.[0],
                  )
                }
                hidden
              />

              {!preview ? (
                <button
                  className="dropzone"
                  onClick={() =>
                    inputRef.current?.click()
                  }
                  onDragOver={(e) =>
                    e.preventDefault()
                  }
                  onDrop={(e) => {
                    e.preventDefault()

                    chooseFile(
                      e.dataTransfer.files?.[0],
                    )
                  }}
                >
                  <span className="upload-icon">
                    ↑
                  </span>

                  <strong>
                    Drop your label image here
                  </strong>

                  <small>
                    or browse files · JPG, PNG
                    or WebP · up to 10 MB
                  </small>
                </button>
              ) : (
                <div className="image-preview">
                  <img
                    src={preview}
                    alt="Selected package label"
                  />

                  <div className="file-info">
                    <span>
                      {file.name}
                    </span>

                    <small>
                      {(
                        file.size /
                        1024 /
                        1024
                      ).toFixed(2)}{' '}
                      MB
                    </small>
                  </div>
                </div>
              )}

              <button
                className="primary"
                disabled={
                  !file || loading
                }
                onClick={analyze}
              >
                {loading ? (
                  <>
                    <span className="spinner" />
                    Reading label…
                  </>
                ) : (
                  'Analyze label'
                )}
              </button>

              {error && (
                <div className="error">
                  {error}
                </div>
              )}

              <p className="privacy">
                Images are sent only for this
                analysis and are not retained
                by this service.
              </p>
            </div>

            {/* RESULTS */}

            <div className="results-panel">
              {!report ? (
                <div className="empty-state">
                  <div className="empty-icon">
                    ⌁
                  </div>

                  <p className="eyebrow">
                    02 / Results
                  </p>

                  <h2>
                    Your review will appear
                    here
                  </h2>

                  <p>
                    We’ll organize extracted
                    facts, checks, and
                    follow-up items into one
                    focused report.
                  </p>
                </div>
              ) : (
                <>
                  <div className="result-header">
                    <div>
                      <p className="eyebrow">
                        02 / Review outcome
                      </p>

                      <h2>
                        {meta.label}
                      </h2>

                      <p>
                        {meta.description}
                      </p>
                    </div>

                    <Badge
                      status={
                        report.outcome
                      }
                    />
                  </div>

                  <div className="score-grid">
                    <Metric
                      label="Passed"
                      value={
                        report.counts
                          .PASS
                      }
                      type="pass"
                    />

                    <Metric
                      label="Needs review"
                      value={
                        report.counts
                          .NEEDS_REVIEW
                      }
                      type="review"
                    />

                    <Metric
                      label="Issues"
                      value={
                        report.counts
                          .POSSIBLE_VIOLATION
                      }
                      type="fail"
                    />

                    <Metric
                      label="Exempt"
                      value={
                        report.counts
                          .EXEMPT
                      }
                      type="exempt"
                    />

                    <Metric
                      label="Not assessed"
                      value={
                        report.counts
                          .SKIPPED
                      }
                      type="skipped"
                    />
                  </div>

                  <div className="tabs">
                    {[
                      [
                        'findings',
                        'All checks',
                      ],
                      [
                        'POSSIBLE_VIOLATION',
                        'Issues',
                      ],
                      [
                        'NEEDS_REVIEW',
                        'Review',
                      ],
                      [
                        'EXEMPT',
                        'Exemptions',
                      ],
                      [
                        'PASS',
                        'Passed',
                      ],
                    ].map(
                      ([id, label]) => (
                        <button
                          key={id}
                          className={
                            activeTab ===
                            id
                              ? 'active'
                              : ''
                          }
                          onClick={() =>
                            setActiveTab(
                              id,
                            )
                          }
                        >
                          {label}
                        </button>
                      ),
                    )}
                  </div>

                  <div className="finding-list">
                    {visibleFindings.map(
                      (
                        finding,
                        index,
                      ) => (
                        <article
                          className="finding"
                          key={`${finding.rule_id}-${index}`}
                        >
                          <div className="finding-top">
                            <span className="rule">
                              {
                                finding.rule_id
                              }
                            </span>

                            <Badge
                              status={
                                finding.outcome
                              }
                            />
                          </div>

                          <p>
                            {
                              finding.message
                            }
                          </p>

                          {finding.observed && (
                            <code>
                              {typeof finding.observed ===
                              'object'
                                ? JSON.stringify(
                                    finding.observed,
                                    null,
                                    2,
                                  )
                                : finding.observed}
                            </code>
                          )}
                        </article>
                      ),
                    )}

                    {visibleFindings.length ===
                      0 && (
                      <p className="no-findings">
                        Nothing in this
                        category.
                      </p>
                    )}
                  </div>

                  <details className="extraction">
                    <summary>
                      View extracted label
                      data
                    </summary>

                    <pre>
                      {JSON.stringify(
                        report.extraction,
                        null,
                        2,
                      )}
                    </pre>
                  </details>
                </>
              )}
            </div>
          </section>
        </>
      )}

      {/* ================= EVIDENCE ================= */}

      {activePage === 'evidence' && (
        <section className="workspace">
          <div className="results-panel evidence-full">
            <EvidenceView
              extraction={
                report?.extraction
              }
              image={preview}
            />
          </div>
        </section>
      )}

     {/* ================= FINDINGS ================= */}

{/* ================= FINDINGS ================= */}

{activePage === 'findings' && (
  <section className="workspace">
    <div className="results-panel evidence-full">

      {!report ? (
        <div className="empty-state">
          <div className="empty-icon">
            ⚖
          </div>

          <p className="eyebrow">
            Regulatory findings
          </p>

          <h2>
            No inspection report yet
          </h2>

          <p>
            Analyze a package label from
            the Inspect page to view its
            findings.
          </p>
        </div>
      ) : (
        <>
          <div className="result-header">
            <div>
              <p className="eyebrow">
                Regulatory assessment
              </p>

              <h2>
                Findings & checks
              </h2>

              <p>
                Each result below is generated
                from the configured deterministic
                compliance rules.
              </p>
            </div>

            <Badge
              status={report.outcome}
            />
          </div>

          <div className="finding-list findings-page-list">

            {report.findings?.map(
              (finding, index) => {

                const detail =
                  RULE_DETAILS[
                    finding.rule_id
                  ]

                return (
                  <article
                    className="regulatory-card"
                    key={`${finding.rule_id}-${index}`}
                  >

                    {/* HEADER */}

                    <div className="regulatory-card-header">

                      <div>
                        <span className="rule">
                          {finding.rule_id}
                        </span>

                        <h3>
                          {detail?.title ||
                            'Configured compliance check'}
                        </h3>
                      </div>

                      <Badge
                        status={
                          finding.outcome
                        }
                      />

                    </div>

                    {/* REQUIREMENT */}

                    <div className="regulatory-block">

                      <span>
                        Requirement
                      </span>

                      <p>
                        {detail?.requirement ||
                          'Requirement configured in the rule engine.'}
                      </p>

                    </div>

                    {/* OBSERVED */}

                    <div className="regulatory-block">

                      <span>
                        Observed
                      </span>

                      {finding.observed !==
                      null &&
                      finding.observed !==
                      undefined ? (
                        <code>
                          {typeof finding.observed ===
                          'object'
                            ? JSON.stringify(
                                finding.observed,
                                null,
                                2,
                              )
                            : String(
                                finding.observed,
                              )}
                        </code>
                      ) : (
                        <p className="muted">
                          No direct observation
                          returned.
                        </p>
                      )}

                    </div>

                    {/* ENGINE MESSAGE */}

                    <div className="regulatory-block">

                      <span>
                        Assessment
                      </span>

                      <p>
                        {finding.message}
                      </p>

                    </div>

                  </article>
                )
              },
            )}

          </div>

          <div className="extractor-notice">
            <strong>
              About these checks
            </strong>

            <p>
              These findings come from the
              configured deterministic rule
              engine. A PASS indicates that the
              configured check was satisfied;
              NEEDS REVIEW indicates that the
              available image evidence was
              insufficient; POSSIBLE VIOLATION
              indicates that the configured
              rule positively detected an issue.
            </p>
          </div>
        </>
      )}

    </div>
  </section>
)}

      {/* ================= DOSSIER ================= */}

      {/* ================= DOSSIER ================= */}

{activePage === 'dossier' && (
  <section className="workspace">
    <div className="results-panel evidence-full dossier-page">

      <div className="result-header dossier-header">
  <div>
    <p className="eyebrow">
      Digital inspection dossier
    </p>

    <h2>
      Inspection record
    </h2>

    <p>
      Consolidated record of officer details,
      extracted declarations, evidence, and
      regulatory findings.
    </p>
  </div>

  <div className="dossier-header-actions">
    {report && (
      <Badge status={report.outcome} />
    )}

    {report && (
      <button
        className="primary dossier-pdf-button"
        onClick={() => window.print()}
      >
        Generate PDF
      </button>
    )}
  </div>
</div>

      {!report ? (
        <div className="empty-state">
          <div className="empty-icon">
            ▣
          </div>

          <p className="eyebrow">
            Inspection dossier
          </p>

          <h2>
            No inspection report yet
          </h2>

          <p>
            Analyze a package label first. The
            completed inspection information will
            appear here.
          </p>

          <button
            className="primary dossier-action"
            onClick={() =>
              setActivePage('inspect')
            }
          >
            Start inspection
          </button>
        </div>
      ) : (
        <div className="dossier-content">

          {/* INSPECTION INFORMATION */}

          <section className="dossier-section">
            <p className="eyebrow">
              01 / Inspection information
            </p>

            <div className="dossier-info-grid">

              <div className="dossier-info-card">
                <span>Inspection ID</span>
                <strong>
                  LL-{new Date()
                    .toISOString()
                    .slice(0, 10)
                    .replaceAll('-', '')}
                </strong>
              </div>

              <div className="dossier-info-card">
                <span>Date</span>
                <strong>
                  {new Date().toLocaleDateString(
                    'en-IN',
                    {
                      day: '2-digit',
                      month: 'short',
                      year: 'numeric',
                    },
                  )}
                </strong>
              </div>

              <div className="dossier-info-card">
                <span>Officer</span>
                <strong>
                  {officer.name ||
                    'Not provided'}
                </strong>
              </div>

              <div className="dossier-info-card">
                <span>Officer ID</span>
                <strong>
                  {officer.id ||
                    'Not provided'}
                </strong>
              </div>

              <div className="dossier-info-card">
                <span>Jurisdiction</span>
                <strong>
                  {officer.jurisdiction ||
                    'Not provided'}
                </strong>
              </div>

              <div className="dossier-info-card">
                <span>File</span>
                <strong>
                  {file?.name ||
                    'Not available'}
                </strong>
              </div>

            </div>
          </section>

          {/* PRODUCT INFORMATION */}

          <section className="dossier-section">
            <p className="eyebrow">
              02 / Product declarations
            </p>

            <div className="declaration-grid">

              <div className="declaration-card">
                <span>
                  Manufacturer
                </span>

                <strong>
                  {report.extraction
                    ?.manufacturer?.name ||
                    'Not reliably detected'}
                </strong>
              </div>

              <div className="declaration-card">
                <span>
                  Generic name
                </span>

                <strong>
                  {report.extraction
                    ?.generic_name ||
                    'Not reliably detected'}
                </strong>
              </div>

              <div className="declaration-card">
                <span>
                  Net quantity
                </span>

                <strong>
                  {report.extraction
                    ?.net_quantity ||
                    'Not reliably detected'}
                </strong>
              </div>

              <div className="declaration-card">
                <span>
                  Manufacture date
                </span>

                <strong>
                  {report.extraction
                    ?.manufacture_month_year ||
                    'Not reliably detected'}
                </strong>
              </div>

              <div className="declaration-card">
                <span>
                  Best before / use by
                </span>

                <strong>
                  {report.extraction
                    ?.best_before_or_use_by ||
                    'Not reliably detected'}
                </strong>
              </div>

              <div className="declaration-card">
                <span>
                  MRP declaration
                </span>

                <strong>
                  {report.extraction
                    ?.mrp_declaration ||
                    'Not reliably detected'}
                </strong>
              </div>

              <div className="declaration-card">
                <span>
                  Country of origin
                </span>

                <strong>
                  {report.extraction
                    ?.country_of_origin ||
                    'Not reliably detected'}
                </strong>
              </div>

            </div>
          </section>

          {/* COMPLIANCE SUMMARY */}

          <section className="dossier-section">
            <p className="eyebrow">
              03 / Compliance summary
            </p>

            <div className="score-grid">

              <Metric
                label="Passed"
                value={
                  report.counts?.PASS
                }
                type="pass"
              />

              <Metric
                label="Needs review"
                value={
                  report.counts
                    ?.NEEDS_REVIEW
                }
                type="review"
              />

              <Metric
                label="Issues"
                value={
                  report.counts
                    ?.POSSIBLE_VIOLATION
                }
                type="fail"
              />

              <Metric
                label="Exempt"
                value={
                  report.counts?.EXEMPT
                }
                type="exempt"
              />

              <Metric
                label="Not assessed"
                value={
                  report.counts?.SKIPPED
                }
                type="skipped"
              />

            </div>
          </section>

          {/* REGULATORY FINDINGS */}

          <section className="dossier-section">
            <p className="eyebrow">
              04 / Regulatory findings
            </p>

            <div className="finding-list dossier-findings">

              {report.findings?.map(
                (finding, index) => (
                  <article
                    className="finding"
                    key={`${finding.rule_id}-${index}`}
                  >

                    <div className="finding-top">

                      <span className="rule">
                        {finding.rule_id}
                      </span>

                      <Badge
                        status={
                          finding.outcome
                        }
                      />

                    </div>

                    <p>
                      {finding.message}
                    </p>

                    {finding.observed && (
                      <code>
                        {typeof finding.observed ===
                        'object'
                          ? JSON.stringify(
                              finding.observed,
                              null,
                              2,
                            )
                          : finding.observed}
                      </code>
                    )}

                  </article>
                ),
              )}

            </div>
          </section>

          {/* EVIDENCE */}

          <section className="dossier-section">
            <p className="eyebrow">
              05 / Evidence
            </p>

            {report.annotated_image_url || preview ? (
              <div className="dossier-image">
                <img
                  src={report.annotated_image_url ? `${API_URL}${report.annotated_image_url}` : preview}
                  alt="Inspected package label"
                />
              </div>
            ) : (
              <p className="no-findings">
                Original inspection image is
                unavailable.
              </p>
            )}

            <div className="evidence-dossier-list">

              {(report.extraction
                ?.evidence || []
              ).map(
                (item, index) => (
                  <div
                    className="evidence-item"
                    key={`${item.field}-${index}`}
                  >

                    <div>
                      <strong>
                        {item.field}
                      </strong>

                      <p>
                        {item.text ||
                          'No text detected'}
                      </p>
                    </div>

                    <span
                      className={`confidence ${
                        item.confidence ||
                        'low'
                      }`}
                    >
                      {item.confidence ||
                        'unknown'}
                    </span>

                  </div>
                ),
              )}

            </div>
          </section>

          {/* REVIEW NOTICE */}

          <div className="extractor-notice dossier-notice">
            <strong>
              Review status
            </strong>

            <p>
              This dossier consolidates
              AI-assisted extraction and the
              configured deterministic rule
              engine. It is intended as an
              inspection aid and requires
              qualified human verification.
            </p>
          </div>

        </div>
      )}

    </div>
  </section>
)}

      {/* ================= HISTORY ================= */}

      {/* ================= HISTORY ================= */}

{activePage === 'history' && (
  <section className="workspace">
    <div className="results-panel evidence-full">

      <div className="result-header">
        <div>
          <p className="eyebrow">
            Inspection history
          </p>

          <h2>
            History & repository
          </h2>

          <p>
            Previous LabelLens inspection
            records stored on this device.
          </p>
        </div>

        <span className="history-count">
          {history.length} record
          {history.length === 1 ? '' : 's'}
        </span>
      </div>

      {history.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">
            ◷
          </div>

          <p className="eyebrow">
            No records
          </p>

          <h2>
            No inspections yet
          </h2>

          <p>
            Completed inspections will
            automatically appear here.
          </p>

          <button
            className="primary dossier-action"
            onClick={() =>
              setActivePage('inspect')
            }
          >
            Start inspection
          </button>
        </div>
      ) : (
        <div className="history-list">

          {history.map((item) => (
            <article
              className="history-card"
              key={item.id}
            >

              <div className="history-card-main">

                <div>
                  <span className="history-id">
                    {item.id}
                  </span>

                  <h3>
                    {item.filename}
                  </h3>

                  <p>
                    {new Date(
                      item.date,
                    ).toLocaleString(
                      'en-IN',
                      {
                        day: '2-digit',
                        month: 'short',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      },
                    )}
                  </p>
                </div>

                <Badge
                  status={item.outcome}
                />

              </div>

              <div className="history-meta">

                <div>
                  <span>Officer</span>
                  <strong>
                    {item.officer}
                  </strong>
                </div>

                <div>
                  <span>Officer ID</span>
                  <strong>
                    {item.officerId}
                  </strong>
                </div>

                <div>
                  <span>Jurisdiction</span>
                  <strong>
                    {item.jurisdiction}
                  </strong>
                </div>

                <div>
                  <span>Passed</span>
                  <strong>
                    {item.counts?.PASS ?? 0}
                  </strong>
                </div>

                <div>
                  <span>Review</span>
                  <strong>
                    {item.counts?.NEEDS_REVIEW ?? 0}
                  </strong>
                </div>

                <div>
                  <span>Issues</span>
                  <strong>
                    {item.counts?.POSSIBLE_VIOLATION ?? 0}
                  </strong>
                </div>

              </div>

            </article>
          ))}

        </div>
      )}

    </div>
  </section>
)}

      <footer>
        LabelLens evaluates configured checks
        only. Always have findings reviewed by
        a qualified professional.
      </footer>
    </main>
  )
}

export default App

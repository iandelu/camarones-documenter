import { Fragment, useEffect, useMemo, useState } from 'react'
import { Aviso, Button, Chip, Skeleton } from '@camaron/ui'
import { advisories, applyFilter, facets, fixTarget, matrix, rowsOf } from '@camaron/ui/libs.js'
import { severities } from '@camaron/ui/result.js'
import { useCmd } from '../hooks.js'
import { Failed, JobOutput, Page } from '../parts.jsx'
import { inventoryArgs, scanProgress } from '../quality.js'
import { t } from '../i18n.js'

// Libraries: what every repo declares, read from the code without AI (inventory), as a library x service table. Any
// line opens on why the library is there (which manifest, which scope), why it is flagged (the advisories with their
// affected versions and full text, read offline from the last scan) and an update: `bump` on a new branch of that
// repo, with its own package manager, never committed. A scan shows the repo it reads and ends on a tick; back here
// while one runs, the section attaches to it.
export const SEV = { critical: 'bad', high: 'bad', medium: 'warn', moderate: 'warn' }
export const sevWord = (s) => { const k = `sev.${s}`; const w = t(k); return w === k ? s : w }
const slug = (name) => name.split(':').pop().split('/').pop().replace(/[^\w.-]+/g, '-')
const libCount = (rows) => new Set(rows.map((r) => r.ecosystem + r.name)).size

export default function Libs({ srv, jobs }) {
  const c = useCmd(srv, jobs)
  const [inv, setInv] = useState(null)
  const [error, setError] = useState('')
  const [f, setF] = useState({})
  const [open, setOpen] = useState(null)
  const [cves, setCves] = useState(true)
  const [closed, setClosed] = useState(false)
  const load = () => srv.get('inventory').then((x) => { setInv(x); setError('') }, (e) => setError(e.message))
  const rows = inv?.libraries || []
  const shown = useMemo(() => applyFilter(rows, f), [rows, f])
  const m = useMemo(() => matrix(shown), [shown])
  const fc = useMemo(() => facets(rows), [rows])
  const sev = severities(rows)
  const run = async (args) => { setCves(!!args.cves); setClosed(false); await c.run('inventory', args); load() }
  useEffect(() => {
    load()
    const args = inventoryArgs(jobs?.get().running)
    if (args) run(args)
  }, [])
  const set = (k) => (v) => setF((cur) => ({ ...cur, [k]: v }))
  const count = libCount(rows)
  return (
    <Page title={t('nav.libs')} wide>
      <p className="muted">{t('lb.lead')}</p>
      {error ? <Failed title={t('q.cvFailed')} detail={error} onRetry={load} /> : null}
      {inv ? (
        <div className="row">
          <b>{t('q.libsCount', { n: count })}</b>
          {inv.vulns ? (sev.length ? sev.map(([s, n]) => <Chip key={s} state={SEV[s]}>{n} {sevWord(s)}</Chip>) : <Chip state="ok">{t('q.cvClean')}</Chip>)
            : <span className="muted small">{t('q.cvNever')}</span>}
          {inv.vulns ? <span className="muted small">{t('q.cvAt', { day: inv.vulns.at?.slice(0, 10) })}</span> : null}
          <span className="dk-grow"></span>
          <Button size="sm" variant="ghost" href="../#/libs">{t('q.inPortal')}</Button>
        </div>
      ) : !error ? <Skeleton lines={3} /> : null}
      <div className="row" data-tour="libs-actions">
        <Button size="sm" variant="primary" disabled={c.running} onClick={() => run({ cves: true, json: true })}>{t('q.cvScan')}</Button>
        <Button size="sm" disabled={c.running} onClick={() => run({ json: true })}>{t('q.libsRead')}</Button>
        <span className="muted small">{t('q.libsNoAi')}</span>
      </div>
      {closed ? null : <ScanStatus c={c} cves={cves} onClose={() => setClosed(true)} />}
      {rows.length ? (<>
        <div className="row" data-tour="libs-filters">
          <input type="search" className="cu-input dk-grow" placeholder={t('q.libsSearch')} aria-label={t('q.libsSearch')} value={f.q || ''} onChange={(e) => set('q')(e.target.value)} />
          <FacetSelect label={t('q.libsCategory')} value={f.category} onChange={set('category')} options={fc.category} />
          <FacetSelect label={t('q.libsRepo')} value={f.repo} onChange={set('repo')} options={fc.repo} />
          <FacetSelect label={t('lb.scope')} value={f.scope} onChange={set('scope')} options={fc.scope} />
          <label className="dk-check"><input type="checkbox" checked={!!f.vulnerable} onChange={(e) => set('vulnerable')(e.target.checked)} />{t('q.libsOnlyVuln')}</label>
        </div>
        {m.items.length ? (
          <div className="dk-scroll" data-tour="libs-table"><table className="dk-table dk-libs">
            <thead><tr><th>{t('q.libsLibrary')}</th><th>{t('q.libsCategory')}</th>{m.repos.map((r) => <th key={r}>{r}</th>)}</tr></thead>
            <tbody>{m.items.map((x) => (
              <Fragment key={x.key}>
                <tr className={(x.worst ? `vuln sev-${SEV[x.worst] || 'low'}` : '') + (open === x.key ? ' on' : '')}>
                  <td><button type="button" className="dk-linkish" aria-expanded={open === x.key} onClick={() => setOpen(open === x.key ? null : x.key)}>
                      <code>{x.name}</code></button> <span className="muted small">{x.ecosystem}</span>
                    {x.worst ? <> <Chip state={SEV[x.worst]}>{sevWord(x.worst)}</Chip></> : null}
                    {x.drift ? <> <Chip state="warn">{t('q.libsVersions')}</Chip></> : null}</td>
                  <td className="muted small">{x.category}</td>
                  {m.repos.map((r) => { const v = x.cells[r]; return <td key={r} className={v?.vulns.length ? 'cell-vuln' : ''}>{v ? v.version || '—' : ''}</td> })}
                </tr>
                {open === x.key ? (
                  <tr className="dk-lib-row"><td colSpan={2 + m.repos.length}>
                    <Library item={x} rows={rowsOf(rows, x.key)} scanned={!!inv.vulns} srv={srv} jobs={jobs} onChanged={load} />
                  </td></tr>
                ) : null}
              </Fragment>
            ))}</tbody>
          </table></div>
        ) : <p className="muted small">{t('nothing')}</p>}
      </>) : inv ? <p className="muted small">{t('q.libsNone')}</p> : null}
    </Page>
  )
}

// A scan (`cves`) or a reread as it goes, then a tick and what it found. A failed or stopped one shows the command's
// output; a scan without OSV-Scanner warns with the reason it gave instead of ticking.
export function ScanStatus({ c, cves, onClose }) {
  const job = c.job
  if (!job || c.error || job.status === 'failed') return <JobOutput c={c} />
  if (job.status === 'running') return <Scanning job={job} cves={cves} onStop={c.stop} />
  const r = job.result
  if (cves && r && r.vulns === null) {
    const why = job.lines.find((l) => l.startsWith('⚠'))
    return <Aviso tone="warn" title={t('lb.noScanner')} detail={why?.replace(/^⚠\s*/, '')}>{t('lb.noScannerWhat')}</Aviso>
  }
  const failed = cves ? r?.vulns?.failed || [] : []
  return (
    <div className="dk-scan done" role="status">
      <Tick />
      <div className="dk-scan-what">
        <b>{t(cves ? 'lb.scanned' : 'lb.read')}</b>
        {r ? <span className="muted small">{found(r, cves)}</span> : null}
        {failed.length ? <span className="small">{t('lb.scanFailedRepos', { repos: failed.join(', ') })}</span> : null}
      </div>
      <span className="dk-grow"></span>
      <button type="button" className="dk-icon" aria-label={t('close')} onClick={onClose}>×</button>
    </div>
  )
}

function found(r, cves) {
  const rows = r.libraries || []
  if (!cves) return t('lb.readWhat', { n: libCount(rows), repos: new Set(rows.map((x) => x.repo)).size })
  const n = libCount(rows.filter((x) => (x.vulns || []).length))
  return t(n ? 'lb.scannedVuln' : 'lb.scannedClean', { repos: r.vulns?.scanned ?? 0, n })
}

// While it runs: the repo it reads with the ones done before it and how many are left (lib/osv.py counts them).
function Scanning({ job, cves, onStop }) {
  const p = scanProgress(job.lines)
  const left = Math.max(0, p.total - p.n)
  return (
    <div className="dk-scan" role="status">
      <div className="row">
        <b>{!cves ? t('lb.reading') : p.repo ? t('lb.scanRepo', { repo: p.repo }) : t('lb.scanPrep')}</b>
        <span className="dk-grow"></span>
        {p.total ? <span className="muted small">{t('lb.scanCount', { n: p.n, total: p.total })}</span> : null}
        <Button size="sm" variant="ghost" onClick={onStop}>{t('job.stop')}</Button>
      </div>
      <Bar n={p.n} total={p.total} />
      {p.total > 1 ? (
        <ol className="dk-scan-repos">
          {p.done.map((r) => <li key={r} className="done">{`✓ ${r}`}</li>)}
          <li className="current"><i></i>{p.repo}</li>
          {left ? <li className="muted">{t('lb.scanLeft', { n: left })}</li> : null}
        </ol>
      ) : null}
    </div>
  )
}

// The repos done fill the bar and the one being read glows after them; before the first count it sweeps.
function Bar({ n, total }) {
  if (!total) return <div className="dk-bar indeterminate" aria-hidden="true"><i></i></div>
  const done = (n - 1) / total
  return (
    <div className="dk-bar" aria-hidden="true">
      <span style={{ transform: `scaleX(${done})` }}></span>
      <i style={{ transform: `translateX(${done * 100}%) scaleX(${1 / total})` }}></i>
    </div>
  )
}

// The check that draws itself in its circle once a scan ends (an approved drawing, see the design system's CAMARON.md).
const Tick = () => (
  <svg className="dk-tick" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2"
    strokeLinecap="round" strokeLinejoin="round">
    <circle className="dk-tick-ripple" cx="12" cy="12" r="10" />
    <circle className="dk-tick-ring" cx="12" cy="12" r="10" />
    <path className="dk-tick-check" d="m7.5 12.5 3 3 6-7" pathLength="1" />
  </svg>
)

function FacetSelect({ label, value, onChange, options }) {
  return (
    <select className="cu-input dk-select" value={value || ''} aria-label={label} onChange={(e) => onChange(e.target.value)}>
      <option value="">{label}: {t('q.libsAll')}</option>
      {options.map(([k, n]) => <option key={k} value={k}>{k} ({n})</option>)}
    </select>
  )
}

// One library: why it is there, why it is flagged and how to update it, repo by repo.
export function Library({ item, rows, scanned, srv, jobs, onChanged }) {
  const advs = advisories(item.vulns)
  return (
    <div className="dk-lib">
      <section>
        <h3>{t('lb.why')}</h3>
        <p className="muted small">{t('lb.whyLead', { category: item.category, language: item.language })}</p>
        <table className="dk-table"><thead><tr><th>{t('q.libsRepo')}</th><th>{t('lb.manifest')}</th><th>{t('lb.declared')}</th>
          <th>{t('lb.version')}</th><th>{t('lb.scope')}</th><th>{t('lb.update')}</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.repo + r.source}>
              <th>{r.repo}</th>
              <td><code>{r.source.split(':').slice(1).join(':')}</code></td>
              <td><code>{r.declared || '—'}</code>{r.managedBy ? <span className="muted small"> · {t('lb.managed', { by: r.managedBy })}</span> : null}</td>
              <td className={(r.vulns || []).length ? 'cell-vuln' : ''}>{r.version || '—'}</td>
              <td><Chip>{t(`lb.scope.${r.scope}`)}</Chip></td>
              <td><Update row={r} srv={srv} jobs={jobs} onChanged={onChanged} /></td>
            </tr>))}</tbody></table>
      </section>
      <section>
        <h3>{t('lb.flagged')}</h3>
        {!scanned ? <p className="muted small">{t('lb.notScanned')}</p>
          : !advs.length ? <p className="small">{t('lb.clean')}</p> : (<>
            <p className="small">{t('lb.flaggedLead', { n: advs.length })}</p>
            <div className="dk-advs">{advs.map((v) => <Advisory key={v.id} v={v} />)}</div>
          </>)}
      </section>
    </div>
  )
}

// An advisory as the last scan kept it: what it is, which versions it affects and its text; a scan from before the
// full text was kept links to it instead.
function Advisory({ v }) {
  const osv = `https://osv.dev/vulnerability/${encodeURIComponent(v.id)}`
  const ranges = (v.ranges || []).map((r) => (r.fixed ? t('lb.range', { from: r.introduced, to: r.fixed })
    : r.last_affected ? t('lb.rangeLast', { from: r.introduced, to: r.last_affected }) : t('lb.rangeOpen', { from: r.introduced })))
  return (
    <details className="dk-adv">
      <summary>
        <b>{v.cve || v.id}</b> <Chip state={SEV[v.severity]}>{sevWord(v.severity)}{v.score ? ` ${v.score}` : ''}</Chip>{' '}
        <span className="small">{v.summary}</span>{v.fixed ? <> <b className="small">{t('q.libsFixed', { v: v.fixed })}</b></> : null}
      </summary>
      <div className="dk-adv-body">
        <dl className="dk-adv-facts">
          <dt>{t('lb.ids')}</dt><dd><code>{[v.id, ...(v.aliases || []).filter((a) => a !== v.id)].join(' · ')}</code></dd>
          {ranges.length ? <><dt>{t('lb.affects')}</dt><dd>{ranges.join('; ')}</dd></> : null}
          {v.published ? <><dt>{t('lb.published')}</dt><dd>{v.published.slice(0, 10)}{v.modified ? ` · ${t('lb.modified', { day: v.modified.slice(0, 10) })}` : ''}</dd></> : null}
          {v.cwes?.length ? <><dt>{t('lb.cwe')}</dt><dd>{v.cwes.join(', ')}</dd></> : null}
        </dl>
        {v.details ? <div className="dk-adv-text">{v.details}</div>
          : <p className="muted small">{t(v.details === undefined ? 'lb.rescan' : 'lb.noText')}</p>}
        <ul className="dk-adv-refs">
          <li><a href={osv} target="_blank" rel="noreferrer">osv.dev ↗</a></li>
          {(v.references || []).map((r) => <li key={r.url}><a href={r.url} target="_blank" rel="noreferrer">{r.url}</a>
            {r.type ? <span className="muted small"> {r.type.toLowerCase()}</span> : null}</li>)}
        </ul>
      </div>
    </details>
  )
}

// Update one library in one repo: the version that fixes its advisories by default, asked once, then `bump` makes the
// branch with the repo's own package manager. Nothing is committed: the person reviews the branch.
function Update({ row, srv, jobs, onChanged }) {
  const c = useCmd(srv, jobs)
  const fix = fixTarget(row.vulns)
  const [version, setVersion] = useState(fix || '')
  const [asking, setAsking] = useState(false)
  const v = version.trim()
  const go = async () => {
    setAsking(false)
    const end = await c.run('bump', { repo: row.repo, library: row.name, version: v, ecosystem: row.ecosystem, json: true }, true)
    if (end?.status === 'done') onChanged()
  }
  const done = c.job?.status === 'done' && c.job.result
  return (
    <div className="dk-bump">
      <div className="row">
        <input className="cu-input dk-bump-v" value={version} onChange={(e) => setVersion(e.target.value)} placeholder={t('lb.to')}
          aria-label={t('lb.toIn', { repo: row.repo })} disabled={c.running} />
        <Button size="sm" variant={fix ? 'primary' : 'secondary'} disabled={!v || v.startsWith('-') || c.running || v === row.version}
          aria-expanded={asking} onClick={() => setAsking(!asking)}>{t('lb.updateGo')}</Button>
      </div>
      {asking ? (
        <Aviso tone="warn" title={t('lb.ask', { name: row.name, version: v, repo: row.repo })}
          action={<span className="row"><Button size="sm" variant="primary" onClick={go}>{t('lb.yes')}</Button>
            <Button size="sm" variant="ghost" onClick={() => setAsking(false)}>{t('cancel')}</Button></span>}>
          {t('lb.askWhat', { branch: `camaron/bump-${slug(row.name)}-${v}` })}
        </Aviso>
      ) : null}
      {done ? <Aviso tone="info" title={t('lb.done', { branch: done.branch, repo: done.repo })}>{t('lb.doneWhat', { files: done.files.join(', ') })}</Aviso> : null}
      {c.running || c.error || c.job?.status === 'failed' ? <JobOutput c={c} /> : null}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Aviso, Button, LibrariesBoard, Skeleton } from '@camaron/ui'
import { Suggestions } from '@camaron/ui/libs.jsx'
import { latestOf, matrix, outdated } from '@camaron/ui/libs.js'
import { useCmd } from '../hooks.js'
import { Failed, JobOutput, Page } from '../parts.jsx'
import { inventoryArgs, lookupProgress, scanProgress } from '../quality.js'
import { t } from '../i18n.js'

// Libraries: the shared board (@camaron/ui LibrariesBoard, the same screen as the portal's) with the app's commands:
// a vulnerability scan, a lookup of newer versions (`inventory --latest`), a reread, and `bump` on a new branch of a
// repo with its own package manager, never committed. A scan or a lookup shows what it reads and ends on a tick; back
// here while one runs, the section attaches to it.
const slug = (name) => name.split(':').pop().split('/').pop().replace(/[^\w.-]+/g, '-')
const libCount = (rows) => new Set(rows.map((r) => r.ecosystem + r.name)).size
const modeOf = (args) => (args.cves ? 'cves' : args.latest ? 'latest' : 'read')

export default function Libs({ srv, jobs }) {
  const c = useCmd(srv, jobs)
  const [inv, setInv] = useState(null)
  const [error, setError] = useState('')
  const [mode, setMode] = useState('cves')
  const [closed, setClosed] = useState(false)
  const load = () => srv.get('inventory').then((x) => { setInv(x); setError('') }, (e) => setError(e.message))
  const run = async (args) => { setMode(modeOf(args)); setClosed(false); await c.run('inventory', args); load() }
  useEffect(() => {
    load()
    const args = inventoryArgs(jobs?.get().running)
    if (args) run(args)
  }, [])
  return (
    <Page title={t('nav.libs')} wide>
      {error ? <Failed title={t('q.cvFailed')} detail={error} onRetry={load} /> : null}
      {inv ? (
        <LibrariesBoard inv={inv} actions={<Actions c={c} run={run} />}
          status={closed ? null : <ScanStatus c={c} mode={mode} onClose={() => setClosed(true)} />}
          renderUpdate={(row, p) => <Update row={row} proposal={p} srv={srv} jobs={jobs} onChanged={load} />} />
      ) : !error ? <Skeleton lines={3} /> : null}
    </Page>
  )
}

export function Actions({ c, run }) {
  return (<>
    <Button size="sm" variant="primary" disabled={c.running} onClick={() => run({ cves: true, json: true })}>{t('q.cvScan')}</Button>
    <Button size="sm" disabled={c.running} onClick={() => run({ latest: true, json: true })}>{t('lb.lookGo')}</Button>
    <Button size="sm" disabled={c.running} onClick={() => run({ json: true })}>{t('q.libsRead')}</Button>
    <Button size="sm" variant="ghost" href="../#/libs">{t('q.inPortal')}</Button>
  </>)
}

// A scan (`cves`), a lookup (`latest`) or a reread as it goes, then a tick and what it found. A failed or stopped one
// shows the command's output; a scan without OSV-Scanner warns with the reason it gave instead of ticking.
export function ScanStatus({ c, mode, onClose }) {
  const job = c.job
  if (!job || c.error || job.status === 'failed') return <JobOutput c={c} />
  if (job.status === 'running') return mode === 'latest' ? <Looking job={job} onStop={c.stop} /> : <Scanning job={job} cves={mode === 'cves'} onStop={c.stop} />
  const r = job.result
  if (mode === 'cves' && r && r.vulns === null) {
    const why = job.lines.find((l) => l.startsWith('⚠'))
    return <Aviso tone="warn" title={t('lb.noScanner')} detail={why?.replace(/^⚠\s*/, '')}>{t('lb.noScannerWhat')}</Aviso>
  }
  const failed = mode === 'cves' ? r?.vulns?.failed || [] : mode === 'latest' ? r?.latest?.failed || [] : []
  return (
    <div className="dk-scan done" role="status">
      <Tick />
      <div className="dk-scan-what">
        <b>{t(mode === 'cves' ? 'lb.scanned' : mode === 'latest' ? 'lb.looked' : 'lb.read')}</b>
        {r ? <span className="muted small">{found(r, mode)}</span> : null}
        {failed.length ? <span className="small">{mode === 'latest' ? t('lb.lookFailedShort', { registries: failed.join(', ') })
          : t('lb.scanFailedRepos', { repos: failed.join(', ') })}</span> : null}
      </div>
      <span className="dk-grow"></span>
      <button type="button" className="dk-icon" aria-label={t('close')} onClick={onClose}>×</button>
    </div>
  )
}

function found(r, mode) {
  const rows = r.libraries || []
  if (mode === 'read') return t('lb.readWhat', { n: libCount(rows), repos: new Set(rows.map((x) => x.repo)).size })
  if (mode === 'latest') {
    const n = matrix(rows).items.filter((x) => outdated(x, latestOf(r.latest, x)) === true).length
    return t('lb.lookedWhat', { checked: r.latest?.checked ?? 0, n })
  }
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

// A lookup names the library it last heard back about and counts; hundreds of libraries get no chip each.
function Looking({ job, onStop }) {
  const p = lookupProgress(job.lines)
  return (
    <div className="dk-scan" role="status">
      <div className="row">
        <b>{p.name ? t('lb.looking', { name: p.name }) : t('lb.lookPrep')}</b>
        <span className="dk-grow"></span>
        {p.total ? <span className="muted small">{t('lb.lookCount', { n: p.n, total: p.total })}</span> : null}
        <Button size="sm" variant="ghost" onClick={onStop}>{t('job.stop')}</Button>
      </div>
      <Bar n={p.total ? Math.min(p.total, p.n + 1) : 0} total={p.total} />
    </div>
  )
}

// The items done fill the bar and the one under way glows after them; before the first count it sweeps.
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

// Update one library in one repo: the proposed version (the latest stable, else the one that fixes its advisories),
// asked once, then `bump` makes the branch with the repo's own package manager. Nothing is committed.
export function Update({ row, proposal, srv, jobs, onChanged }) {
  const c = useCmd(srv, jobs)
  const [version, setVersion] = useState(proposal.version)
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
      <Suggestions proposal={proposal} value={v} onPick={(x) => { setVersion(x); setAsking(false) }} />
      <div className="row">
        <input className="cu-input dk-bump-v" value={version} onChange={(e) => setVersion(e.target.value)} placeholder={t('lb.to')}
          aria-label={t('lb.toIn', { repo: row.repo })} disabled={c.running} />
        <Button size="sm" variant={proposal.version ? 'primary' : 'secondary'} disabled={!v || v.startsWith('-') || c.running || v === row.version}
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

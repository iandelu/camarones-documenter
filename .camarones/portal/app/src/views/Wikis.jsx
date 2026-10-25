import { useEffect, useState } from 'react'
import { Aviso, Button, Card, Chip, EmptyState, Skeleton } from '@camaron/ui'
import { getJSON, postJSON } from '../api.js'
import { docsGet } from '../docsApi.js'
import { useBuild } from '../useBuild.js'
import { DocView } from './Doc.jsx'
import { wikiTarget } from './wiki.js'
import { core } from '../core.js'

const runs = () => core.mode() === 'app'

// OpenWiki, one navigable wiki per repo with its own menu and backlinks, apart from the Docs tree.
// api/wikis takes a while (it reads every wiki): one answer is shared by the sidebar and the view, until a run ends.
let wikisAnswer = null
function useWikis() {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const load = (fresh = false) => {
    if (fresh || !wikisAnswer) wikisAnswer = docsGet('wikis')
    wikisAnswer.then(setRows, (e) => { wikisAnswer = null; setError(e.message) })
  }
  useEffect(() => { load() }, [])
  return { rows, error, load: () => load(true) }
}

// The sidebar on the wiki views: the repos, or one wiki's graph and pages.
export function WikiSide({ repo = '', page = '' }) {
  const t = core.t
  const { rows } = useWikis()
  const wikis = (rows || []).filter((w) => w.pages)
  const w = wikis.find((r) => r.repo === repo)
  return (
    <nav className="wiki-side" aria-label={t('wikis')}>
      <div className="side-title">{t('wikis')}</div>
      {w && wikis.length > 1 && (
        <select aria-label="repo" value={repo} onChange={(e) => { location.hash = `#/wiki/${e.target.value}` }}>
          {wikis.map((r) => <option key={r.repo} value={r.repo}>{r.repo}</option>)}
        </select>
      )}
      {w ? (
        <>
          <div className="group"><a href="#/wikis" className="back"><span aria-hidden="true">←</span> {t('allWikis')}</a></div>
          <div className="group"><a href={`#/wiki/${w.repo}`} className={page === 'graph' ? 'on' : ''}>{t('graph')}</a></div>
          <div className="group"><div className="group-title">{w.repo} · {t('wikiPages')}</div>
            {w.nav.pages.map((p) => <a key={p.path} href={core.hrefFor(p.path)} className={p.path === page ? 'on' : ''}
              aria-current={p.path === page ? 'page' : undefined}>{p.title}</a>)}</div>
        </>
      ) : (
        <div className="group">
          {wikis.map((r) => <a key={r.repo} href={`#/wiki/${r.repo}`} className={r.repo === repo ? 'on' : ''}>{r.repo} <span className="count">{r.pages}</span></a>)}
          {rows && !wikis.length && <p className="muted small">{t('noWiki')}</p>}
        </div>
      )}
    </nav>
  )
}

// #/wikis: every repo's wiki — its pages, when it was written, and (in the app) generate or update it.
export function Wikis() {
  const t = core.t
  const index = core.tree()
  const { rows, error, load } = useWikis()
  const [running, setRunning] = useState([])
  useEffect(() => {                                  // a wiki run started earlier (here or in another tab) is shown again
    if (runs()) getJSON('jobs').then((jobs) => setRunning(jobs.filter((j) => j.kind === 'wiki' && j.status === 'running')), () => {})
  }, [])
  const engines = index.engines || []
  return (
    <div className="page wide">
      <h1>{t('wikis')} <span className="muted small">OpenWiki</span></h1>
      <p className="lead">{t('wikisHelp')}</p>
      {runs() && !engines.length && <Aviso tone="warn" title={t(index.engineHelp && index.engineHelp !== 'key' ? 'noEngine.' + index.engineHelp : 'noEngine')} />}
      {error && <Aviso tone="error" title={t('error')} detail={error} />}
      {!rows && !error && <Skeleton lines={4} />}
      {rows && !rows.length && <EmptyState title={t('noWiki')} action={<Button href="#/docs">{t('docs')}</Button>} />}
      <div className="cards">
        {(rows || []).map((w) => <WikiCard key={w.repo} w={w} t={t} engines={engines}
          running={running.find((j) => j.label.endsWith(' ' + w.repo))} onDone={async () => { await core.reload(); load() }} />)}
      </div>
    </div>
  )
}

function WikiCard({ w, t, engines, running, onDone }) {
  const build = useBuild()
  const [engine, setEngine] = useState(engines[0] || '')
  const [error, setError] = useState('')
  useEffect(() => { if (running) build.follow(running).then((s) => { if (s?.status === 'done') onDone() }) }, [running?.id])
  const generate = async () => {
    setError('')
    try {
      const j = await postJSON('wiki', { repo: w.repo, engine, choose: !w.chosen, starter: !w.brief && !w.pages })
      const s = await build.follow(j)
      if (s?.status === 'done') onDone()
    } catch (e) { setError(e.message) }
  }
  return (
    <Card className="card">
      <div className="card-h">
        {w.pages ? <a href={`#/wiki/${w.repo}`}><b>{w.repo}</b></a> : <b>{w.repo}</b>}
        <span className="muted small">{w.pages ? `${t('pages', { n: w.pages })} · ${t('updated', { when: core.ago(w.at) })}`
          : t(w.cloned ? 'noWiki' : 'notCloned')}</span>
        {w.stale && <Chip state="warn">{t('stale')}</Chip>}
        {w.unit && <Chip>{t('unit')}: {w.unit}</Chip>}
        {w.brief === 'starter' && <Chip>{t('starterBrief')}</Chip>}
      </div>
      <div className="row">
        {w.pages > 0 && <><Button size="sm" variant="primary" href={`#/wiki/${w.repo}`}>{t('graph')}</Button>
          <Button size="sm" href={core.hrefFor(w.nav.home)}>{t('readPages')}</Button></>}
        {runs() && w.canGenerate && !w.chosen && !w.pages && <span className="muted small">{t('notChosen')}</span>}
        {runs() && w.canGenerate && !w.brief && !w.pages && <span className="muted small">{t('needBrief')}</span>}
        {runs() && w.canGenerate && (
          <>
            <Button size="sm" disabled={build.running} onClick={generate}>{t(w.pages ? 'update' : 'generate')}</Button>
            {engines.length > 1
              ? <label className="small muted">{t('via')} <select value={engine} onChange={(e) => setEngine(e.target.value)}>
                  {engines.map((e) => <option key={e}>{e}</option>)}</select></label>
              : engines[0] && <span className="muted small">{t('via')} {engines[0]}</span>}
          </>
        )}
      </div>
      {w.old && <p className="warn small">{t('wikiOld')}</p>}
      {(error || build.error) && <Aviso tone="error" title={t('error')} detail={error || build.error} />}
      {build.job && <pre className="joblog" aria-live="polite">{build.job.lines.join('\n')}</pre>}
    </Card>
  )
}

// #/wiki/<repo>: the wiki opens on OpenWiki's own visualizer (page graph and reader); the app builds it first when it
// is missing or out of date.
export function WikiGraph({ arg }) {
  const repo = arg || ''
  const t = core.t
  const { rows, error, load } = useWikis()
  const build = useBuild()
  const w = rows?.find((r) => r.repo === repo)
  const ready = w?.graph && (!runs() || !w.graphStale)
  useEffect(() => {
    if (!rows || !w?.pages || ready) return
    if (!runs()) { location.replace(core.hrefFor(w.nav.home)); return }
    build.start('wiki-graph', repo).then((s) => { if (s?.status === 'done') load() })
  }, [rows])
  if (error) return <div className="page"><Aviso tone="error" title={t('error')} detail={error} /></div>
  if (!rows) return <div className="page"><Skeleton lines={3} /></div>
  if (!w?.pages) return (
    <div className="page"><h1>{repo}</h1>
      <EmptyState title={t('noWikiPages')} action={<Button href="#/wikis">{t('wikis')}</Button>} /></div>
  )
  const src = `wiki-graph/${encodeURIComponent(repo)}/`
  return (
    <>
      {w.old && <Aviso tone="warn" title={t('wikiOld')} />}
      <div className="vbar">
        <b>{repo}</b>
        <span className="muted small">{ready ? t('pages', { n: w.pages }) : build.job?.status === 'running' || !build.job ? t('graphBuilding') : t('graphFailed')}</span>
        <a href={core.hrefFor(w.nav.home)}>{t('readPages')}</a>
        {w.graph && <a href={src} target="_blank" rel="noopener">{t('openTab')} <span aria-hidden="true">↗</span></a>}
        {runs() && ready && <Button size="sm" disabled={build.running}
          onClick={() => build.start('wiki-graph', repo).then((s) => { if (s?.status === 'done') load() })}>{t('rebuild')}</Button>}
        {build.job && <pre className="joblog inline">{build.job.lines.slice(-3).join('\n')}</pre>}
      </div>
      {ready && <iframe className="viewer" src={src} title={`${repo} · ${t('graph')}`}></iframe>}
    </>
  )
}

// #/wiki/<repo>/<page>: a wiki page, read like a doc page, with the wiki's own order, its graph and backlinks.
export function WikiPage({ arg }) {
  const [where, anchor] = (arg || '').split('::')
  const [repo, ...rest] = where.split('/')
  const t = core.t
  const { rows, error } = useWikis()
  if (error) return <div className="page"><Aviso tone="error" title={t('error')} detail={error} /></div>
  if (!rows) return <div className="page"><Skeleton lines={6} /></div>
  const { wiki, path, order, backlinks } = wikiTarget(rows, repo, rest.join('/'))
  if (!path || !core.byPath(path)) return (
    <div className="page"><h1>{repo}</h1>
      <EmptyState title={t(path ? 'notFound' : 'noWikiPages')} action={<Button href="#/wikis">{t('wikis')}</Button>} /></div>
  )
  return (
    <DocView path={path} anchor={anchor} order={order}
      extra={<Button size="sm" variant="ghost" href={`#/wiki/${repo}`}>{t('graph')}</Button>}
      banner={wiki?.old ? <Aviso tone="warn" title={t('wikiOld')} /> : null}
      after={backlinks.length ? (
        <div className="box backlinks"><b>{t('linkedFrom')}</b>
          <ul className="list">{backlinks.map((b) => <li key={b.path}><a href={core.hrefFor(b.path)}>{b.title}</a></li>)}</ul></div>
      ) : null} />
  )
}

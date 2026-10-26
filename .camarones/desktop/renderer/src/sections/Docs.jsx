import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card } from '@camaron/ui'
import { answerView, askBody, askError, buildFailed, c4Card, openPortal, startBuild, startWiki, wikiBlocks, wikiBusyWith,
  wikiError } from '../docs.js'
import { useJob, useStore } from '../hooks.js'
import { errorLine } from '../onboarding.js'
import { JobOutput, Page } from '../parts.jsx'
import { t } from '../i18n.js'

// Reading is the portal's, on this same server one folder up: these buttons open it in the system browser (never an
// href the window would follow). The portal has no token, so what it shows but cannot run is run here: the C4
// explorer, each repo's wiki (generate it, build its graph) and Ask's AI answer. One wiki runs at a time: while one
// runs (the jobs store), Generate is closed on the other repos.
const NONE = { running: [] }
const NO_JOBS = { get: () => NONE, subscribe: () => () => {} }
export default function Docs({ srv, jobs, app, index }) {
  const open = (hash) => openPortal(app, location.origin, hash)
  const { rows, loading, reload } = useWikis(srv)
  const { running } = useStore(jobs || NO_JOBS)
  return (
    <Page title={t('nav.docs')}>
      <div className="row">
        <Button variant="primary" onClick={() => open('#/')}>{t('docs.read')}</Button>
        <Button onClick={() => open('#/review')}>{t('docs.review')}</Button>
        <Button variant="ghost" onClick={() => open('#/search')}>{t('docs.search')}</Button>
      </div>
      <Build srv={srv} jobs={jobs} card={c4Card} title={t('docs.c4')} hint={t('docs.c4Hint')} onView={() => open(c4Card.hash)} />
      {wikiBlocks(index, rows).map((b) => (
        <WikiBlock key={b.repo} srv={srv} jobs={jobs} block={b} loading={loading} busyWith={wikiBusyWith(running, b.repo)}
          onView={() => open(b.hash)} onDone={reload} />))}
      <Ask srv={srv} open={open} />
    </Page>
  )
}

// Each repo's wiki state (GET wikis, read-only: cloned, chosen, brief, pages, whether it can be generated), read once and
// again after a run; null while loading or when it could not be read (the blocks then keep Generate closed).
function useWikis(srv) {
  const [rows, setRows] = useState(null)
  const [loading, setLoading] = useState(true)
  const alive = useRef(true)
  const reload = () => srv.get('wikis').then((r) => { if (alive.current) { setRows(r); setLoading(false) } },
    () => { if (alive.current) { setRows(null); setLoading(false) } })
  useEffect(() => {
    alive.current = true
    reload()
    return () => { alive.current = false }
  }, [])
  return { rows, loading, reload }
}

// A build job of the project server (POST build, token-gated) followed to its end.
function Build({ srv, jobs, card, ...rest }) {
  const build = useJob(srv, jobs, () => startBuild(srv, card))
  return <BuildCard build={build} onBuild={() => build.run()} {...rest} />
}

// A job's state with a rejection said in the person's language (the POST failed before there was a job).
const shownJob = (build, say = errorLine) => (build.error ? { ...build, error: say({ message: build.error }, t) } : build)

// The card itself: Build runs the job (Retry once it failed, with the reason in the person's language), View opens the
// result in the portal. The buttons repeat on every card, so each says whose it is.
export function BuildCard({ title, hint, build, onBuild, onView }) {
  const go = buildFailed(build) ? t('retry') : t('docs.build')
  return (
    <Card className="dk-run">
      <div className="row"><span className="eyebrow">{title}</span><span className="dk-grow"></span>
        <Button size="sm" disabled={build.running} aria-label={`${go}: ${title}`} onClick={onBuild}>{go}</Button>
        <Button size="sm" variant="ghost" aria-label={`${t('docs.view')}: ${title}`} onClick={onView}>{t('docs.view')}</Button></div>
      <p className="muted small">{hint}</p>
      <JobOutput c={shownJob(build)} />
    </Card>
  )
}

// One block per repo: Generate runs POST wiki (it chooses the repo and writes the starter brief, which the hint says),
// and once there are pages — already, or after this run — the graph can be built and the wiki viewed in the portal.
// Generate is closed, with the reason, for a repo that is not cloned or without a wiki engine (the portal's canGenerate),
// and while another repo's wiki runs (busyWith: that repo).
const WHY = { notCloned: 'docs.notCloned', noEngine: 'docs.noEngine', unread: 'docs.wikiUnread' }
export function WikiBlock({ srv, jobs, block, loading = false, busyWith = '', onView, onDone }) {
  const gen = useJob(srv, jobs, async () => startWiki(srv, block))
  const graph = useJob(srv, jobs, () => startBuild(srv, block.graph))
  const title = t('docs.wikiBlock', { repo: block.repo })
  const graphTitle = t('docs.wiki', { repo: block.repo })
  const go = buildFailed(gen) ? t('retry') : t('docs.generate')
  const run = async () => { if ((await gen.run())?.status === 'done') onDone?.() }
  const again = buildFailed(graph) ? t('retry') : t('docs.build')
  const pages = block.hasWiki || gen.job?.status === 'done'
  const why = (block.blocked && !(block.blocked === 'unread' && loading) ? t(WHY[block.blocked]) : '')
    || (busyWith ? t('docs.wikiBusy', { repo: busyWith }) : '')
  return (
    <Card className="dk-run">
      <div className="row"><span className="eyebrow">{title}</span><span className="dk-grow"></span>
        <Button size="sm" variant="primary" disabled={gen.running || !!block.blocked || !!busyWith} aria-label={`${go}: ${title}`} onClick={() => run()}>{go}</Button>
        {pages ? <Button size="sm" variant="ghost" aria-label={`${t('docs.view')}: ${title}`} onClick={onView}>{t('docs.view')}</Button> : null}</div>
      <p className="muted small">{why || t('docs.generateHint')}</p>
      <JobOutput c={shownJob(gen, wikiError)} />
      {pages ? (
        <>
          <div className="row"><span className="muted small">{graphTitle}</span><span className="dk-grow"></span>
            <Button size="sm" disabled={graph.running} aria-label={`${again}: ${graphTitle}`} onClick={() => graph.run()}>{again}</Button></div>
          <p className="muted small">{t('docs.wikiHint')}</p>
          <JobOutput c={shownJob(graph)} />
        </>
      ) : null}
    </Card>
  )
}

// Ask's AI answer: POST ask/answer waits for the model (up to 90 s), so it is a request of its own, not a job. An
// empty question is not sent.
function Ask({ srv, open }) {
  const [q, setQ] = useState('')
  const [state, setState] = useState({ busy: false, view: null, error: '' })
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])
  async function submit(e) {
    e.preventDefault()
    const body = askBody(q)
    if (!body || state.busy) return
    setState({ busy: true, view: null, error: '' })
    try {
      const view = answerView(await srv.post('ask/answer', body))
      if (alive.current) setState({ busy: false, view, error: '' })
    } catch (err) {
      if (alive.current) setState({ busy: false, view: null, error: askError(err, t) })
    }
  }
  return (
    <Card className="dk-run">
      <span className="eyebrow">{t('docs.ask')}</span>
      <p className="muted small">{t('docs.askHint')}</p>
      <form className="row" onSubmit={submit}>
        <input className="cu-input dk-grow" value={q} placeholder={t('docs.askPh')} aria-label={t('docs.askLabel')} onChange={(e) => setQ(e.target.value)} />
        <Button type="submit" variant="primary" size="sm" disabled={state.busy || !q.trim()}>{t('docs.askGo')}</Button>
      </form>
      {state.busy ? <p className="muted small" role="status">{t('docs.asking')}</p> : null}
      {state.error ? <Aviso tone="error" title={state.error} /> : null}
      {state.view ? <AnswerView view={state.view} onOpen={open} /> : null}
    </Card>
  )
}

// The answer as text, who wrote it, and its sources as buttons that open the page in the portal.
export function AnswerView({ view, onOpen }) {
  if (view.kind === 'none') return <p className="muted">{t('docs.askNone')}</p>
  return (
    <div className="dk-out">
      <p className="dk-answer">{view.text}</p>
      {view.by ? <p className="muted small">{t('docs.by', { who: view.by })}</p> : null}
      {view.sources.length ? (
        <div className="row">
          <span className="muted small">{t('docs.sources')}</span>
          {view.sources.map((s) => (
            <Button key={s.cite} size="sm" variant="ghost" aria-label={`${t('docs.view')}: ${s.cite}`} onClick={() => onOpen(s.hash)}>{s.cite}</Button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

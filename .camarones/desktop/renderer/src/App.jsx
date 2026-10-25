import { useEffect, useMemo, useState } from 'react'
import { Brand, Breadcrumbs, Button, EmptyState, Keys, Skeleton, SkipLink } from '@camaron/ui'
import { initials, sectionOf, sections } from './nav.js'
import { jobsStore } from './jobs.js'
import { chord, entries, keyFor, typing } from './palette.js'
import { server } from './server.js'
import { useHash, useStore } from './hooks.js'
import { Failed } from './parts.jsx'
import Hub from './Hub.jsx'
import JobsPanel from './JobsPanel.jsx'
import Palette from './Palette.jsx'
import { catalog } from './sections/Commands.jsx'
import Interviews from './sections/Interviews.jsx'
import KitDev from './sections/KitDev.jsx'
import Machine from './sections/Machine.jsx'
import Plan from './sections/Plan.jsx'
import Quality from './sections/Quality.jsx'
import Summary from './sections/Summary.jsx'
import Team from './sections/Team.jsx'
import { lang, t } from './i18n.js'

const MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

// The desktop app's UI. Three ways to be loaded: the hub (window.camaronHub, from disk: the start screen, Hub.jsx), a
// project's window (window.camaronApp, served by that project's server at /desktop/), or a browser that wandered to
// /desktop/ (neither: say where the app is).
export default function App() {
  if (typeof window !== 'undefined' && window.camaronHub) return <Hub hub={window.camaronHub} />
  if (typeof window !== 'undefined' && window.camaronApp) return <Project app={window.camaronApp} />
  return (
    <main className="dk-outside">
      <EmptyState title={t('outside.title')} action={<Button variant="primary" href="../#/">{t('outside.portal')}</Button>}>
        {t('outside.body')}
      </EmptyState>
    </main>
  )
}

// The main landmark takes the focus after a jump (a shortcut, the palette), so Tab goes on from the new section.
const focusMain = () => document.getElementById('main')?.focus({ preventScroll: true })

function Project({ app }) {
  const hash = useHash()
  const [index, setIndex] = useState(null)
  const [kitdev, setKitdev] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [palette, setPalette] = useState(false)
  const [commands, setCommands] = useState([])
  const srv = useMemo(() => server(app.token), [])
  const jobs = useMemo(() => jobsStore(srv.get), [])           // one for the window: it outlasts the sections
  const { running } = useStore(jobs)
  const projects = useProjects(app, index?.project, setStatus)
  const loadIndex = () => srv.get('tree').then((x) => { setIndex(x); setError('') }, (e) => setError(e.message))
  useEffect(() => {
    loadIndex()
    srv.get('app/info').then((i) => setKitdev(!!i.kitdev), () => {})
    jobs.refresh()
    return () => jobs.stop()
  }, [])
  const here = sectionOf(hash, { kitdev })
  const { project, machine } = sections({ kitdev })
  const all = [...project, ...machine]
  useEffect(() => {                                     // ⌘K / Ctrl K anywhere; g + a letter outside fields and dialogs
    let pending = 0
    const on = (e) => {
      if (e.key.toLowerCase() === 'k' && (e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey) { e.preventDefault(); setPalette(true); return }
      if (e.metaKey || e.ctrlKey || e.altKey || typing(e.target)) { pending = 0; return }
      const r = chord(pending, e.key, e.timeStamp, all)
      pending = r.pending
      if (r.go) { e.preventDefault(); location.hash = `#/${r.go}`; focusMain() }
    }
    addEventListener('keydown', on)
    return () => removeEventListener('keydown', on)
  }, [kitdev])
  useEffect(() => { if (palette) catalog(srv).then((c) => setCommands(c.commands), () => {}) }, [palette])
  const onPick = (it) => {
    if (it.project) projects.open(it.project)
    else if (it.action === 'add') app.hub?.()
    else if (it.href.startsWith('../')) location.href = it.href
    else { location.hash = it.href; focusMain() }
  }
  const link = (s) => (
    <a key={s} href={`#/${s}`} className={'dk-nav' + (s === here ? ' on' : '')} aria-current={s === here ? 'page' : undefined}>
      {t('nav.' + s)}<span className="dk-hint" aria-hidden="true"><Keys keys={['g', keyFor(s)]} /></span></a>
  )
  return (
    <div className="dk">
      <SkipLink target="main">{t('skip')}</SkipLink>
      <header className="dk-top">
        <Brand project={index?.project} href="#/summary" />
        <Breadcrumbs items={[{ label: index?.project || '…', href: '#/summary' }, { label: t('nav.' + here) }]} />
        <span className="dk-grow"></span>
        <button type="button" className="dk-find" aria-haspopup="dialog" onClick={() => setPalette(true)}>
          {t('pal.open')}<Keys keys={MAC ? ['⌘', 'K'] : ['Ctrl', 'K']} /></button>
        {/* no menu bar on screen (the header is the title bar): this opens the app menu under itself */}
        {app.menu && <button type="button" className="dk-icon" aria-label={t('appMenu')} title={t('appMenu')}
          onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); app.menu(r.left, r.bottom) }}>⋯</button>}
      </header>
      <Palette open={palette} onClose={() => setPalette(false)} onPick={onPick}
        groups={entries({ sections: all, projects: projects.list, commands, t, lang: lang() })} />
      <Rail app={app} projects={projects} />
      <nav className="dk-side" aria-label={t('nav.project')}>
        {project.map(link)}
        <span className="dk-gap"></span>
        <span className="eyebrow">{t('nav.app')}</span>
        {machine.map(link)}
      </nav>
      <main className="dk-main" id="main" tabIndex={-1}>
        {error && <Failed title={t('project.failed')} detail={error} onRetry={() => { setError(''); loadIndex() }} />}
        {!index && !error ? <Skeleton lines={4} /> : <Section here={here} srv={srv} jobs={jobs} app={app} />}
      </main>
      <JobsPanel srv={srv} jobs={jobs} />
      <footer className="dk-status">
        <span role="status">{status || (running[0] ? `${t('job.running')}: ${running[0].label || running[0].kind}` : '')}</span>
        <span className="dk-grow"></span>
        <span>{index ? `kit ${index.kit}` : ''}</span></footer>
    </div>
  )
}

// This machine's projects, this window's marked: another one opens in this window's place (the main process starts
// its server and stops this one). Until the list arrives, this project alone; a project opened by its folder but
// never listed comes first. The rail and the palette share it.
function useProjects(app, name, onStatus) {
  const [rows, setRows] = useState(null)
  const [busy, setBusy] = useState(false)          // one switch at a time: the other server takes seconds to start
  useEffect(() => { app.projects?.().then((r) => r?.projects && setRows(r.projects), () => {}) }, [])
  const open = async (p) => {
    if (busy) return
    setBusy(true)
    onStatus(t('hub.opening', { name: p.name }))
    const r = await app.switchTo(p.path).catch((e) => ({ error: e.message }))
    setBusy(false)
    onStatus(r?.error ? `${t('hub.error')}: ${r.error}` : '')
  }
  const self = name ? [{ name, path: '', exists: true, current: true }] : []
  const list = !rows ? self : rows.some((p) => p.current) ? rows : [...self, ...rows]    // opened but never listed
  return { list, busy, open }
}

function Rail({ app, projects: { list, busy, open } }) {
  return (
    <nav className="dk-rail" aria-label={t('rail')}>
      {list.map((p) => (p.current
        ? <a key={p.path || p.name} className="dk-proj on" href="#/summary" aria-current="true" title={p.name}>{initials(p.name)}</a>
        : <button key={p.path} type="button" className="dk-proj" disabled={!p.exists || busy} onClick={() => open(p)}
            title={p.exists ? p.name : `${p.name}: ${t('rail.missing')}`}>{initials(p.name)}</button>))}
      <button type="button" className="dk-proj add" aria-label={t('rail.add')} title={t('rail.add')} onClick={() => app.hub?.()}>+</button>
    </nav>
  )
}

const SECTIONS = { summary: Summary, plan: Plan, interviews: Interviews, team: Team, quality: Quality, docs: Docs, machine: Machine,
  kitdev: KitDev }
function Section({ here, ...props }) {
  const View = SECTIONS[here]
  return <View key={here} {...props} />
}

// Reading is the portal's (on this same server, one folder up): the app does not keep a second reader.
function Docs() {
  return (
    <div className="dk-page">
      <h1 className="t-impact">{t('nav.docs')}</h1>
      <div className="row">
        <Button variant="primary" href="../#/">{t('docs.read')}</Button>
        <Button href="../#/review">{t('docs.review')}</Button>
        <Button variant="ghost" href="../#/search">{t('docs.search')}</Button>
      </div>
    </div>
  )
}

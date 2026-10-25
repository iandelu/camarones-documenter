import { useEffect, useMemo, useState } from 'react'
import { Aviso, Brand, Breadcrumbs, Button, Card, EmptyState, Field, Skeleton } from '@camaron/ui'
import { initials, sectionOf, sections } from './nav.js'
import { jobsStore } from './jobs.js'
import { server } from './server.js'
import { useStore } from './hooks.js'
import JobsPanel from './JobsPanel.jsx'
import Interviews from './sections/Interviews.jsx'
import KitDev from './sections/KitDev.jsx'
import Machine from './sections/Machine.jsx'
import Plan from './sections/Plan.jsx'
import Quality from './sections/Quality.jsx'
import Summary from './sections/Summary.jsx'
import Team from './sections/Team.jsx'
import { t } from './i18n.js'

// The desktop app's UI. Three ways to be loaded: the hub (window.camaronHub, from disk: pick or make a project), a
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

function useHash() {
  const [hash, setHash] = useState(typeof location !== 'undefined' ? location.hash : '')
  useEffect(() => {
    const on = () => setHash(location.hash)
    addEventListener('hashchange', on)
    return () => removeEventListener('hashchange', on)
  }, [])
  return hash
}

function Project({ app }) {
  const hash = useHash()
  const [index, setIndex] = useState(null)
  const [kitdev, setKitdev] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const srv = useMemo(() => server(app.token), [])
  const jobs = useMemo(() => jobsStore(srv.get), [])           // one for the window: it outlasts the sections
  const { running } = useStore(jobs)
  useEffect(() => {
    srv.get('tree').then(setIndex, (e) => setError(e.message))
    srv.get('app/info').then((i) => setKitdev(!!i.kitdev), () => {})
    jobs.refresh()
    return () => jobs.stop()
  }, [])
  const here = sectionOf(hash, { kitdev })
  const { project, machine } = sections({ kitdev })
  const link = (s) => (
    <a key={s} href={`#/${s}`} className={'dk-nav' + (s === here ? ' on' : '')} aria-current={s === here ? 'page' : undefined}>
      {t('nav.' + s)}</a>
  )
  return (
    <div className="dk">
      <header className="dk-top">
        <Brand project={index?.project} href="#/summary" />
        <Breadcrumbs items={[{ label: index?.project || '…', href: '#/summary' }, { label: t('nav.' + here) }]} />
      </header>
      <Rail app={app} name={index?.project} onStatus={setStatus} />
      <nav className="dk-side" aria-label={t('nav.project')}>
        {project.map(link)}
        <span className="dk-gap"></span>
        <span className="eyebrow">{t('nav.app')}</span>
        {machine.map(link)}
      </nav>
      <main className="dk-main">
        {error && <Aviso tone="error" title={t('hub.failed')} detail={error} />}
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
// never listed comes first.
function Rail({ app, name, onStatus }) {
  const [rows, setRows] = useState(null)
  const [busy, setBusy] = useState(false)          // one switch at a time: the other server takes seconds to start
  useEffect(() => { app.projects?.().then((r) => r?.projects && setRows(r.projects), () => {}) }, [])
  const go = async (p) => {
    setBusy(true)
    onStatus(t('hub.opening', { name: p.name }))
    const r = await app.switchTo(p.path).catch((e) => ({ error: e.message }))
    setBusy(false)
    onStatus(r?.error ? `${t('hub.error')}: ${r.error}` : '')
  }
  const self = name ? [{ name, path: '', exists: true, current: true }] : []
  const list = !rows ? self : rows.some((p) => p.current) ? rows : [...self, ...rows]    // opened but never listed
  return (
    <nav className="dk-rail" aria-label={t('rail')}>
      {list.map((p) => (p.current
        ? <a key={p.path || p.name} className="dk-proj on" href="#/summary" aria-current="true" title={p.name}>{initials(p.name)}</a>
        : <button key={p.path} type="button" className="dk-proj" disabled={!p.exists || busy} onClick={() => go(p)}
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

// The hub: this machine's projects, and making, joining or adding one (the main process runs the CLI).
function Hub({ hub }) {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [form, setForm] = useState('')            // '' | 'new' | 'join'
  const [name, setName] = useState('')
  const [from, setFrom] = useState('')
  const [status, setStatus] = useState('')
  const load = () => hub.list().then((r) => (r.error ? setError(r.error) : setRows(r.projects)))
  useEffect(() => { load() }, [])
  const act = async (p) => {
    setStatus('')
    const r = await p
    if (r?.error) setStatus(`${t('hub.error')}: ${r.error}`)
    else if (!r?.cancelled) load()
  }
  const open = (p) => { setStatus(t('hub.opening', { name: p.name })); act(hub.open(p.path)) }
  return (
    <main className="dk-hub">
      <Brand />
      <h1 className="t-impact">{t('hub.title')}</h1>
      {error && <Aviso tone="error" title={t('hub.failed')} detail={error} />}
      {!rows && !error && <Skeleton lines={3} />}
      {rows && !rows.length && (
        <EmptyState title={t('hub.empty')} action={<Button variant="primary" onClick={() => setForm('new')}>{t('hub.new')}</Button>}>
          {t('hub.emptyBody')}</EmptyState>
      )}
      {rows?.length > 0 && (
        <ul className="dk-hub-list">
          {rows.map((p) => (
            <li key={p.path}><Card className="dk-hub-row">
              <span className="dk-proj">{initials(p.name)}</span>
              <span className="dk-hub-name"><b>{p.name}</b><span className="muted small">{p.path}</span></span>
              {p.exists ? <Button size="sm" onClick={() => open(p)}>{t('hub.open')}</Button>
                : <span className="muted small">{t('rail.missing')}</span>}
            </Card></li>
          ))}
        </ul>
      )}
      <div className="row">
        <Button variant={rows?.length ? 'secondary' : 'ghost'} onClick={() => setForm('new')}>{t('hub.new')}</Button>
        <Button onClick={() => setForm('join')}>{t('hub.join')}</Button>
        <Button variant="ghost" onClick={() => act(hub.add())}>{t('hub.add')}</Button>
      </div>
      {form && (
        <Card as="form" className="dk-hub-form" onSubmit={(e) => {
          e.preventDefault()
          act(form === 'new' ? hub.create(name, from) : hub.join(name))
        }}>
          <Field id="h-name" label={t(form === 'new' ? 'hub.name' : 'hub.url')} value={name} onChange={(e) => setName(e.target.value)} required />
          {form === 'new' && <Field id="h-from" label={t('hub.from')} value={from} onChange={(e) => setFrom(e.target.value)} />}
          <div className="row"><Button variant="primary" type="submit">{t(form === 'new' ? 'hub.create' : 'hub.joinGo')}</Button>
            <Button variant="ghost" onClick={() => setForm('')}>{t('cancel')}</Button></div>
        </Card>
      )}
      {status && <p className="muted small" role="status">{status}</p>}
    </main>
  )
}

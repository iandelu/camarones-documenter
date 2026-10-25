import { useEffect, useState } from 'react'
import { Aviso, Brand, Breadcrumbs, Button, Card, EmptyState, Field, Skeleton } from '@camaron/ui'
import { initials, sectionOf, sections, TALLER_OF } from './nav.js'
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

// The project's server, one folder up from /desktop/; the app's token on every request (lib/serve.py checks it).
export const api = (app) => async (name) => {
  const r = await fetch(`../api/${name}`, { headers: { 'X-Camaron-Token': app.token } })
  const data = await r.json()
  if (!r.ok) throw new Error(data.error || r.statusText)
  return data
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
  useEffect(() => {
    const get = api(app)
    get('tree').then(setIndex, (e) => setError(e.message))
    get('app/info').then((i) => setKitdev(!!i.kitdev), () => {})
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
        {!index && !error ? <Skeleton lines={4} /> : <Soon section={here} />}
      </main>
      <section className="dk-jobs" aria-label={t('jobs')}>
        <span className="eyebrow">{t('jobs')}</span><span className="muted small">{t('jobs.none')}</span>
      </section>
      <footer className="dk-status"><span role="status">{status}</span><span className="dk-grow"></span>
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

// A section not rebuilt here yet: one way to it, where it still is.
function Soon({ section }) {
  return (
    <div className="dk-page">
      <h1 className="t-impact">{t('nav.' + section)}</h1>
      <EmptyState title={t('soon.title')} action={<Button variant="primary" href={`../${TALLER_OF[section]}`}>{t('soon.open')}</Button>}>
        {t('soon.body')}
      </EmptyState>
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

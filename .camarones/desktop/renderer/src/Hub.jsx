import { useEffect, useState } from 'react'
import { Aviso, Brand, Button, Card, Chip, Field, Skeleton } from '@camaron/ui'
import { Failed } from './parts.jsx'
import { adoptSay, BADGE, card, errorKey, JOIN0, joinOnce, names } from './hub.js'
import { t } from './i18n.js'

// The start screen (the hub window, loaded from disk): what do you want to document. Pick a folder (the CLI says what
// it is, the person confirms, it becomes a project), join the team's cam-docs, or open a recent project. Everything
// goes through window.camaronHub (preload.cjs) to the main process, which runs the CLI and opens the project window.

// Text with `code` spans.
const rich = (s) => s.split('`').map((part, i) => (i % 2 ? <code key={i}>{part}</code> : part))

// The two option icons: inline SVG, the one exception to text glyphs (CAMARON.md).
const svg = { className: 'dk-option-icon', viewBox: '0 0 24 24', 'aria-hidden': true, fill: 'none', stroke: 'currentColor',
  strokeWidth: 1.75, strokeLinecap: 'round', strokeLinejoin: 'round' }
const FolderIcon = () => (
  <svg {...svg}><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" /></svg>
)
const UsersIcon = () => (
  <svg {...svg}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg>
)

// One line per screen in the hub's own words; an error also shows the CLI's line, as it is.
function Say({ say }) {
  if (!say) return null
  const text = t(say.key, say.vars)
  if (say.error) return <Aviso tone="error" title={text} detail={say.detail || undefined} />
  return <p className="muted small" role="status">{text}</p>
}

export default function Hub({ hub }) {
  const [view, setView] = useState('start')              // start | join | found
  const [busy, setBusy] = useState(false)
  const [say, setSay] = useState(null)
  const [rows, setRows] = useState(null)
  const [listError, setListError] = useState('')
  const [found, setFound] = useState(null)               // {dir, info}: the folder picked and what the CLI says it is
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [js, setJs] = useState(JOIN0)                     // the join form's token state (hub.js joinStep)

  const load = () => hub.list().then((r) => (r?.error ? setListError(r.error) : setRows(r?.projects || [])),
    (e) => setListError(e.message))
  useEffect(() => { load() }, [])
  const go = (v) => { setView(v); setSay(null); setJs(JOIN0); window.scrollTo?.(0, 0) }
  const work = async (fn) => {
    setBusy(true)
    try { await fn() } catch (e) { setSay({ key: 'hub.failed', detail: e.message, error: true }) } finally { setBusy(false) }
  }

  const open = (p) => work(async () => {
    setSay({ key: 'hub.opening', vars: { name: p.name } })
    const r = await hub.open(p.path)
    setSay(r && r.ok === false ? { key: 'hub.openFailed', detail: r.error, error: true } : null)
  })

  // Pick a folder → what I found (inspect never writes) → the person's Continue (adopt).
  const look = async (dir) => {
    const r = await hub.inspect(dir)
    if (!r?.found) return setSay({ key: errorKey('folder'), detail: r?.detail, error: true })
    setFound({ dir, info: r.found })
    setName(r.found.name || '')
    setView('found')
    setSay(null)
  }
  const pick = () => work(async () => {
    const p = await hub.pick()
    if (!p?.dir) return
    setSay({ key: 'hub.looking' })
    await look(p.dir)
  })
  // Code without git: only this click runs git init; then the folder is read again (it becomes a repo or an umbrella).
  const gitInit = () => work(async () => {
    setSay({ key: 'hub.gitIniting' })
    const r = await hub.gitInit(found.dir)
    if (!r || r.error) return setSay({ key: errorKey(r?.error === 'folder' ? 'folder' : 'git-init'), detail: r?.detail, error: true })
    await look(found.dir)
  })
  const c = found ? card(found.info) : null
  const adopt = (e) => {
    e.preventDefault()
    if (!c?.canContinue) return
    const n = c.askName ? name.trim() || undefined : undefined       // a project keeps the name it has
    if (n?.startsWith('-')) return setSay({ key: 'hub.badName', error: true })
    work(async () => {
      setSay({ key: 'hub.preparing' })
      setSay(adoptSay(found.info, await hub.adopt(found.dir, n)))
    })
  }

  // Join: the URL, then the folder (the main process asks); a token only when the host asked for one.
  const join = (e) => {
    e.preventDefault()
    const u = url.trim()
    if (!u) return
    if (u.startsWith('-')) return setSay({ key: 'hub.badUrl', error: true })
    const token = js.showToken ? js.token.trim() : undefined
    if (token === '') return
    work(async () => {
      setSay({ key: 'hub.joiningNow' })
      const next = await joinOnce(hub, js, u, token)                   // never throws: a rejection clears the token too
      setJs(next)
      setSay(next.say)
    })
  }
  // another URL may be another host: the token (and folder) asked for the old one no longer apply
  const onUrl = (e) => {
    setUrl(e.target.value)
    if (js.showToken) { setJs(JOIN0); setSay(null) }
  }

  const back = <button type="button" className="dk-back" disabled={busy} onClick={() => go('start')}>{t('hub.back')}</button>
  return (<>
    <header className="dk-titlebar"><Brand /></header>
    {view === 'start' && (
      <main className="dk-hub">
        <h1 className="t-impact">{t('hub.title')}</h1>
        <p className="dk-lede">{t('hub.lede')}</p>
        <ul className="dk-options">
          <li className="dk-option primary"><FolderIcon />
            <div className="dk-option-text"><h2>{t('hub.pickTitle')}</h2><p>{t('hub.pickHelp')}</p></div>
            <Button variant="primary" disabled={busy} onClick={pick}>{t('hub.pick')}</Button></li>
          <li className="dk-option"><UsersIcon />
            <div className="dk-option-text"><h2>{t('hub.joinTitle')}</h2><p>{rich(t('hub.joinHelp'))}</p></div>
            <Button disabled={busy} onClick={() => { setUrl(''); go('join') }}>{t('hub.join')}</Button></li>
        </ul>
        <Say say={say} />
        {listError && <Failed title={t('hub.listFailed')} detail={listError} onRetry={() => { setListError(''); load() }} />}
        {!rows && !listError && <Skeleton lines={2} />}
        {rows?.length > 0 && (                         // first run: nothing recent, the two options are the whole screen
          <section className="dk-recent">
            <h2 className="eyebrow">{t('hub.recent')}</h2>
            <ul className="dk-recent-list">
              {rows.map((p) => (
                <li key={p.path}>
                  <span className="dk-recent-name"><b>{p.name}</b><code className="muted small">{p.path}</code></span>
                  {p.exists ? <Button size="sm" disabled={busy} onClick={() => open(p)}>{t('hub.open')}</Button>
                    : <span className="muted small">{t('rail.missing')}</span>}
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    )}
    {view === 'join' && (
      <main className="dk-hub">
        {back}
        <h1 className="t-impact">{t('hub.joinTitle')}</h1>
        <p className="dk-lede">{rich(t('hub.joinHelp'))}</p>
        <Card as="form" className="dk-hub-form" onSubmit={join}>
          <Field id="h-url" className="cu-input dk-mono" label={t('hub.urlLabel')} value={url} onChange={onUrl} required autoFocus
            disabled={busy} autoComplete="off" spellCheck={false} placeholder="https://gitlab.com/shop/cam-docs.git" />
          {js.showToken && (<div className="dk-token">
            <Field id="h-token" className="cu-input dk-mono" type="password" label={t('hub.tokenLabel', { host: js.host })}
              value={js.token} onChange={(e) => setJs({ ...js, token: e.target.value })} required autoFocus disabled={busy}
              autoComplete="off" spellCheck={false} />
            <p className="muted small">{t('hub.tokenHelp')}</p>
          </div>)}
          <Say say={say} />
          <div className="row dk-end">
            <Button variant="ghost" disabled={busy} onClick={() => go('start')}>{t('cancel')}</Button>
            <Button variant="primary" type="submit" disabled={busy}>{t(js.showToken ? 'hub.tokenGo' : 'hub.joinGo')}</Button>
          </div>
        </Card>
      </main>
    )}
    {view === 'found' && c && (
      <Found c={c} back={back} busy={busy} say={say} name={name} setName={setName} onPick={pick} onGitInit={gitInit}
        onAdopt={adopt} />
    )}
  </>)
}

// What I found, one card per case (hub.js card), then the name and the way on: Continue, or only what the card allows.
export function Found({ c, back, busy, say, name, setName, onPick, onGitInit, onAdopt }) {
  return (
    <main className="dk-hub">
      {back}
      <h1 className="t-impact">{t('hub.foundTitle')}</h1>
      <Card as="article" className="dk-found">
        <span><Chip state={BADGE[c.badge]}>{t('hub.badge.' + c.badge)}</Chip></span>
        <h2>{t(c.titleKey, c.titleVars)}</h2>
        <p>{[names(c.lead || []), t(c.bodyKey)].filter(Boolean).join('. ')}</p>
        {c.siblingsKey && <p className="small">{t(c.siblingsKey, { n: c.siblings.length, names: names(c.siblings) })}</p>}
        {c.warningKey && (
          <Aviso tone="warn" title={t(c.warningKey + 'Title')} action={c.action === 'gitInit'
            ? <Button variant="primary" disabled={busy} autoFocus onClick={onGitInit}>{t('hub.gitInit')}</Button> : null}>
            {t(c.warningKey)}</Aviso>
        )}
        <p className="dk-dest"><span className="muted">cam-docs →</span> <code>{c.dest}</code></p>
      </Card>
      <form className="dk-hub-form" onSubmit={onAdopt}>
        {c.canContinue && c.askName && <Field id="h-name" label={t('hub.name')} value={name}
          onChange={(e) => setName(e.target.value)} autoComplete="off" spellCheck={false} />}
        <Say say={say} />
        <div className="row dk-end">
          {/* with nothing else to do here, changing the folder is the one way on */}
          <Button variant={c.canContinue || c.action ? 'ghost' : 'primary'} disabled={busy} onClick={onPick}>{t('hub.change')}</Button>
          {c.canContinue && <Button variant="primary" type="submit" disabled={busy} autoFocus>{t('hub.continue')}</Button>}
        </div>
      </form>
    </main>
  )
}

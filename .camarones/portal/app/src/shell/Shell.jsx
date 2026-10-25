import { Fragment, useEffect, useRef, useState } from 'react'
import { MotionConfig } from 'motion/react'
import { Brand, Breadcrumbs, Chip, Keys } from '@camaron/ui'
import '@camaron/ui/ui.css'
import Native from '../Native.jsx'
import { t as tr } from '../i18n.js'
import { resolve } from '../router.js'
import { crumbs, locate, zonesFor } from '../zones.js'
import './shell.css'

// The portal's shell: header, the sidebar that stays, and the hash router. A view not migrated to React yet is
// painted by the plain scripts (window.CamaronLegacy, public/legacy/app.js) into the #main, #toc and #tree slots,
// which React renders empty and never touches again.
const L = () => window.CamaronLegacy
const MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

function useRouter() {
  const [shown, setShown] = useState(null)        // the action on screen: { kind: 'native' | 'legacy', … }
  const queue = useRef({ seq: 0, chain: Promise.resolve() })

  // One view renders at a time and a newer address skips the queued ones, so a slow page never paints over the next.
  const go = () => {
    const q = queue.current
    const seq = ++q.seq
    const run = q.chain.then(async () => {
      if (seq !== q.seq) return
      const legacy = L()
      const a = resolve(location.hash, { mode: legacy.mode(), current: legacy.current(),
        space: (p) => legacy.byPath(p)?.space, hrefFor: legacy.hrefFor })
      if (a.kind === 'redirect') return location.replace(a.to)
      if (a.kind === 'scroll') return legacy.scroll(a.anchor)
      legacy.closePalette()
      document.body.classList.toggle('native-mode', a.kind === 'native')   // before painting: #main must be visible
      document.body.classList.remove('nav-open')
      setShown({ ...a, at: seq })
      if (a.kind === 'native') return legacy.leave()
      await legacy.run(a.fn, a.args)
    })
    q.chain = run.catch(() => {})                  // one address that fails must not stop the next ones
    return run
  }
  return [shown, go]
}

export default function Shell() {
  const [ready, setReady] = useState(false)
  const [failed, setFailed] = useState('')
  const [shown, go] = useRouter()

  useEffect(() => {
    window.CamaronShell = { go }                    // legacy route(): after a save, a language or theme change
    const onHash = () => go()
    const onKey = (e) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || '')
      if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !typing)) { e.preventDefault(); L().openPalette() }
    }
    addEventListener('hashchange', onHash)
    addEventListener('keydown', onKey)
    L().boot().then(() => { setReady(true); go() }, (e) => setFailed(e.message || String(e)))
    return () => { removeEventListener('hashchange', onHash); removeEventListener('keydown', onKey) }
  }, [])

  const legacy = L()
  const t = legacy.t
  const index = ready ? legacy.tree() : null
  const mode = legacy.mode()
  return (
    <>
      <header className="top">
        <button className="ghost icon menu" type="button" aria-label={t('menu')} title={t('menu')}
          onClick={() => document.body.classList.toggle('nav-open')}>☰</button>
        <Brand project={index?.project} href="#/" />
        {index && <Crumbs index={index} mode={mode} t={t} />}
        <button className="searchbtn" type="button" aria-label={t('search')} onClick={() => legacy.openPalette()}>
          <span className="searchbtn-label">{t('search')}</span><span className="searchbtn-glyph" aria-hidden="true">⌕</span>
          <Keys keys={MAC ? ['⌘', 'K'] : ['Ctrl', 'K']} />
        </button>
        <div className="tools">
          {index && <Summary s={index.summary || {}} feedback={index.feedback} t={t} />}
          {index && <Language index={index} legacy={legacy} onChange={go} />}
          <button className="ghost icon" type="button" aria-label={tr('shell.theme')} title={tr('shell.theme')}
            onClick={() => { legacy.toggleTheme(); go() }}>◐</button>
        </div>
      </header>
      {legacy.isStatic() && <div className="ro aviso" dangerouslySetInnerHTML={{ __html: t('readOnly') }} />}
      <div className="layout" id="layout">
        <aside className="side" id="side">
          {index && <ZoneNav index={index} mode={mode} t={t} />}
          <div id="side-head"></div>
          <nav id="tree" aria-label={t('docs')}></nav>
        </aside>
        <main id="main" className="main">
          {failed && <div className="page"><h1>{t('unreachable')}</h1><p>{failed}</p></div>}
        </main>
        {shown?.kind === 'native' && (
          <section id="native" className="main native">
            <MotionConfig reducedMotion="user"><Native view={shown.view} arg={shown.arg || null} /></MotionConfig>
          </section>
        )}
        <aside className="toc empty" id="toc"></aside>
      </div>
      <div id="scrim" onClick={() => document.body.classList.remove('nav-open')}></div>
    </>
  )
}

// The address as a path: zone › section › page. The brand is the way home.
function Crumbs({ index, mode, t }) {
  const label = (c) => (!c.key ? c.text : c.key.startsWith('sec.') ? L().sectionLabel(c.key.slice(4)) : t(c.key))
  const items = crumbs(location.hash, mode, index).map((c) => ({ label: label(c), href: c.href }))
  return items.length ? <Breadcrumbs items={items} /> : <span className="crumbs-room" />
}

// Every zone the mode has, always on screen; the current zone opens to its views.
function ZoneNav({ index, mode, t }) {
  const here = locate(location.hash)
  const zones = zonesFor(mode, index)
  return (
    <nav className="shell-nav" aria-label={tr('shell.nav')}>
      <a href="#/" className={!here.zone && !location.hash.startsWith('#/search') ? 'on' : ''}>{t('home')}</a>
      {zones.map((z) => {
        const on = z.id === here.zone
        const views = z.views.length > 1 || z.views[0]?.href !== z.href ? z.views : []
        return (
          <Fragment key={z.id}>
            <a href={z.href} className={on ? 'on' : ''} aria-current={on && !here.view ? 'page' : undefined}>{t('zone.' + z.id)}</a>
            {on && views.map((v) => (
              <a key={v.id} href={v.href} className={'sub' + (v.id === here.view ? ' on' : '')}
                aria-current={v.id === here.view ? 'page' : undefined}>{t('view.' + v.id)}</a>
            ))}
          </Fragment>
        )
      })}
    </nav>
  )
}

// The docs' trust, in words: what is confirmed, what is a draft, what needs another look.
function Summary({ s, feedback, t }) {
  return (
    <span className="summary">
      <Chip state="ok">{`${s.confirmed || 0} ${t('trust.confirmed')}`}</Chip>
      {s.draft > 0 && <Chip state="warn">{`${s.draft} ${t('trust.draft')}`}</Chip>}
      {s['needs-reconfirm'] > 0 && <Chip state="info">{`${s['needs-reconfirm']} ${t('trust.needs-reconfirm')}`}</Chip>}
      {feedback > 0 && <Chip>{`${feedback} ${t('changeRequests')}`}</Chip>}
    </span>
  )
}

function Language({ index, legacy, onChange }) {
  const langs = ['', ...(index.langs || [])]
  if (langs.length < 2) return null
  return (
    <select aria-label={tr('shell.lang')} value={langs.includes(legacy.lang()) ? legacy.lang() : ''}
      onChange={(e) => { legacy.setLang(e.target.value); onChange() }}>
      {langs.map((l) => <option key={l} value={l}>{legacy.langName(l || 'en')}</option>)}
    </select>
  )
}

import { Fragment, useEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { Brand, Breadcrumbs, Button, Chip, Keys, SkipLink } from '@camaron/ui'
import '@camaron/ui/ui.css'
import Native from '../Native.jsx'
import Palette from '../views/Palette.jsx'
import DocsTree, { audience } from '../views/DocsTree.jsx'
import { WikiSide } from '../views/Wikis.jsx'
import { CodeSide } from '../views/CodeMap.jsx'
import { ArchSide } from '../views/C4.jsx'
import { drawToc, scrollToAnchor, wireDocs } from '../content/doc.js'
import { t as tr } from '../i18n.js'
import { APP } from '../api.js'
import { resolve } from '../router.js'
import { crumbs, locate, zonesFor } from '../zones.js'
import { core } from '../core.js'
import './shell.css'
import '../views/views.css'

// The portal's shell: header, the sidebar that stays, and the hash router (src/router.js) that picks the view.
const TREE_VIEWS = ['docs', 'doc', 'new']          // the views with the docs tree (DocsTree) under the zones
const WIKI_VIEWS = ['wikis', 'wikigraph', 'wikipage']
const VIEWER_VIEWS = ['wikigraph', 'code', 'c4']    // full width, no padding: a visualizer, a graph, a diagram
const MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

function useRouter(onRoute) {
  const [shown, setShown] = useState(null)        // the view on screen: { view, arg, at }
  const queue = useRef({ seq: 0, chain: Promise.resolve() })

  // One view renders at a time and a newer address skips the queued ones, so a slow page never paints over the next.
  const go = () => {
    const q = queue.current
    const seq = ++q.seq
    const run = q.chain.then(async () => {
      if (seq !== q.seq) return
      const a = resolve(location.hash, { mode: core.mode(), current: core.current(),
        space: (p) => core.byPath(p)?.space, hrefFor: core.hrefFor,
        firstView: (id) => zonesFor(core.mode(), core.tree()).find((z) => z.id === id)?.views[0]?.href })
      if (a.kind === 'redirect') return location.replace(a.to)
      if (a.kind === 'scroll') return scrollToAnchor(a.anchor)
      onRoute()
      core.setCurrent('')                           // the doc views set it once their page is on screen
      drawToc(null)
      document.body.classList.remove('nav-open')
      document.body.classList.toggle('viewer-mode', VIEWER_VIEWS.includes(a.view))
      flushSync(() => setShown({ ...a, at: seq }))
    })
    q.chain = run.catch(() => {})                  // one address that fails must not stop the next ones
    return run
  }
  return [shown, go]
}

export default function Shell() {
  const [ready, setReady] = useState(false)
  const [failed, setFailed] = useState('')
  const [palette, setPalette] = useState(false)
  const [shown, go] = useRouter(() => setPalette(false))

  useEffect(() => {
    window.CamaronShell = { go }                    // views re-show the address after a save, a language or theme change
    const onHash = () => go()
    const onKey = (e) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || '')
      if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !typing)) { e.preventDefault(); setPalette(true) }
    }
    addEventListener('hashchange', onHash)
    addEventListener('keydown', onKey)
    document.body.classList.add('native-mode')
    document.documentElement.classList.toggle('in-app', !!APP)   // the header is the window's title bar (portal.css)
    document.body.dataset.audience = audience()      // `:::tech` blocks follow the reader's audience (DocsTree)
    wireDocs()
    core.boot().then(() => { setReady(true); go() }, (e) => setFailed(e.message || String(e)))
    return () => { removeEventListener('hashchange', onHash); removeEventListener('keydown', onKey) }
  }, [])

  const t = core.t
  const index = ready ? core.tree() : null
  const mode = core.mode()
  return (
    <>
      <SkipLink target="native">{tr('shell.skip')}</SkipLink>
      <header className="top">
        <button className="ghost icon menu" type="button" aria-label={t('menu')} title={t('menu')}
          onClick={() => document.body.classList.toggle('nav-open')}>☰</button>
        <Brand project={index?.project} href="#/" />
        {index && <Crumbs index={index} mode={mode} t={t} />}
        <button className="searchbtn" type="button" aria-label={t('search')} aria-haspopup="dialog" onClick={() => setPalette(true)}>
          <span className="searchbtn-label">{t('search')}</span><span className="searchbtn-glyph" aria-hidden="true">⌕</span>
          <Keys keys={MAC ? ['⌘', 'K'] : ['Ctrl', 'K']} />
        </button>
        <div className="tools">
          {/* in the desktop app: its own UI is one folder down on this server (desktop/renderer) */}
          {APP && <Button variant="ghost" size="sm" href="./desktop/#/summary">{tr('shell.app')}</Button>}
          {index && <Summary s={index.summary || {}} feedback={index.feedback} t={t} />}
          {index && <Language index={index} core={core} onChange={go} />}
          <button className="ghost icon" type="button" aria-label={tr('shell.theme')} title={tr('shell.theme')}
            onClick={() => { core.toggleTheme(); go() }}>◐</button>
          {/* the app has no menu bar on screen (its header is the title bar): this opens the app menu under itself */}
          {APP?.menu && <button className="ghost icon" type="button" aria-label={t('appMenu')} title={t('appMenu')}
            onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); APP.menu(r.left, r.bottom) }}>⋯</button>}
        </div>
      </header>
      {core.isStatic() && <div id="ro" className="ro aviso" dangerouslySetInnerHTML={{ __html: t('readOnly') }} />}
      <div className="layout" id="layout">
        <aside className="side" id="side">
          {index && <ZoneNav index={index} mode={mode} t={t} />}
          {shown && <Side shown={shown} go={go} />}
        </aside>
        <main id="native" className="main native" tabIndex={-1}>
          {failed && <div className="page"><h1>{t('unreachable')}</h1><p>{failed}</p></div>}
          {shown && <Native key={shown.at} view={shown.view} arg={shown.arg || null} />}
        </main>
      </div>
      <div id="scrim" onClick={() => document.body.classList.remove('nav-open')}></div>
      {ready && <Palette open={palette} onClose={() => setPalette(false)} />}
    </>
  )
}

// Under the zones, what the view lists: the docs tree, a wiki's pages, the C4 views, the repos with a code map.
function Side({ shown, go }) {
  if (TREE_VIEWS.includes(shown.view))
    return <DocsTree key={shown.at} active={shown.view === 'doc' ? (shown.arg || '').split('::')[0] : ''} onChange={go} />
  if (WIKI_VIEWS.includes(shown.view)) {
    const [where] = (shown.arg || '').split('::')
    const [repo, ...rel] = where.split('/')
    return <WikiSide key={shown.at} repo={shown.view === 'wikis' ? '' : repo}
      page={shown.view === 'wikigraph' ? 'graph' : rel.length ? `repos/${repo}/${rel.join('/')}` : ''} />
  }
  if (shown.view === 'code') return <CodeSide key={shown.at} arg={shown.arg} />
  if (shown.view === 'c4') return <ArchSide key={shown.at} arg={shown.arg} />
  return null
}

// The address as a path: zone › section › page. The brand is the way home.
function Crumbs({ index, mode, t }) {
  const label = (c) => (!c.key ? c.text : c.key.startsWith('sec.') ? core.sectionLabel(c.key.slice(4)) : t(c.key))
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
            <a href={z.views[0]?.href || z.href} className={on ? 'on' : ''}>{t('zone.' + z.id)}</a>
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

function Language({ index, core, onChange }) {
  const langs = ['', ...(index.langs || [])]
  if (langs.length < 2) return null
  return (
    <select aria-label={tr('shell.lang')} value={langs.includes(core.lang()) ? core.lang() : ''}
      onChange={(e) => { core.setLang(e.target.value); onChange() }}>
      {langs.map((l) => <option key={l} value={l}>{core.langName(l || 'en')}</option>)}
    </select>
  )
}

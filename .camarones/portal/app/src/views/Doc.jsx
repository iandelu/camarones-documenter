import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Chip, Skeleton } from '@camaron/ui'
import { postJSON } from '../api.js'
import { docsGet } from '../docsApi.js'
import { t as tr } from '../i18n.js'
import { pageBanners, pager } from './docpage.js'
import Editor from './Editor.jsx'
import Sources, { FreshIcon } from './Sources.jsx'
import { pageFresh } from './sources.js'
import { mountDoc, render } from '../content/doc.js'
import { readerTrees } from './DocsTree.jsx'
import { adrStatusLabel, adrTone } from './tree.js'
import { core } from '../core.js'

const STATE = { draft: 'warn', 'needs-reconfirm': 'info', confirmed: 'ok' }
const TONE = { info: 'info', warn: 'warn' }

// #/docs/<path>::<anchor>: one page — its state, the banners that matter, the actions a person can take (edit,
// confirm, ask for a change), the body, where it comes from and the pages around it. The body is drawn by the
// docs renderer (src/content/doc.js: Markdown, Mermaid, C4 embeds, the outline).
export default function Doc({ arg }) {
  const [path, anchor] = (arg || '').split('::')
  const trees = readerTrees(path)
  return <DocView path={path} anchor={anchor} order={core.byPath(path)?.space === 'notes' ? trees.notesOrder : trees.order} />
}

// The page itself, also for a wiki page: `order` drives the pager; `extra` (actions), `banner` and `after` (below
// the body) are what the wiki adds — its graph, the note on an old wiki, the pages that link here.
export function DocView({ path, anchor, order, extra = null, banner = null, after = null }) {
  const t = core.t
  const live = core.mode() !== 'static'
  const lang = core.lang()
  const [d, setD] = useState(null)
  const [english, setEnglish] = useState(null)
  const [error, setError] = useState('')
  const [panel, setPanel] = useState('')          // '' | 'confirm' | 'feedback'
  const [editing, setEditing] = useState(false)
  const body = useRef(null)

  useEffect(() => {
    docsGet('doc', { path, lang, track: 1 }).then(async (page) => {
      setEnglish(lang && !page.exists ? await docsGet('doc', { path }) : null)
      setD(page)
    }, (e) => setError(e.message))
  }, [path])

  useEffect(() => {                                     // the body, once the page is on screen
    if (!d || editing || !body.current) return
    body.current.innerHTML = ''
    mountDoc(body.current, d.exists ? d.raw : english?.exists ? english.raw : t('emptyPage'), path, anchor, d.exists ? d.blocks : [])
    core.setCurrent(path)
  }, [d, editing])

  if (error) return <div className="page"><Aviso tone="error" title={t('error')} detail={error} /></div>
  if (!d) return <div className="docpage"><article className="page"><Skeleton lines={6} /></article></div>
  if (editing) return <Editor d={d} onDone={() => setEditing(false)} />

  const row = core.byPath(path) || {}
  const title = d.exists ? d.title : english?.title || row.title || d.title
  const around = pager(order, path)
  const sources = (d.sources?.length ? d.sources : english?.sources) || []      // a missing translation has none of its own
  const changed = async (msg) => { core.toast(msg); await core.reload(); window.CamaronShell.go() }
  return (
    <div className="docpage">
      <article className="page">
        <h1>{title}</h1>
        {row.description && <p className="lead">{row.description}</p>}
        <div className="meta">
          {row.adr_status && <Chip state={adrTone(row.adr_status)}>{t(adrStatusLabel(row.adr_status))}</Chip>}
          <Chip state={STATE[d.trust]}>{t('trust.' + d.trust)}</Chip>
          {d.fresh && (
            <span className="fresh-pill" data-state={pageFresh(d.fresh)} title={t('freshHint.' + pageFresh(d.fresh))}>
              <FreshIcon state={pageFresh(d.fresh)} />{t('fresh.' + pageFresh(d.fresh))}</span>
          )}
          {d.confirmed?.by && <span className="small muted">{t('confirmedBy')} {d.confirmed.by} · {String(d.confirmed.at).slice(0, 10)}</span>}
          {d.owner === 'human' && <span className="small muted">{t('humanOwned')}</span>}
          <code className="file" title={d.file}>{d.file}</code>
          <span className="actions">
            {extra}
            {!live && core.tree().editBase && (
              <Button size="sm" variant="ghost" href={core.tree().editBase + d.file} target="_blank" rel="noopener">
                {t('editForge')} <span aria-hidden="true">↗</span></Button>)}
            {live && <Button size="sm" onClick={() => setEditing(true)}>{t('edit')}</Button>}
            {live && d.trust !== 'confirmed' && (
              <Button size="sm" variant="primary" aria-expanded={panel === 'confirm'} onClick={() => setPanel(panel === 'confirm' ? '' : 'confirm')}>
                {t('confirm')}</Button>)}
            {live && <Button size="sm" variant="ghost" aria-expanded={panel === 'feedback'}
              onClick={() => setPanel(panel === 'feedback' ? '' : 'feedback')}>{t('requestChange')}</Button>}
          </span>
        </div>
        {pageBanners(d, row, lang).map((b) => (
          <Aviso key={b.key + (b.adr?.id || '')} tone={TONE[b.tone]} title={t(b.key, { lang: core.langName(lang), id: b.adr?.id })}
            detail={b.code || undefined} action={b.adr && <a href={core.hrefFor(b.adr.path)}>{b.adr.title}</a>} />
        ))}
        {banner}
        {panel === 'confirm' && <ConfirmPanel d={d} t={t} onDone={() => changed(t('confirmedToast'))} onCancel={() => setPanel('')} />}
        {panel === 'feedback' && <FeedbackPanel d={d} body={body} t={t} onDone={() => changed(t('commentSaved'))} onCancel={() => setPanel('')} />}
        {d.feedback?.length > 0 && (
          <div className="box"><b>{t('pendingComments')}</b><ul className="list">{d.feedback.map((f) => <li key={f}>{f.slice(6)}</li>)}</ul></div>
        )}
        <div ref={body}></div>
        {after}
        {around && (
          <nav className="pager" aria-label={t('prev') + ' / ' + t('next')}>
            {around.prev ? <a className="prev" href={core.hrefFor(around.prev)}><span className="muted small">← {t('prev')}</span>
              <b>{core.byPath(around.prev)?.title || around.prev}</b></a> : <span></span>}
            {around.next ? <a className="next" href={core.hrefFor(around.next)}><span className="muted small">{t('next')} →</span>
              <b>{core.byPath(around.next)?.title || around.next}</b></a> : <span></span>}
          </nav>
        )}
      </article>
      <aside className="doc-aside">
        <div id="toc" className="toc empty"></div>
        {sources.length > 0 && <Sources entries={d.sourceInfo?.length ? d.sourceInfo : english?.sourceInfo} refs={sources} />}
      </aside>
    </div>
  )
}

function ConfirmPanel({ d, t, onDone, onCancel }) {
  const [by, setBy] = useState(core.tree().reviewer || '')
  const [error, setError] = useState('')
  const go = async () => {
    try { await postJSON('confirm', { path: d.path, lang: core.lang(), by }); onDone() } catch (e) { setError(e.message) }
  }
  return (
    <div className="box doc-panel">
      <b>{t('confirmTitle')}</b>
      <p className="muted">{t('confirmHelp')}</p>
      {error && <Aviso tone="error" title={t('error')} detail={error} />}
      <div className="row">
        <input className="cu-input" value={by} onChange={(e) => setBy(e.target.value)} placeholder={t('yourName')} aria-label={t('yourName')} />
        <Button variant="primary" disabled={!by.trim()} onClick={go}>{t('confirm')}</Button>
        <Button variant="ghost" onClick={onCancel}>{t('cancel')}</Button>
      </div>
    </div>
  )
}

// A comment for the next AI session; it can point at one section (its slug and a short quote of what follows it).
function FeedbackPanel({ d, body, t, onDone, onCancel }) {
  const sections = [...(body.current?.querySelectorAll('.doc h2') || [])]
  const [slug, setSlug] = useState('')
  const [text, setText] = useState('')
  const [by, setBy] = useState(core.tree().reviewer || '')
  const [error, setError] = useState('')
  // The Board's add form, with a link to this page (and section) filled in. In a translation the link points at the
  // source page: the same H2 by position.
  const toBoard = async () => {
    let section = slug
    if (section && core.lang() && d.exists) {
      const i = sections.findIndex((h) => h.id === 'h-' + section)
      const src = await docsGet('doc', { path: d.path })
      section = (render(src.raw || '', d.path).querySelectorAll('h2')[i]?.id || '').slice(2)
    }
    location.hash = `#/kanban/new?path=${encodeURIComponent(d.path)}${section ? `&section=${encodeURIComponent(section)}` : ''}`
  }
  const go = async () => {
    const heading = slug && document.getElementById('h-' + slug)
    let snippet = ''
    for (let n = heading?.nextElementSibling; n && !/^H[12]$/.test(n.tagName) && snippet.length < 80; n = n.nextElementSibling)
      snippet += ' ' + n.textContent.trim()
    try {
      await postJSON('feedback', { path: d.path, text, by, slug, snippet: snippet.trim().slice(0, 80) })
      onDone()
    } catch (e) { setError(e.message) }
  }
  return (
    <div className="box doc-panel">
      <b>{t('requestChange')}</b>
      <p className="muted">{t('fbHelp')}</p>
      {error && <Aviso tone="error" title={t('error')} detail={error} />}
      <div className="row">
        {sections.length > 0 && <><label className="small muted" htmlFor="f-sec">{t('section')}</label>
          <select id="f-sec" value={slug} onChange={(e) => setSlug(e.target.value)}>
            <option value="">{t('wholePage')}</option>
            {sections.map((h) => <option key={h.id} value={h.id.slice(2)}>{h.dataset.title}</option>)}
          </select></>}
        <Button size="sm" variant="ghost" title={t('createItemHint')} onClick={toBoard}>{t('createItem')} <span aria-hidden="true">→</span></Button>
      </div>
      <textarea rows="4" value={text} onChange={(e) => setText(e.target.value)} aria-label={t('requestChange')} />
      <div className="row">
        <input className="cu-input" value={by} onChange={(e) => setBy(e.target.value)} placeholder={t('yourName')} aria-label={t('yourName')} />
        <Button variant="primary" disabled={!text.trim()} onClick={go}>{t('send')}</Button>
        <Button variant="ghost" onClick={onCancel}>{t('cancel')}</Button>
      </div>
    </div>
  )
}

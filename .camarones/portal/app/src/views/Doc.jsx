import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Chip, Skeleton } from '@camaron/ui'
import { postJSON } from '../api.js'
import { docsGet } from '../docsApi.js'
import { t as tr } from '../i18n.js'
import { pageBanners, pager } from './docpage.js'
import Editor from './Editor.jsx'

const L = () => window.CamaronLegacy
const STATE = { draft: 'warn', 'needs-reconfirm': 'info', confirmed: 'ok' }
const TONE = { info: 'info', warn: 'warn' }

// #/docs/<path>::<anchor>: one page — its state, the banners that matter, the actions a person can take (edit,
// confirm, ask for a change), the body, where it comes from and the pages around it. The body is still drawn by the
// docs renderer of the plain scripts (legacy/doc.js: Markdown, Mermaid, C4 embeds, the outline).
export default function Doc({ arg }) {
  const [path, anchor] = (arg || '').split('::')
  const legacy = L()
  const t = legacy.t
  const live = legacy.mode() !== 'static'
  const lang = legacy.lang()
  const [d, setD] = useState(null)
  const [english, setEnglish] = useState(null)
  const [error, setError] = useState('')
  const [panel, setPanel] = useState('')          // '' | 'confirm' | 'feedback'
  const [editing, setEditing] = useState(false)
  const body = useRef(null)

  useEffect(() => {
    legacy.drawDocsSide(path)
    docsGet('doc', { path, lang, track: 1 }).then(async (page) => {
      setEnglish(lang && !page.exists ? await docsGet('doc', { path }) : null)
      setD(page)
    }, (e) => setError(e.message))
  }, [path])

  useEffect(() => {                                     // the body, once the page is on screen
    if (!d || editing || !body.current) return
    body.current.innerHTML = ''
    legacy.mountDoc(body.current, d.exists ? d.raw : english?.exists ? english.raw : t('emptyPage'), path, anchor)
    legacy.setCurrent(path)
  }, [d, editing])

  if (error) return <div className="page"><Aviso tone="error" title={t('error')} detail={error} /></div>
  if (!d) return <div className="docpage"><article className="page"><Skeleton lines={6} /></article></div>
  if (editing) return <Editor d={d} onDone={() => setEditing(false)} />

  const row = legacy.byPath(path) || {}
  const title = d.exists ? d.title : english?.title || row.title || d.title
  const order = row.space === 'notes' ? legacy.notesOrder() : legacy.docsOrder()
  const around = pager(order, path)
  const changed = async (msg) => { legacy.toast(msg); await legacy.reload(); window.CamaronShell.go() }
  return (
    <div className="docpage">
      <article className="page">
        <h1>{title}</h1>
        {row.description && <p className="lead">{row.description}</p>}
        <div className="meta">
          <Chip state={STATE[d.trust]}>{t('trust.' + d.trust)}</Chip>
          {d.confirmed?.by && <span className="small muted">{t('confirmedBy')} {d.confirmed.by} · {String(d.confirmed.at).slice(0, 10)}</span>}
          {d.owner === 'human' && <span className="small muted">{t('humanOwned')}</span>}
          <code className="file" title={d.file}>{d.file}</code>
          <span className="actions">
            {!live && legacy.tree().editBase && (
              <Button size="sm" variant="ghost" href={legacy.tree().editBase + d.file} target="_blank" rel="noopener">
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
          <Aviso key={b.key} tone={TONE[b.tone]} title={t(b.key, { lang: legacy.langName(lang) })} detail={b.code || undefined} />
        ))}
        {panel === 'confirm' && <ConfirmPanel d={d} t={t} onDone={() => changed(t('confirmedToast'))} onCancel={() => setPanel('')} />}
        {panel === 'feedback' && <FeedbackPanel d={d} body={body} t={t} onDone={() => changed(t('commentSaved'))} onCancel={() => setPanel('')} />}
        {d.feedback?.length > 0 && (
          <div className="box"><b>{t('pendingComments')}</b><ul className="list">{d.feedback.map((f) => <li key={f}>{f.slice(6)}</li>)}</ul></div>
        )}
        <div ref={body}></div>
        {around && (
          <nav className="pager" aria-label={t('prev') + ' / ' + t('next')}>
            {around.prev ? <a className="prev" href={legacy.hrefFor(around.prev)}><span className="muted small">← {t('prev')}</span>
              <b>{legacy.byPath(around.prev)?.title || around.prev}</b></a> : <span></span>}
            {around.next ? <a className="next" href={legacy.hrefFor(around.next)}><span className="muted small">{t('next')} →</span>
              <b>{legacy.byPath(around.next)?.title || around.next}</b></a> : <span></span>}
          </nav>
        )}
      </article>
      <aside className="doc-aside">
        <div id="toc" className="toc empty"></div>
        {d.sources?.length > 0 && (
          <div className="cu-card doc-sources">
            <span className="eyebrow">{t('sources')} · {d.sources.length}</span>
            <ul>{d.sources.map((s) => <li key={s}><code title={s}>{s}</code></li>)}</ul>
          </div>
        )}
      </aside>
    </div>
  )
}

function ConfirmPanel({ d, t, onDone, onCancel }) {
  const [by, setBy] = useState(L().tree().reviewer || '')
  const [error, setError] = useState('')
  const go = async () => {
    try { await postJSON('confirm', { path: d.path, lang: L().lang(), by }); onDone() } catch (e) { setError(e.message) }
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
  const [by, setBy] = useState(L().tree().reviewer || '')
  const [error, setError] = useState('')
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
      {sections.length > 0 && (
        <div className="row"><label className="small muted" htmlFor="f-sec">{t('section')}</label>
          <select id="f-sec" value={slug} onChange={(e) => setSlug(e.target.value)}>
            <option value="">{t('wholePage')}</option>
            {sections.map((h) => <option key={h.id} value={h.id.slice(2)}>{h.dataset.title}</option>)}
          </select></div>
      )}
      <textarea rows="4" value={text} onChange={(e) => setText(e.target.value)} aria-label={t('requestChange')} />
      <div className="row">
        <input className="cu-input" value={by} onChange={(e) => setBy(e.target.value)} placeholder={t('yourName')} aria-label={t('yourName')} />
        <Button variant="primary" disabled={!text.trim()} onClick={go}>{t('send')}</Button>
        <Button variant="ghost" onClick={onCancel}>{t('cancel')}</Button>
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Aviso, Button, Chip, EmptyState, Skeleton } from '@camaron/ui'
import { postJSON } from '../api.js'
import { docsGet } from '../docsApi.js'
import { t as tr } from '../i18n.js'
import { changedRepos, FILTERS, filterQueue, queueCounts } from './review.js'
import { core } from '../core.js'

const STATE = { draft: 'warn', 'needs-reconfirm': 'info', confirmed: 'ok' }

// #/review: the pages that wait for a person, confirmed one by one or several at once, each with where it comes from.
// Below, what else waits: review requests, change requests, code that moved, the checks.
export default function Review() {
  const t = core.t
  const live = core.mode() !== 'static'
  const [s, setS] = useState(null)
  const [requests, setRequests] = useState([])
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all')
  const [picked, setPicked] = useState(() => new Set())
  const [focus, setFocus] = useState(0)
  const [by, setBy] = useState(core.tree().reviewer || '')
  const [busy, setBusy] = useState(false)
  const load = () => {
    docsGet('status').then(setS, (e) => setError(e.message))
    if (live) docsGet('reviews').then(setRequests, () => setRequests([]))
  }
  useEffect(load, [])

  const rows = s ? filterQueue(s.queue, filter) : []
  const at = Math.min(focus, Math.max(rows.length - 1, 0))
  const toggle = (p) => setPicked((cur) => { const n = new Set(cur); n.has(p) ? n.delete(p) : n.add(p); return n })

  useEffect(() => {                                       // j / k move, x marks, Enter opens (not while typing)
    const onKey = (e) => {
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || '') || e.metaKey || e.ctrlKey) return
      if (e.key === 'j' || e.key === 'k') setFocus((f) => Math.max(0, Math.min(rows.length - 1, f + (e.key === 'j' ? 1 : -1))))
      else if (e.key === 'x' && live && rows[at]) toggle(rows[at].path)
      else if (e.key === 'Enter' && rows[at] && document.activeElement === document.body) location.hash = core.hrefFor(rows[at].path)
    }
    addEventListener('keydown', onKey)
    return () => removeEventListener('keydown', onKey)
  }, [rows, at])

  const confirmPicked = async () => {
    setBusy(true)
    setError('')
    try {
      for (const path of picked) await postJSON('confirm', { path, lang: core.lang(), by })
      core.toast(t('confirmedToast'))
      setPicked(new Set())
      await core.reload()
      load()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  if (error && !s) return <div className="page"><Aviso tone="error" title={tr('review.loadFailed')} detail={error} /></div>
  if (!s) return <div className="page"><Skeleton lines={5} /></div>
  const counts = queueCounts(s.queue)
  const shownPicked = rows.filter((r) => picked.has(r.path))
  return (
    <div className="page wide review">
      <h1 className="t-impact">{tr('review.title')} <span className="t-eco">
        {s.queue.length ? tr('review.waiting', { n: s.queue.length }) : tr('review.none')}</span></h1>
      {s.queue.length > 0 && (
        <div className="rv-filters" role="group" aria-label={t('filter')}>
          {FILTERS.map((f) => (
            <Button key={f} size="sm" variant={f === filter ? 'primary' : 'secondary'} aria-pressed={f === filter}
              onClick={() => { setFilter(f); setFocus(0) }}>{tr('review.f.' + f)} · {counts[f]}</Button>
          ))}
        </div>
      )}
      {error && <Aviso tone="error" title={tr('review.failed')} detail={error} />}
      {!s.queue.length && <EmptyState title={t('allConfirmed')} action={<Button href="#/docs">{t('docs')}</Button>} />}
      {rows.length > 0 && (
        <div className="rv-split">
          <section className="cu-card rv-list" aria-label={t('waiting')}>
            {live && (
              <div className="rv-bar">
                <span className="muted small">{tr('review.selected', { n: shownPicked.length })}</span>
                <label className="rv-by"><span className="sr-only">{tr('review.by')}</span>
                  <input className="cu-input" value={by} onChange={(e) => setBy(e.target.value)} placeholder={tr('review.by')} /></label>
                <Button variant="primary" size="sm" disabled={!shownPicked.length || !by.trim() || busy} onClick={confirmPicked}>
                  {tr('review.confirmN', { n: shownPicked.length })}</Button>
              </div>
            )}
            <ul role="list">
              {rows.map((r, i) => (
                <li key={r.path} className={'rv-row' + (i === at ? ' on' : '') + (picked.has(r.path) ? ' picked' : '')}
                  onMouseEnter={() => setFocus(i)}>
                  {live && <input type="checkbox" checked={picked.has(r.path)} onChange={() => toggle(r.path)}
                    aria-label={r.title} />}
                  <span className="rv-title"><a href={core.hrefFor(r.path)}>{r.title}</a>
                    <span className="muted small">{r.path}</span></span>
                  <Chip state={STATE[r.trust]}>{t('trust.' + r.trust)}</Chip>
                </li>
              ))}
            </ul>
            <p className="muted small rv-keys">{tr('review.keys')}</p>
          </section>
          <Preview path={rows[at]?.path} t={t} />
        </div>
      )}
      {live && requests.length > 0 && <Requests requests={requests} by={by} t={t} onDone={load} />}
      <More s={s} t={t} />
    </div>
  )
}

// Where the focused page comes from: its sources (x-sources), so a person can check it against the code.
function Preview({ path, t }) {
  const [doc, setDoc] = useState(null)
  useEffect(() => {
    setDoc(null)
    if (path) docsGet('doc', { path }).then(setDoc, () => setDoc({ sources: [] }))
  }, [path])
  return (
    <aside className="cu-card rv-preview" aria-live="polite">
      {!path ? <p className="muted small">{tr('review.pick')}</p> : !doc ? <Skeleton lines={3} /> : (
        <>
          <span className="eyebrow">{tr('review.from')}</span>
          {doc.sources?.length ? <ul className="list">{doc.sources.map((x) => <li key={x}><code>{x}</code></li>)}</ul>
            : <p className="muted small">{t('none')}</p>}
          <Button size="sm" href={core.hrefFor(path)}>{tr('review.open')} <span aria-hidden="true">→</span></Button>
        </>
      )}
    </aside>
  )
}

// Review requests (an agent asked a person to approve its work): approve, or ask for changes saying which.
function Requests({ requests, by, t, onDone }) {
  const [text, setText] = useState({})
  const [error, setError] = useState('')
  const decide = async (r, decision) => {
    const comments = (text[r.id] || '').trim()
    if (decision === 'changes' && !comments) return
    try { await postJSON('review/decide', { id: r.id, decision, comments, by }); core.toast(t('decided')); onDone() }
    catch (e) { setError(e.message) }
  }
  return (
    <section className="cu-card rv-requests">
      <b>{t('reviewRequests')} · {requests.length}</b>
      {error && <Aviso tone="error" title={t('error')} detail={error} />}
      <ul className="list">
        {requests.map((r) => (
          <li key={r.id} className="rv">
            <a href={core.hrefFor(r.path)}>{core.byPath(r.path)?.title || r.path}</a>
            <span className="muted small"> {r.by}{r.note ? ' · ' + r.note : ''}</span>
            <div className="row">
              <Button size="sm" variant="primary" onClick={() => decide(r, 'approve')}>{t('approve')}</Button>
              <input className="cu-input" value={text[r.id] || ''} placeholder={t('whatChanges')} aria-label={t('whatChanges')}
                onChange={(e) => setText({ ...text, [r.id]: e.target.value })} />
              <Button size="sm" disabled={!(text[r.id] || '').trim()} onClick={() => decide(r, 'changes')}>{t('askChanges')}</Button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function More({ s, t }) {
  const repos = changedRepos(s.changes)
  const checks = s.check ? [...s.check.errors.map((m) => ['bad', m]), ...s.check.warnings.map((m) => ['warn', m])] : []
  if (!s.feedback.length && !repos.length && !checks.length) return null
  return (
    <details className="cu-card rv-more">
      <summary><b>{tr('review.more')}</b> <span className="muted small">
        {[s.feedback.length && `${t('changeRequests')} · ${s.feedback.length}`, repos.length && `${t('codeChanged')} · ${repos.length}`,
          checks.length && `${t('checks')} · ${checks.length}`].filter(Boolean).join(' — ')}</span></summary>
      {s.feedback.length > 0 && <><h3>{t('changeRequests')}</h3><ul className="list">{s.feedback.map((f) => <li key={f}>{f.slice(6)}</li>)}</ul></>}
      {repos.length > 0 && <><h3>{t('codeChanged')}</h3><ul className="list">{repos.map((r) => (
        <li key={r.repo}><b>{r.repo}</b> — {r.status}{r.files ? ` (${r.files} ${t('files')})` : ''}</li>))}</ul>
        <p className="muted small">{t('askAgent')}</p></>}
      {checks.length > 0 && <><h3>{t('checks')}</h3><ul className="list">{checks.map(([tone, m]) => (
        <li key={m}><Chip state={tone}>{tr(tone === 'bad' ? 'review.err' : 'review.warn')}</Chip> {m}</li>))}</ul></>}
    </details>
  )
}

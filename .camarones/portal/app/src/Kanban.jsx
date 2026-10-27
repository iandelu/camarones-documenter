import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getJSON, postJSON } from './api.js'
import { lang, t } from './i18n.js'
import { Skeleton } from '@camaron/ui'
import Failed from './Failed.jsx'
import { applyFilters, blockedText, columns, dropAnchor, keyMove, parentOf, parseArg, STATUS_LABELS, waveOf } from './kanban.js'

// The Board (spec §7): the project's Backlog.md board in cam-docs/backlog/, six columns, a card's goal, the docs it
// links and its history. Anyone on localhost reads it; writes need the machine token (the app, or `camaron up`).
const fmt = (key, vars = {}) => t(key).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? '')
const statusLabel = (s) => (STATUS_LABELS[lang()] || STATUS_LABELS.en)[s] || s
const known = (key, fallback) => { const v = t(key); return v === key ? fallback : v }
const typeLabel = (ty) => known(`kbt.${ty}`, ty)
const splitList = (s) => s.split(',').map((x) => x.trim()).filter(Boolean)
const sectionOf = (link) => String(link || '').match(/#([^@]+)/)?.[1] || ''
const when = (iso) => { try { return new Date(iso).toLocaleString(document.documentElement.lang || 'en', { dateStyle: 'medium', timeStyle: 'short' }) } catch { return iso } }
const kindLabel = (k) => known(`kanban.kind.${k}`, k)
const NO_FILTERS = { repo: '', epic: '', label: '', docs: '', parent: '' }
const KEYS = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', ' ', 'Enter', 'Escape']

// A side panel takes the focus when it opens (its `data-first` field, else itself), Escape closes it, and the focus
// goes back to whatever opened it (a card, the Add button) if that is still on the page.
function useDrawer(onClose) {
  const ref = useRef(null)
  useEffect(() => {
    const opener = document.activeElement
    const el = ref.current
    ;(el?.querySelector('[data-first]:not(:disabled)') || el)?.focus()
    return () => { if (opener && opener !== document.body && opener.isConnected) opener.focus() }
  }, [])
  const onKeyDown = (e) => { if (e.key === 'Escape') { e.stopPropagation(); onClose() } }
  return { ref, onKeyDown, tabIndex: -1 }
}

// The columns as drawn: while a card is grabbed with the keyboard it shows where it would land.
function placed(cols, kb) {
  if (!kb?.grabbed) return cols
  let moving = null
  const out = cols.map((c) => ({ ...c, cards: c.cards.filter((x) => (x.id === kb.focus ? ((moving = x), false) : true)) }))
  if (moving) out[kb.col].cards.splice(kb.row, 0, moving)
  return out
}

function Card({ card, story, wave, grabbed, writable, onKey, onOpen, onDragStart, onDragEnd, refFor }) {
  const suspect = (card.links || []).some((l) => l.fresh === 'suspect' || l.fresh === 'stale')
  const blocked = card.blocked_by || []
  const why = blocked.length ? fmt('kanban.blocked', { ids: blockedText(blocked, kindLabel) }) : ''
  return (
    <div ref={refFor(card.id)} className={`kb-card${grabbed ? ' grabbed' : ''}`} role="button" tabIndex={0}
         aria-grabbed={writable ? grabbed : undefined} aria-describedby="kb-help" draggable={writable}
         onKeyDown={(e) => onKey(e, card)} onClick={() => onOpen(card.id)}
         onDragStart={(e) => onDragStart(e, card)} onDragEnd={onDragEnd}>
      <span className="kb-card-top"><span className="card-id">{card.id}</span><span className={`kb-type t-${card.type}`}>{typeLabel(card.type)}</span>
        {card.priority ? <span className="kb-prio">{card.priority}</span> : null}
        {wave ? <span className="kb-wave">{fmt('kanban.wave', { n: wave })}</span> : null}
        {why ? <span className="kb-blocked" title={why}>{t('kanban.blockedBadge')}<span className="sr-only">: {why}</span></span> : null}</span>
      {story ? <span className="kb-sub" title={fmt('kanban.sub', { id: story })}><span aria-hidden="true">↳ {story}</span>
        <span className="sr-only">{fmt('kanban.sub', { id: story })}</span></span> : null}
      <span className="kb-card-title">{card.title}</span>
      <span className="card-meta">
        {[card.assignee?.[0] && `@${card.assignee[0]}`, !story && card.epic, ...(card.repos || [])].filter(Boolean).join(' · ')}
        {card.docs?.length ? <span className={suspect ? 'kb-docs warn' : 'kb-docs'}>{card.assignee?.[0] || (!story && card.epic) || card.repos?.length ? ' · ' : ''}{fmt(card.docs.length === 1 ? 'kbDocsOne' : 'kbDocsMany', { n: card.docs.length })}{suspect ? ` (${t('kbf.suspect')})` : ''}</span> : null}
      </span>
    </div>
  )
}

function Detail({ id, onClose }) {
  const drawer = useDrawer(onClose)
  const [item, setItem] = useState(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('goal')
  useEffect(() => {
    setItem(null); setError('')
    getJSON(`kanban/item?id=${encodeURIComponent(id)}`).then(setItem, (e) => setError(e.message))
  }, [id])
  const TABS = ['goal', 'knowledge', 'history', 'plan', 'runs', 'evidence']
  const tabKey = { goal: 'kbGoal', knowledge: 'kbKnowledge', history: 'kbHistory', plan: 'kbPlan', runs: 'kbRuns', evidence: 'kbEvidence' }
  return (
    <aside className="drawer kb-drawer" aria-label={id} {...drawer}>
      <button className="close" onClick={onClose} aria-label={t('kbClose')}>×</button>
      <h2>{id}</h2>
      {error ? <p className="error" role="alert">{error}</p> : !item ? <p className="muted">{t('kbLoadingCard')}</p> : (
        <>
          <p className="kb-detail-title">{item.title}</p>
          <dl>
            <div><dt>{t('kbStatus')}</dt><dd>{statusLabel(item.status)}</dd></div>
            <div><dt>{t('kbType')}</dt><dd>{typeLabel(item.type)}</dd></div>
            {item.priority ? <div><dt>{t('kbPriority')}</dt><dd>{item.priority}</dd></div> : null}
            {item.assignee?.length ? <div><dt>{t('kbAssignee')}</dt><dd>{item.assignee.join(', ')}</dd></div> : null}
            {item.epic ? <div><dt>{t('kbEpic')}</dt><dd>{item.epic}</dd></div> : null}
            {item.repos?.length ? <div><dt>{t('kbRepos')}</dt><dd>{item.repos.join(', ')}</dd></div> : null}
            <div><dt>{t('kbFile')}</dt><dd>{item.file}</dd></div>
          </dl>
          <div className="seg kb-tabs" role="tablist">
            {TABS.map((k) => (
              <button key={k} role="tab" id={`kb-tab-${k}`} aria-selected={tab === k} aria-controls="kb-tabpanel"
                      className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{t(tabKey[k])}</button>
            ))}
          </div>
          <div id="kb-tabpanel" role="tabpanel" aria-labelledby={`kb-tab-${tab}`}>
            {tab === 'goal' ? (
              <>
                <h3>{t('kbDescription')}</h3>
                {item.description ? <p className="kb-desc">{item.description}</p> : <p className="muted">{t('kbNoDescription')}</p>}
                <h3>{t('kbCriteria')}</h3>
                {item.criteria?.length ? <ul className="kb-checks">{item.criteria.map((c) => (
                  <li key={c.n}><span aria-hidden="true">{c.done ? '☑' : '☐'}</span> <code>{item.id}/AC-{c.n}</code> {c.text}</li>))}</ul>
                  : <p className="muted">{t('kbNothing')}</p>}
                <h3>{t('kbDod')}</h3>
                {item.dod?.length ? <ul className="kb-checks">{item.dod.map((c) => (
                  <li key={c.n}><span aria-hidden="true">{c.done ? '☑' : '☐'}</span> {c.text}</li>))}</ul>
                  : <p className="muted">{t('kbNothing')}</p>}
              </>
            ) : tab === 'knowledge' ? (
              item.links?.length ? <ul className="kb-links">{item.links.map((l) => {
                const sec = sectionOf(l.link)
                return (
                  <li key={l.link}>
                    {l.path ? <a href={`#/docs/${l.path}${sec ? `::${sec}` : ''}`}>{l.title || l.path}{sec ? ` § ${sec}` : ''}</a> : <code>{l.link}</code>}
                    {l.trust ? <span className={`pill trust ${l.trust}`}>{known(`kbtr.${l.trust}`, l.trust)}</span> : null}
                    {l.fresh === 'suspect' || l.fresh === 'stale' ? <span className="pill warn">{t(`kbf.${l.fresh}`)}</span> : null}
                    {l.changed ? <span className="pill warn">{t('kbChanged')}</span> : null}
                    {l.missing ? <span className="pill bad">{t('kbMissing')}</span> : null}
                  </li>)
              })}</ul> : <p className="muted">{t('kbNoLinks')}</p>
            ) : tab === 'history' ? (
              item.history?.length ? <ul className="kb-history">{[...item.history].reverse().map((h, i) => (
                <li key={i}><span className="muted">{when(h.at)}</span> <b>{h.by}</b> <span>{h.what}</span>
                  {h.hash ? <code> {h.hash}</code> : null}</li>))}</ul> : <p className="muted">{t('kbNoHistory')}</p>
            ) : <p className="muted">{t('kbLater')}</p>}
          </div>
        </>
      )}
    </aside>
  )
}

function AddForm({ board, prefill, writable, onClose, onCreated }) {
  const drawer = useDrawer(onClose)
  const [f, setF] = useState({ type: 'story', title: '', epic: '', repos: '', labels: '', priority: '',
    path: prefill?.path || '', section: prefill?.section || '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  async function submit(e) {
    e.preventDefault()
    if (!f.title.trim()) return setError(t('kbNeedTitle'))
    setBusy(true); setError('')
    try {
      const row = await postJSON('kanban/add', { type: f.type, title: f.title, epic: f.epic || null, repos: splitList(f.repos),
        labels: splitList(f.labels), priority: f.priority || null,
        docs: f.path.trim() ? [{ path: f.path.trim(), section: f.section.trim() }] : [] })
      onCreated(row)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  const off = !writable || busy
  return (
    <aside className="drawer kb-drawer" aria-labelledby="kb-add-h" {...drawer}>
      <button className="close" onClick={onClose} aria-label={t('kbClose')}>×</button>
      <h2 id="kb-add-h">{t('kbAddTitle')}</h2>
      <form className="kb-form" onSubmit={submit}>
        <fieldset disabled={off}>
          <label>{t('kbType')}<select className="co-input" value={f.type} onChange={set('type')}>
            {board.types.map((ty) => <option key={ty} value={ty}>{typeLabel(ty)}</option>)}</select></label>
          <label>{t('kbTitleField')}<input className="co-input" value={f.title} onChange={set('title')} required data-first /></label>
          <label>{t('kbEpic')}<select className="co-input" value={f.epic} onChange={set('epic')}>
            <option value="">{t('kbNone')}</option>
            {board.epics.map((ep) => <option key={ep.id} value={ep.id}>{ep.id} · {ep.title}</option>)}</select></label>
          <label>{t('kbRepos')} <small className="muted">({t('kbCommaHint')})</small>
            <input className="co-input" value={f.repos} onChange={set('repos')} list="kb-repos" /></label>
          <datalist id="kb-repos">{board.repos.map((r) => <option key={r} value={r} />)}</datalist>
          <label>{t('kbLabels')} <small className="muted">({t('kbCommaHint')})</small>
            <input className="co-input" value={f.labels} onChange={set('labels')} /></label>
          <label>{t('kbPriority')}<select className="co-input" value={f.priority} onChange={set('priority')}>
            <option value="">{t('kbNone')}</option>
            {board.priorities.map((p) => <option key={p} value={p}>{p}</option>)}</select></label>
          <label>{t('kbDoc')}<input className="co-input" value={f.path} onChange={set('path')} placeholder="flows/payments.md" /></label>
          <label>{t('kbSection')}<input className="co-input" value={f.section} onChange={set('section')} placeholder="retries" /></label>
          <div className="row kb-form-actions">
            <button type="submit">{t('kbCreate')}</button>
            <button type="button" className="ghost" onClick={onClose}>{t('kbCancel')}</button>
          </div>
        </fieldset>
        {error ? <p className="error" role="alert">{error}</p> : null}
      </form>
    </aside>
  )
}

// The start gate said no: what the card waits for or collides with, and the choice to move it anyway (a person may;
// agents never can). The focus goes to Cancel, the safe answer; Escape cancels.
function ForceMove({ gate, onCancel, onForce }) {
  const ref = useRef(null)
  useEffect(() => { ref.current?.focus() }, [])
  return (
    <div className="aviso kb-gate" role="alertdialog" aria-labelledby="kb-gate-q"
         onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); onCancel() } }}>
      <p id="kb-gate-q">{fmt('kanban.forceAsk', { id: gate.id })}</p>
      <ul className="kb-gate-list">{gate.blocked.map((b) => (
        <li key={`${b.id}:${b.kind}`}><b>{b.id}</b> {kindLabel(b.kind)}{b.files?.length ? <> · <code>{b.files.join(', ')}</code></> : null}</li>))}</ul>
      <div className="row kb-form-actions">
        <button type="button" ref={ref} className="ghost" onClick={onCancel}>{t('kbCancel')}</button>
        <button type="button" onClick={onForce}>{t('kanban.force')}</button>
      </div>
    </div>
  )
}

export default function Kanban({ arg }) {
  const [board, setBoard] = useState(null)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState(NO_FILTERS)
  const [gate, setGate] = useState(null)               // a move the start gate refused: {id, status, anchor, blocked}
  const [open, setOpen] = useState(null)
  const [adding, setAdding] = useState(null)
  const [kb, setKb] = useState(null)
  const [say, setSay] = useState('')
  const [notice, setNotice] = useState('')
  const [over, setOver] = useState(null)
  const nodes = useRef({})
  const dragged = useRef(null)
  const refFor = useCallback((id) => (el) => { if (el) nodes.current[id] = el; else delete nodes.current[id] }, [])

  const load = useCallback(() => getJSON('kanban').then((b) => { setBoard(b); setError('') }, (e) => setError(e.message)), [])
  useEffect(() => { load() }, [load])
  useEffect(() => {                  // #/kanban/new?… opens the add form, #/kanban/WI-3 a card, #/kanban?parent=WI-14 filters
    const a = parseArg(arg)
    if (a.add) { setAdding(a.add); setOpen(null) } else if (a.open) { setOpen(a.open); setAdding(null) }
    setFilters((f) => ({ ...f, parent: a.parent || '' }))
  }, [arg])
  useEffect(() => {                                    // the card keeps the focus when a move redraws it elsewhere
    const el = kb?.focus && nodes.current[kb.focus]
    const active = document.activeElement
    if (el && (kb.grabbed || !active || active === document.body || active === el)) el.focus()
  }, [kb, board])

  const shown = useMemo(() => (board ? applyFilters(board.cards, filters) : []), [board, filters])
  const cols = useMemo(() => (board ? columns(shown, board.statuses) : []), [board, shown])
  const drawn = useMemo(() => placed(cols, kb), [cols, kb])
  const writable = !!board?.writable
  const byId = useMemo(() => Object.fromEntries((board?.cards || []).map((c) => [c.id, c])), [board])
  const waves = useMemo(() => waveOf(board?.cards || []), [board])

  // Back to the bare address (the crumbs follow it); the board stays mounted (Native keys it by view only).
  const closeArg = () => { if (/^#\/kanban\/./.test(location.hash)) location.replace(filters.parent ? `#/kanban?parent=${filters.parent}` : '#/kanban') }
  const clearFilters = () => { setFilters(NO_FILTERS); if (/^#\/kanban\?/.test(location.hash)) location.replace('#/kanban') }
  const close = () => { setOpen(null); setAdding(null); closeArg() }

  // A move into In Progress passes the start gate: refused (409 with blocked_by), the person may move it anyway.
  async function move(id, status, anchor, force = false) {
    const card = board.cards.find((c) => c.id === id)
    if (!card || (!force && card.status === status && !anchor.before && !anchor.after)) return
    setNotice(''); setGate(null)
    try {
      await postJSON('kanban/move', { id, status, ...anchor, ...(force ? { force: true } : {}) })
      setSay(fmt('kbMoved', { id, status: statusLabel(status) }))
      await load()
    } catch (e) {
      if (e.status === 409 && e.data?.blocked_by?.length && !force) setGate({ id, status, anchor, blocked: e.data.blocked_by })
      else setNotice(`${t('kbMoveFailed')} ${e.message}`)
      await load()
    }
  }

  function onKey(e, card) {
    if (!KEYS.includes(e.key) || e.target !== e.currentTarget) return
    e.preventDefault()
    const col = cols.findIndex((c) => c.cards.some((x) => x.id === card.id))
    const start = kb && kb.focus === card.id ? kb : { focus: card.id, grabbed: false, col, row: cols[col].cards.findIndex((x) => x.id === card.id) }
    if (e.key === ' ' && !start.grabbed && !writable) return
    const next = keyMove(start, e.key, cols)
    if (next.open) { setKb({ ...next, open: undefined }); return setOpen(next.open) }
    if (next.drop) {
      const { id, status, ...anchor } = next.drop
      setKb({ focus: id, grabbed: false, col: next.col, row: next.row })
      return move(id, status, anchor)
    }
    if (next.grabbed && !start.grabbed) setSay(fmt('kbGrabbed', { id: card.id }))
    else if (next.grabbed) setSay(fmt('kbOver', { id: card.id, status: statusLabel(cols[next.col].status), n: next.row + 1 }))
    else if (start.grabbed && e.key === 'Escape') setSay(fmt('kbCancelled', { id: card.id }))
    setKb(next)
  }

  function onDragStart(e, card) {
    dragged.current = card.id
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', card.id)
  }
  function dropIndex(e, colEl) {
    const els = [...colEl.querySelectorAll('.kb-card')].filter((el) => el !== nodes.current[dragged.current])
    const i = els.findIndex((el) => { const r = el.getBoundingClientRect(); return e.clientY < r.top + r.height / 2 })
    const idx = i < 0 ? els.length : i
    const all = [...colEl.querySelectorAll('.kb-card')]              // the index in the column as shown (dropAnchor's input)
    return els[idx] ? all.indexOf(els[idx]) : all.length
  }
  function onDrop(e, col) {
    e.preventDefault()
    setOver(null)
    const id = dragged.current || e.dataTransfer.getData('text/plain')
    dragged.current = null
    if (!id || !writable) return
    move(id, col.status, dropAnchor(col.cards, dropIndex(e, e.currentTarget), id))
  }

  if (error) return <section className="view kanban"><h1>{t('kbTitle')}</h1><Failed title={t('kbFailed')} detail={error} onRetry={() => { setError(''); load() }} /></section>
  if (!board) return <section className="view kanban"><h1>{t('kbTitle')}</h1><Skeleton lines={4} /></section>

  const readOnly = !writable ? <p className="aviso kb-ro" role="status">{t('kbReadOnly')}</p> : null
  if (!board.enabled) {
    return (
      <section className="view kanban">
        <h1>{t('kbTitle')}</h1>
        {readOnly}
        <p className="lede">{t('kbOff')}</p>
        <p className="muted">{t('kbOffCli')}</p>
        <button type="button" disabled={!writable} onClick={async () => {
          try { await postJSON('kanban/init', {}); await load() } catch (e) { setNotice(e.message) }
        }}>{t('kbInit')}</button>
        {notice ? <p className="error" role="alert">{notice}</p> : null}
      </section>
    )
  }

  const total = board.cards.length
  const notDone = board.cards.filter((c) => c.status !== 'Done').length
  const filtered = Object.values(filters).some(Boolean)
  const select = (k, all, values) => (
    <select className="co-input" aria-label={all} value={filters[k]} onChange={(e) => setFilters({ ...filters, [k]: e.target.value })}>
      <option value="">{all}</option>{values}
    </select>)
  return (
    <>
    <section className="view kanban">
      <div className="pipe-head">
        <div>
          <h1>{t('kbTitle')}</h1>
          <p className="lede">{fmt('kbLead', { n: total, open: notDone })}</p>
        </div>
        <button type="button" disabled={!writable} onClick={() => { setOpen(null); setAdding({ path: '', section: '' }) }}>+ {t('kbAdd')}</button>
      </div>
      {readOnly}
      <div className="kb-filters" role="group" aria-label={t('kbFilters')}>
        {select('repo', t('kbAllRepos'), board.repos.map((r) => <option key={r} value={r}>{r}</option>))}
        {select('epic', t('kbAllEpics'), board.epics.map((ep) => <option key={ep.id} value={ep.id}>{ep.id} · {ep.title}</option>))}
        {select('label', t('kbAllLabels'), board.labels.map((l) => <option key={l} value={l}>{l}</option>))}
        {select('docs', t('kbDocsAny'), [<option key="s" value="suspect">{t('kbDocsSuspect')}</option>,
          <option key="u" value="unconfirmed">{t('kbDocsUnconfirmed')}</option>])}
        {filtered ? <>
          <span className="muted small">{fmt('kbShown', { n: shown.length, total })}</span>
          <button type="button" className="ghost small" onClick={clearFilters}>{t('kbClear')}</button>
        </> : null}
        {filters.parent ? <span className="kb-chip">{fmt('kanban.parent', { id: filters.parent })}
          <button type="button" className="ghost small" aria-label={t('kanban.parentClear')} title={t('kanban.parentClear')}
                  onClick={() => { setFilters({ ...filters, parent: '' }); location.replace('#/kanban') }}>✕</button></span> : null}
      </div>
      {board.problems?.length ? <div className="aviso kb-problems" role="status"><ul>{board.problems.map((p) => (
        <li key={p.path}><code>{p.path}</code>: {p.error}</li>))}</ul></div> : null}
      {!total ? <p className="muted kb-empty">{t('kbEmpty')}</p> : null}
      {notice ? <p className="error" role="alert">{notice}</p> : null}
      {gate ? <ForceMove gate={gate} onCancel={() => setGate(null)} onForce={() => move(gate.id, gate.status, gate.anchor, true)} /> : null}
      <p id="kb-help" className="muted small">{t('kbHelp')}</p>
      <div className="kb-board">
        {drawn.map((col) => (
          <div key={col.status} className={`kb-col${over === col.status ? ' over' : ''}`} role="group" aria-label={statusLabel(col.status)}
               onDragOver={(e) => { if (writable && dragged.current) { e.preventDefault(); setOver(col.status) } }}
               onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setOver(null) }}
               onDrop={(e) => onDrop(e, cols.find((c) => c.status === col.status))}>
            <div className="col-head">{statusLabel(col.status)} <span>{col.cards.length}</span></div>
            {col.cards.map((c) => (
              <Card key={c.id} card={c} story={parentOf(c, byId)} wave={waves[c.id]} grabbed={!!(kb?.grabbed && kb.focus === c.id)} writable={writable} refFor={refFor}
                    onKey={onKey} onOpen={(id) => { setAdding(null); setOpen(id) }} onDragStart={onDragStart}
                    onDragEnd={() => { dragged.current = null; setOver(null) }} />
            ))}
          </div>
        ))}
      </div>
      <p className="sr-only" aria-live="polite" role="status">{say}</p>
    </section>
    {/* outside the animated .view: its transform would make the fixed panels scroll with it */}
    {open ? <Detail key={open} id={open} onClose={close} /> : null}
    {adding ? <AddForm key={`${adding.path}#${adding.section}`} board={board} prefill={adding} writable={writable} onClose={close}
                       onCreated={(row) => { setAdding(null); closeArg(); setSay(fmt('kbCreated', { id: row.id })); load() }} /> : null}
    </>
  )
}

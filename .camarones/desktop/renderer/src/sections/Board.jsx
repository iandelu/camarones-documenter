import { useCallback, useEffect, useMemo, useState } from 'react'
import { Aviso, Button, Chip, EmptyState, Skeleton } from '@camaron/ui'
import { columns, dropAnchor, keyMove } from '@camaron/ui/kanban.js'
import { cardAt, childrenOf, fit, gateKey, moved, parentLabel, placed, sendMove, shouldFocus } from '../board.js'
import { Failed, Page } from '../parts.jsx'
import { AddForm, StoryPanel, known, label } from './BoardPanels.jsx'
import { lang, t } from '../i18n.js'

export { AddForm, StoryPanel }

// The Board: the project's Backlog.md board in six columns, a card per work item. The app's token writes it, so a
// card moves here by mouse (drag) or keyboard (the portal's way: Space grabs, arrows move, Enter drops, Escape puts
// it back). A move shows at once and is undone if the server refuses it. A picked card opens its panel beside the
// columns (a story's lists its tasks and adds one); Add in the header opens the form for any item.
const KEYS = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', ' ', 'Enter', 'Escape']

export default function Board({ srv }) {
  const [board, setBoard] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [kb, setKb] = useState(null)
  const [say, setSay] = useState('')
  const [dragging, setDragging] = useState(null)
  const [over, setOver] = useState(null)
  const [open, setOpen] = useState(null)
  const [adding, setAdding] = useState(null)             // the form's prefill ({} for an empty one), or null when closed
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState('')
  const [item, setItem] = useState(null)                 // what GET kanban/item returned for the open card
  const [itemError, setItemError] = useState('')
  const [land, setLand] = useState(null)                 // the card just added: it takes the focus once drawn
  const load = useCallback(() => srv.get('kanban').then((b) => { setBoard(b); setError('') }, (e) => setError(e.message)), [srv])
  useEffect(() => { load() }, [load])
  useEffect(() => {                                    // the card keeps the focus when a move redraws it elsewhere
    const el = kb?.focus && document.getElementById(`bd-${kb.focus}`)
    if (shouldFocus(kb, document.activeElement, el)) el.focus()
  }, [kb, board])
  useEffect(() => {
    setItem(null); setItemError('')
    if (!open) return undefined
    let live = true
    srv.get('kanban/item', { id: open }).then((i) => live && setItem(i), (e) => live && setItemError(e.message))
    return () => { live = false }
  }, [open, srv])
  useEffect(() => {
    const el = land && document.getElementById(`bd-${land}`)
    if (el) { el.focus(); setLand(null) }
  }, [land, board])
  const cols = useMemo(() => (board ? columns(fit(board.cards, board.statuses), board.statuses) : []), [board])

  async function move(id, status, anchor) {
    const card = cols.flatMap((c) => c.cards).find((c) => c.id === id)
    if (!card || (card.status === status && !anchor.before && !anchor.after)) return
    const before = board
    setNotice('')
    setBoard({ ...board, cards: moved(fit(board.cards, board.statuses), id, status, anchor) })
    const r = await sendMove((body) => srv.post('kanban/move', body), (ids) => window.confirm(t(gateKey(ids), { ids: ids.join(', ') })),
      { id, status, ...anchor })
    if (r.kind === 'sent') setSay(t('bd.moved', { id, status: label(lang(), status) }))
    else { setBoard(before); if (r.kind === 'error') setNotice(r.message) }       // declined: back, with nothing to say
    await load()
  }
  const show = (id) => { setAdding(null); setFormError(''); setOpen(id) }
  const openForm = (prefill) => { setOpen(null); setFormError(''); setAdding(prefill) }
  const pick = (id) => { const at = cardAt(cols, id); if (at) setKb(at) }       // a click or a drag starts the keys from that card
  const openCard = (id) => { pick(id); show(id) }
  const drag = (id) => { if (id) pick(id); setDragging(id) }
  const closePanel = () => { setOpen(null); setAdding(null); setFormError('') }
  async function create(body) {
    setBusy(true); setFormError('')
    try {
      const row = await srv.post('kanban/add', body)
      await load()
      const story = adding?.parent && body.parent === adding.parent ? adding.parent : null     // opened from a story: back to it
      setAdding(null); setOpen(story); setLand(row.id); setSay(t('bd.added', { id: row.id }))
    } catch (e) { setFormError(e.message) } finally { setBusy(false) }     // the form stays, filled
  }
  async function init() {
    try { await srv.post('kanban/init', {}); setNotice(''); await load() } catch (e) { setNotice(e.message) }
  }

  function onKey(e, card) {
    if (!KEYS.includes(e.key) || e.target !== e.currentTarget) return
    e.preventDefault()
    const start = kb && kb.focus === card.id ? kb : cardAt(cols, card.id)
    if (e.key === ' ' && !start.grabbed && !board.writable) return
    const next = keyMove(start, e.key, cols)
    if (next.open) { setKb({ ...next, open: undefined }); return show(next.open) }
    if (next.drop) {
      const { id, status, ...anchor } = next.drop
      setKb({ focus: id, grabbed: false, col: next.col, row: next.row })
      return move(id, status, anchor)
    }
    if (next.grabbed && !start.grabbed) setSay(t('bd.grabbed', { id: card.id }))
    else if (next.grabbed) setSay(t('bd.over', { id: card.id, status: label(lang(), cols[next.col].status), n: next.row + 1 }))
    else if (start.grabbed && e.key === 'Escape') setSay(t('bd.cancelled', { id: card.id }))
    setKb(next)
  }

  if (error) return <Page title={t('nav.board')}><Failed title={t('bd.failed')} detail={error} onRetry={() => { setError(''); load() }} /></Page>
  if (!board) return <Page title={t('nav.board')}><Skeleton lines={6} /></Page>
  const picked = open && board.cards.find((c) => c.id === open)
  const shown = item && item.id?.toUpperCase() === open ? { ...item, status: picked?.status ?? item.status } : null
  const side = adding ? (
    <AddForm cards={board.cards} types={board.types} priorities={board.priorities} prefill={adding} busy={busy} error={formError}
      onSubmit={create} onClose={closePanel} />
  ) : open ? (
    <StoryPanel id={open} item={shown} error={itemError} tasks={childrenOf(board.cards, open)} lang={lang()} writable={!!board.writable}
      onAddTask={(story) => openForm({ type: 'task', parent: story })} onOpen={openCard} onClose={closePanel} />
  ) : null
  return (
    <Page title={t('nav.board')} wide>
      <BoardView board={board} lang={lang()} kb={kb} notice={notice} say={say} open={open} dragging={dragging} over={over} side={side}
        onMove={move} onOpen={openCard} onAdd={() => openForm({})} onKey={onKey} onInit={init} onDrag={drag} onOver={setOver} />
    </Page>
  )
}

// What the board draws, from its data alone (the test renders it): the columns as they are, with a grabbed card
// where it would land.
export function BoardView({ board, lang: l, kb, notice = '', say = '', open = null, dragging = null, over = null, side = null,
  onMove, onOpen, onAdd, onKey, onInit, onDrag, onOver }) {
  const writable = !!board.writable
  const readOnly = writable ? null : <Aviso tone="info" title={t('bd.readOnly')} />
  if (!board.enabled) {
    return (
      <>
        {readOnly}
        <EmptyState title={t('bd.off')} action={<Button variant="primary" disabled={!writable} onClick={onInit}>{t('bd.init')}</Button>}>
          {t('bd.offBody')}
        </EmptyState>
        {notice ? <Aviso tone="error" title={t('bd.failed')} detail={notice} /> : null}
      </>
    )
  }
  const byId = new Map(board.cards.map((c) => [c.id, c]))
  const cols = columns(fit(board.cards, board.statuses), board.statuses)
  const drawn = placed(cols, kb)

  // Where among the column's cards as shown the pointer is: the index dropAnchor takes.
  const dropIndex = (e) => {
    const els = [...e.currentTarget.querySelectorAll('.dk-bd-card')]
    const next = els.filter((el) => el.dataset.id !== dragging)
      .find((el) => { const r = el.getBoundingClientRect(); return e.clientY < r.top + r.height / 2 })
    return next ? els.indexOf(next) : els.length
  }
  const drop = (e, col) => {
    e.preventDefault()
    onOver(null)
    const id = dragging || e.dataTransfer.getData('text/plain')
    onDrag(null)
    if (id && writable) onMove(id, col.status, dropAnchor(col.cards, dropIndex(e), id))
  }
  return (
    <>
      {readOnly}
      <div className="row dk-bd-bar"><Button variant="primary" disabled={!writable} onClick={onAdd}>{t('bd.add')}</Button></div>
      {board.problems?.length ? <Aviso tone="warn" title={t('bd.problems')}>{board.problems.map((p) => `${p.path}: ${p.error}`).join(' · ')}</Aviso> : null}
      {notice ? <Aviso tone="error" title={t('bd.moveFailed')} detail={notice} /> : null}
      {!board.cards.length ? <p className="muted">{t('bd.empty')}</p> : null}
      <p id="bd-help" className="muted small">{t('bd.help')}</p>
      <div className={'dk-bd-wrap' + (side ? ' with-side' : '')}>
      <div className="dk-bd">
        {drawn.map((col) => (
          <section key={col.status} className={'dk-bd-col' + (over === col.status ? ' over' : '')} role="group" aria-label={label(l, col.status)}
            onDragOver={(e) => { if (writable && dragging) { e.preventDefault(); onOver(col.status) } }}
            onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) onOver(null) }}
            onDrop={(e) => drop(e, cols.find((c) => c.status === col.status))}>
            <h2 className="dk-bd-head"><span>{label(l, col.status)}</span> <span className="muted">{col.cards.length}</span></h2>
            {col.cards.map((c) => (
              <Card key={c.id} card={c} byId={byId} writable={writable} open={open === c.id} grabbed={!!(kb?.grabbed && kb.focus === c.id)}
                onKey={onKey} onOpen={onOpen} onDrag={onDrag} onOver={onOver} />))}
            {!col.cards.length ? <p className="muted small dk-bd-none">{t('col.empty')}</p> : null}
          </section>
        ))}
      </div>
      {side}
      </div>
      <p className="sr-only" aria-live="polite" role="status">{say}</p>
    </>
  )
}

function Card({ card, byId, writable, open, grabbed, onKey, onOpen, onDrag, onOver }) {
  const who = [].concat(card.assignee ?? [])[0]
  const meta = [parentLabel(card, byId), who && `@${who}`].filter(Boolean).join(' · ')
  return (
    <div id={`bd-${card.id}`} data-id={card.id} className={'dk-bd-card' + (grabbed ? ' grabbed' : '') + (open ? ' on' : '')} role="button" tabIndex={0}
      aria-grabbed={writable ? grabbed : undefined} aria-describedby="bd-help" aria-current={open ? 'true' : undefined} draggable={writable}
      onKeyDown={(e) => onKey(e, card)} onClick={() => onOpen(card.id)}
      onDragStart={(e) => { onDrag(card.id); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', card.id) }}
      onDragEnd={() => { onDrag(null); onOver(null) }}>
      <span className="dk-bd-top">
        <b className="dk-bd-id">{card.id}</b>
        {card.type ? <Chip state={card.type === 'bug' ? 'bad' : undefined}>{known(`bd.type.${card.type}`, card.type)}</Chip> : null}
        {card.priority ? <Chip>{card.priority}</Chip> : null}
      </span>
      <span className="dk-bd-title">{card.title}</span>
      {meta ? <span className="muted small">{meta}</span> : null}
    </div>
  )
}

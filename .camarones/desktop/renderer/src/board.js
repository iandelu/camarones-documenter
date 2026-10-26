// The Board's pure helpers: who a card's parent is, how a move that failed reads, how a grabbed card is drawn. The
// rows are the board API's (GET /api/kanban); a hand-edited file can leave any field out, so nothing here assumes one.

// A parent key may arrive in the rows later; until then `epic` holds the parent, whichever type it has.
export const parentOf = (card) => String(card?.parent ?? card?.epic ?? '').toUpperCase() || null

// '↳ WI-14' under a card whose parent is a story, or one the board does not show; an epic is the column's own context.
export function parentLabel(card, byId) {
  const id = parentOf(card)
  if (!id) return ''
  return byId.get(id)?.type === 'epic' ? '' : `↳ ${id}`
}

const idNum = (id) => Number(String(id).match(/(\d+)$/)?.[1] ?? Infinity)

export const childrenOf = (cards, id) => {
  const want = String(id).toUpperCase()
  return cards.filter((c) => parentOf(c) === want)
    .sort((a, b) => (a.ordinal ?? 0) - (b.ordinal ?? 0) || idNum(a.id) - idNum(b.id))
}

// Who a new item may go under (the server's table: an epic takes story/bug/spike/task, a story takes task). Done ones
// stay: a finished story can still get a late task. Archived ones are not on the board (GET kanban leaves them out, and
// the server refuses them as a parent). By id, in number order.
const PARENT_TYPES = { task: ['epic', 'story'], story: ['epic'], bug: ['epic'], spike: ['epic'] }
export const allowedParents = (type, cards) => cards.filter((c) => (PARENT_TYPES[type] || []).includes(c.type))
  .sort((a, b) => idNum(a.id) - idNum(b.id) || String(a.id).localeCompare(String(b.id)))

// What a failed move means: a 409 that names the cards blocking it asks the person (and may be forced); the rest is
// shown as the server said it (server.js keeps `status` and the response `data` on the error).
export function moveOutcome(err) {
  const blocked = err?.data?.blocked_by
  if (err?.status === 409 && Array.isArray(blocked) && blocked.length) return { kind: 'gate', blockedBy: blocked }
  return { kind: 'error', message: err?.message || String(err) }
}

// Sends a move (`post` takes the body). A gate (409 naming the blocking cards) asks `confirm(blockedBy)` once; yes sends it
// again with force. -> {kind: 'sent'} | {kind: 'declined'} (the person said no: nothing to show) | {kind: 'error', message}.
export async function sendMove(post, confirm, body) {
  try {
    await post(body)
    return { kind: 'sent' }
  } catch (e) {
    const o = moveOutcome(e)
    if (o.kind !== 'gate') return o
    if (!confirm(o.blockedBy)) return { kind: 'declined' }
  }
  try {
    await post({ ...body, force: true })
    return { kind: 'sent' }
  } catch (e) {
    return moveOutcome(e)
  }
}

// The columns as drawn: while a card is grabbed with the keyboard it shows where it would land (as the portal's).
export function placed(cols, kb) {
  if (!kb?.grabbed) return cols
  let moving = null
  const out = cols.map((c) => ({ ...c, cards: c.cards.filter((x) => (x.id === kb.focus ? ((moving = x), false) : true)) }))
  if (moving) out[kb.col].cards.splice(kb.row, 0, moving)
  return out
}

// A move shown before the server answers: the card in its column, between the neighbour it was dropped by (ordinals
// are only compared, so half a step is enough) or last of the column.
export function moved(cards, id, status, anchor = {}) {
  const at = (nid) => cards.find((c) => c.id === nid)?.ordinal ?? 0
  const last = Math.max(0, ...cards.filter((c) => c.status === status).map((c) => c.ordinal ?? 0)) + 1
  const ordinal = anchor.before ? at(anchor.before) - 0.5 : anchor.after ? at(anchor.after) + 0.5 : last
  return cards.map((c) => (c.id === id ? { ...c, status, ordinal } : c))
}

// A row whose status is missing or not one of the board's (a hand edit) would sit in no column and vanish: it is
// drawn in the first one, as it would be read, and the file is left as it is.
export const fit = (cards, statuses) => cards.map((c) => (statuses.includes(c.status) ? c : { ...c, status: statuses[0] }))

// Whether the card the keyboard state points at should take the focus now. It does when it was grabbed, when nothing has
// the focus, when it already has it, or when the focus is on another card of the board (an arrow picked it); not when
// the person is working elsewhere, in the side panel's field for one.
export function shouldFocus(kb, active, el) {
  if (!el) return false
  return !!(kb?.grabbed || !active || active.tagName === 'BODY' || active === el || active.closest?.('.dk-bd'))
}

// The keyboard state that points at a card, where `cols` (columns()) draw it; null when it is not there. A click or a drag
// start resets the keyboard to its card, so the next arrow starts from there and not from an older pick.
export function cardAt(cols, id) {
  const col = cols.findIndex((c) => c.cards.some((x) => x.id === id))
  return col < 0 ? null : { focus: id, grabbed: false, col, row: cols[col].cards.findIndex((x) => x.id === id) }
}

// Which string asks about a move that blocking cards gate: one card is told in the singular, several in the plural.
export const gateKey = (ids) => (ids.length === 1 ? 'bd.gate.one' : 'bd.gate.many')

// The gate's question. The server names each blocker as {id, kind, files?}; an older one sent bare ids. Each reads as
// its id, with why in brackets when the kind is one the app knows; an entry without an id is left out. `t` is i18n's.
const KINDS = ['dependency', 'missing', 'conflict']
export function gateMessage(blockedBy, t) {
  const named = (blockedBy || []).map((b) => (typeof b === 'string' ? { id: b } : { id: b?.id, kind: b?.kind }))
    .filter((b) => b.id && typeof b.id === 'string')
  const ids = named.map((b) => (KINDS.includes(b.kind) ? `${b.id} (${t(`bd.kind.${b.kind}`)})` : b.id)).join(', ')
  return t(gateKey(named), { ids })
}

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

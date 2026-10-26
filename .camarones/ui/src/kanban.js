// Pure helpers of the Board's Kanban over its cards (portal GET /api/kanban, desktop app): columns, where a dropped card
// lands and the keyboard move. Statuses are English in the files; only their labels change with the language.
export const STATUS_LABELS = {
  en: { Backlog: 'Backlog', Ready: 'Ready', 'In Progress': 'In Progress', 'In Review': 'In Review', Done: 'Done', Blocked: 'Blocked' },
  es: { Backlog: 'Backlog', Ready: 'Listo', 'In Progress': 'En curso', 'In Review': 'En revisión', Done: 'Hecho', Blocked: 'Bloqueado' },
}

const idNum = (id) => Number(String(id).match(/(\d+)$/)?.[1] ?? Infinity)
const byOrdinal = (a, b) => (a.ordinal ?? 0) - (b.ordinal ?? 0) || idNum(a.id) - idNum(b.id) || String(a.id).localeCompare(String(b.id))

// Every status gets its column, an empty one too, in the board's order.
export function columns(cards, statuses) {
  return statuses.map((status) => ({ status, cards: cards.filter((c) => c.status === status).sort(byOrdinal) }))
}

// Where a card dropped at `index` of a column (as shown, the moved card maybe in it) goes: next to a neighbour, or
// nothing when it lands where it already was or the column is empty.
export function dropAnchor(columnCards, index, movedId) {
  const at = columnCards.findIndex((c) => c.id === movedId)
  if (at >= 0 && (index === at || index === at + 1)) return {}
  const rest = columnCards.filter((c) => c.id !== movedId)
  const i = at >= 0 && index > at ? index - 1 : index
  if (!rest.length) return {}
  return i <= 0 ? { before: rest[0].id } : { after: rest[Math.min(i, rest.length) - 1].id }
}

const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n))

// The keyboard move over `cols` (columns()): arrows pick a card; Space grabs it; arrows then move it (its row is a
// place among the other cards of that column); Enter drops it (`drop`: what to POST) or, not grabbed, opens it
// (`open`); Escape puts it back.
export function keyMove(state, key, cols) {
  const { drop, open, ...s } = state
  const n = cols.length
  if (!s.grabbed) {
    const pick = (col, row) => {
      const list = cols[col]?.cards || []
      const r = list.length ? clamp(row, 0, list.length - 1) : 0
      return { ...s, col, row: r, focus: list[r]?.id ?? s.focus }
    }
    if (key === 'ArrowRight' || key === 'ArrowLeft') {       // the next column with a card: the focus follows the column
      const step = key === 'ArrowRight' ? 1 : -1
      let col = s.col + step
      while (col >= 0 && col < n && !cols[col].cards.length) col += step
      return col >= 0 && col < n ? pick(col, s.row) : s
    }
    if (key === 'ArrowDown') return pick(s.col, s.row + 1)
    if (key === 'ArrowUp') return pick(s.col, s.row - 1)
    if (key === ' ' && s.focus) return { ...s, grabbed: true, from: { col: s.col, row: s.row } }
    if (key === 'Enter' && s.focus) return { ...s, open: s.focus }
    return s
  }
  const others = (col) => (cols[col]?.cards || []).filter((c) => c.id !== s.focus)
  if (key === 'ArrowRight' || key === 'ArrowLeft') {
    const col = clamp(s.col + (key === 'ArrowRight' ? 1 : -1), 0, n - 1)
    return { ...s, col, row: clamp(s.row, 0, others(col).length) }
  }
  if (key === 'ArrowDown' || key === 'ArrowUp') return { ...s, row: clamp(s.row + (key === 'ArrowDown' ? 1 : -1), 0, others(s.col).length) }
  if (key === 'Escape') {
    const { from, ...rest } = s
    return { ...rest, grabbed: false, ...(from || {}) }
  }
  if (key === 'Enter' || key === ' ') {
    const { from, ...rest } = s
    const list = others(s.col)
    const anchor = !list.length ? {} : s.row === 0 ? { before: list[0].id } : { after: list[s.row - 1].id }
    return { ...rest, grabbed: false, drop: { id: s.focus, status: cols[s.col].status, ...anchor } }
  }
  return s
}

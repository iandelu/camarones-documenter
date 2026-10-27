// Pure helpers of the Board view (Kanban.jsx) over GET /api/kanban: the filters, the waves, a story's subtasks and the
// start gate's refusal. Columns, drop anchor and keyboard move live in the kit's shared kanban.js, the desktop app's
// Board uses them too.
export { STATUS_LABELS, columns, dropAnchor, keyMove } from '@camaron/ui/kanban.js'

const SUSPECT = new Set(['suspect', 'stale'])
const DOCS = {
  suspect: (c) => (c.links || []).some((l) => SUSPECT.has(l.fresh)),
  unconfirmed: (c) => (c.links || []).some((l) => l.trust !== 'confirmed'),
}
const up = (s) => String(s || '').trim().toUpperCase()

// An empty filter lets everything through; `epic` keeps the epic itself and its stories, `parent` (#/kanban?parent=)
// the parent itself and its children (a story and its subtasks).
export function applyFilters(cards, { repo, epic, label, docs, parent } = {}) {
  return cards.filter((c) => (!repo || (c.repos || []).includes(repo))
    && (!epic || up(c.epic) === up(epic) || up(c.id) === up(epic))
    && (!parent || up(c.parent) === up(parent) || up(c.id) === up(parent))
    && (!label || (c.labels || []).includes(label))
    && (!docs || !DOCS[docs] || DOCS[docs](c)))
}

// Each Backlog/Ready card's wave, 1-based as people count: from `waves` (GET /api/kanban/waves: lists of rows or ids)
// when given, else from the card's own `wave` (0-based; null or -1 when it has none). → {id: n}
export function waveOf(cards, waves) {
  const open = new Set(cards.filter((c) => c.status === 'Backlog' || c.status === 'Ready').map((c) => c.id))
  const out = {}
  if (Array.isArray(waves)) {
    waves.forEach((wave, n) => (wave || []).forEach((r) => {
      const id = typeof r === 'string' ? r : r?.id
      if (open.has(id) && !(id in out)) out[id] = n + 1
    }))
    return out
  }
  for (const c of cards) if (open.has(c.id) && Number.isInteger(c.wave) && c.wave >= 0) out[c.id] = c.wave + 1
  return out
}

// The story a card hangs from (its `↳ WI-14` mark), only when that parent is a story on the board. `byId`: {id: card}.
export function parentOf(card, byId) {
  const p = up(card?.parent)
  return p && byId[p]?.type === 'story' ? p : null
}

// The start gate's refusal as one line: "WI-20 (conflict), WI-7 (dependency)"; `label` names a kind.
export function blockedText(blocked, label = (k) => k) {
  return (blocked || []).map((b) => `${b.id} (${label(b.kind)})`).join(', ')
}

// What the Board's address asks for: `?parent=WI-14` the filter, `new?…` the add form, `WI-3` a card.
export function parseArg(arg) {
  const s = String(arg ?? '')
  if (s.startsWith('?')) {
    const parent = up(new URLSearchParams(s.slice(1)).get('parent'))
    return parent ? { parent } : {}
  }
  const add = parseNewArg(s)
  if (add) return { add }
  return s ? { open: up(s) } : {}
}

// `#/kanban/new?path=<logical>&section=<slug>`: the add form with a doc link filled in.
export function parseNewArg(arg) {
  const m = String(arg ?? '').match(/^new(?:\?(.*))?$/)
  if (!m) return null
  const q = new URLSearchParams(m[1] || '')
  return { path: q.get('path') || '', section: q.get('section') || '' }
}

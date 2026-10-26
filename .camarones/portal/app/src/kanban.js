// Pure helpers of the Board view (Kanban.jsx) over GET /api/kanban: the filters. Columns, drop anchor and keyboard move
// live in the kit's shared kanban.js, the desktop app's Board uses them too.
export { STATUS_LABELS, columns, dropAnchor, keyMove } from '@camaron/ui/kanban.js'

const SUSPECT = new Set(['suspect', 'stale'])
const DOCS = {
  suspect: (c) => (c.links || []).some((l) => SUSPECT.has(l.fresh)),
  unconfirmed: (c) => (c.links || []).some((l) => l.trust !== 'confirmed'),
}

// An empty filter lets everything through; `epic` keeps the epic itself and its stories.
export function applyFilters(cards, { repo, epic, label, docs } = {}) {
  const up = (s) => String(s || '').toUpperCase()
  return cards.filter((c) => (!repo || (c.repos || []).includes(repo))
    && (!epic || up(c.epic) === up(epic) || up(c.id) === up(epic))
    && (!label || (c.labels || []).includes(label))
    && (!docs || !DOCS[docs] || DOCS[docs](c)))
}

// `#/kanban/new?path=<logical>&section=<slug>`: the add form with a doc link filled in.
export function parseNewArg(arg) {
  const m = String(arg ?? '').match(/^new(?:\?(.*))?$/)
  if (!m) return null
  const q = new URLSearchParams(m[1] || '')
  return { path: q.get('path') || '', section: q.get('section') || '' }
}

// The Decisiones section's pure helpers: where a hash goes, how the list filters, the stepper, the presentation keys,
// why accept is refused. The rows and the ADR are the app API's (lib/adr.py `rows` and `get`); a hand-edited file can
// leave any field out, so nothing here assumes one.

// Inside the section: the list, the new-decision form, the candidates, or one ADR (the server's four-digit number).
export function route(hash) {
  const seg = String(hash ?? '').split('?')[0].replace(/\/+$/, '').match(/^#\/decisions\/([^/]+)$/)?.[1]
  if (seg === 'new' || seg === 'candidates') return { view: seg }
  return /^\d{4}$/.test(seg ?? '') ? { view: 'adr', id: seg } : { view: 'list' }
}

// The header's last breadcrumb (App.jsx) for a place inside the section; the list has none, the section's own is last.
export function crumb(hash, t) {
  const r = route(hash)
  return r.view === 'new' ? t('adr.new') : r.view === 'candidates' ? t('adr.cand.title') : r.view === 'adr' ? `ADR ${r.id}` : null
}

export const FILTERS = ['all', 'running', 'review', 'accepted', 'superseded']

const norm = (s) => String(s ?? '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()

export function counts(rows) {
  const list = rows || []
  return Object.fromEntries(FILTERS.map((f) => [f, f === 'all' ? list.length : list.filter((r) => r.chip === f).length]))
}

// The rows of one filter whose title, number or repos hold every word of the query, accents and case aside.
export function filterRows(rows, filter, q) {
  const words = norm(q).split(/\s+/).filter(Boolean)
  return (rows || []).filter((r) => {
    if (filter !== 'all' && r.chip !== filter) return false
    const text = norm(`${r.title} ${r.id} ${(r.repos || []).join(' ')}`)
    return words.every((w) => text.includes(w))
  })
}

export const STEPS = ['problem', 'evidence', 'research', 'synthesis', 'review', 'accepted']
const MANUAL_SKIPS = ['research', 'synthesis']

// A rejected ADR ends on a `rejected` step in the place of `accepted`; a phase it does not know leaves every step to do.
export function stepper(phase, mode) {
  const rejected = phase === 'rejected'
  const at = STEPS.indexOf(rejected ? 'accepted' : phase)
  return STEPS.map((step, i) => ({
    id: rejected && i === at ? 'rejected' : step,
    state: mode === 'manual' && MANUAL_SKIPS.includes(step) ? 'skipped' : i < at ? 'done' : i === at ? 'current' : 'todo' }))
}

// The part before or after `current` (an id; `parts` are the API's {id, status}), clamped at both ends. A part that is
// not in the list moves to the first.
export function nextPart(parts, current, dir) {
  const ids = (parts || []).map((p) => p?.id ?? p)
  if (!ids.length) return current
  const at = ids.indexOf(current)
  return ids[at < 0 ? 0 : Math.min(ids.length - 1, Math.max(0, at + dir))]
}

const KEYS = { ArrowRight: 'next', ArrowLeft: 'prev', e: 'edit', d: 'defer', a: 'accept', Escape: 'exit', p: 'toggle' }

// What a key does in the presentation. Text typed into a field is text: nothing here fires then. A number picks the
// option it names, if the point has it; modifiers are the view's to filter.
export function presentKey(key, ctx) {
  if (ctx?.typing) return null
  if (/^[1-9]$/.test(key)) return Number(key) <= (ctx?.options ?? 0) ? { do: 'choose', n: Number(key) } : null
  return Object.hasOwn(KEYS, key) ? { do: KEYS[key] } : null
}

const PLACEHOLDER = 'To be decided in review: see the decision points.'

// The first reason accept is refused, in the server's own order (lib/adr.py `_outcome`): the string key and the point
// it names, null when nothing is in the way.
export function acceptBlock(adr) {
  for (const p of adr?.points || []) {
    const point = String(p.id).toUpperCase()
    if (p.deferred) return { key: 'adr.why.deferred', point }
    if (!(p.chosen || p.other)) return { key: 'adr.why.unchosen', point }
  }
  if (adr?.points?.length) return null
  const written = String(adr?.sections?.decision ?? '').trim()
  return !written || written === PLACEHOLDER ? { key: 'adr.why.noDecision' } : null
}

// A search hit added to the files an ADR touches: a group brings its files, a file or a page itself; sorted, once each.
export function addHit(touches, hit) {
  const added = hit?.kind === 'group' ? hit.files : [hit?.touch]
  return [...new Set([...(touches || []), ...(added || [])].filter((x) => typeof x === 'string' && x))].sort()
}

// Which screen an ADR opens on: no working state (legacy) → read-only; framed or with its evidence → the evidence step;
// in review or decided → the review.
export function viewOf(adr) {
  const phase = adr?.state?.phase
  return !adr?.state ? 'legacy' : phase === 'problem' || phase === 'evidence' ? 'evidence' : 'review'
}

// One ADR's screen as state (Decisions.jsx AdrScreen): React keys it by the ADR, so another one starts afresh from
// here. `pack` is undefined until read and null when none was gathered; `notice` is a string key and its vars.
export const startScreen = (notice) => ({ adr: null, error: '', reads: 0, pack: undefined, packError: '', packing: false, busy: false,
  actError: '', notice: notice ?? null })

export function screen(s, a) {
  switch (a.type) {
    case 'read': return { ...s, adr: a.adr, error: '' }
    case 'readFailed': return { ...s, error: a.error, busy: false, packing: false }
    case 'retry': return { ...s, error: '', reads: s.reads + 1 }
    case 'pack': return { ...s, pack: a.pack ?? null }
    case 'packing': return { ...s, packing: true, packError: '' }
    case 'packed': return { ...s, packing: false, pack: a.pack, adr: a.adr ?? s.adr }
    case 'packFailed': return { ...s, packing: false, packError: a.error, pack: s.pack === undefined ? null : s.pack }
    case 'busy': return { ...s, busy: true, actError: '' }
    case 'done': return { ...s, busy: false, adr: a.adr }
    case 'actFailed': return { ...s, busy: false, actError: a.error }
    case 'reloaded': return { ...s, busy: false, packing: false, adr: a.adr, notice: { key: 'adr.reloaded' } }
    default: return s
  }
}

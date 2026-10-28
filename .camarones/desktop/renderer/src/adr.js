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
const TODO = 'TODO(question)'
const POINTS_HEADING = '### Decision points'
const bare = (text) => String(text ?? '').replace(/<!--[\s\S]*?-->/g, '')

// A section holding nothing a person wrote (lib/adr_doc.py `unwritten`): once comments are set aside, empty or only
// placeholders: TODO(question) lines, the kit's Decision placeholder, a 4.x skeleton's `<…>` lines (`<What was chosen.>`).
export const unwritten = (text) => bare(text).split(/\r?\n/).map((l) => l.trim()).filter(Boolean)
  .every((l) => l.startsWith(TODO) || l === PLACEHOLDER || /^<[^<>]+>$/.test(l))

// The first reason accept is refused, in the server's own order (lib/adr.py `_outcome`): the string key and the point
// it names, null when nothing is in the way.
export function acceptBlock(adr) {
  for (const p of adr?.points || []) {
    const point = String(p.id).toUpperCase()
    if (p.deferred) return { key: 'adr.why.deferred', point }
    if (!(p.chosen || p.other)) return { key: 'adr.why.unchosen', point }
  }
  if (adr?.points?.length) return null
  return unwritten(adr?.sections?.decision) ? { key: 'adr.why.noDecision' } : null
}

const ASKED = ['context', 'drivers', 'options', 'decision', 'consequences', 'confirmation', 'diagram', 'evidence']

// The sections that will still ask a TODO(question) once the ADR is accepted, in reading order: a warning in the accept
// dialog, never a block. With decision points, accepting fills a Considered options that holds nothing written and puts
// their paragraphs in place of an unwritten Decision (lib/adr.py `_considered`, `_outcome`), so those are left out.
export function todoSections(adr) {
  const points = (adr?.points?.length ?? 0) > 0
  return ASKED.filter((key) => {
    const text = bare(key === 'decision' ? String(adr?.sections?.decision ?? '').split(POINTS_HEADING)[0] : adr?.sections?.[key])
    return text.includes(TODO) && !(points && ['options', 'decision'].includes(key) && unwritten(text))
  })
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
    case 'done': return { ...s, busy: false, adr: a.adr, notice: null }
    case 'actFailed': return { ...s, busy: false, actError: a.error }
    case 'dialog': return { ...s, actError: '' }          // a dialog opens: a refusal from before it is not its own
    case 'reloaded': return { ...s, busy: false, packing: false, adr: a.adr, notice: { key: 'adr.reloaded' } }
    default: return s
  }
}

// ---------- the review (sections/adr/Review.jsx) ----------

// A part is a section of text (approved, edited or deferred), a decision point, or the docs the ADR covers once accepted
// (computed: they are seen and approved, never edited).
export const partKind = (id) => (String(id ?? '').startsWith('point:') ? 'point' : id === 'affected' ? 'affected' : 'text')
export const decided = (adr) => ['accepted', 'rejected'].includes(adr?.state?.phase)
export const pointOf = (adr, part) => (adr?.points || []).find((p) => `point:${p.id}` === part) ?? null

// The parts the review walks (lib/adr.py parts_of). With no decision point, accepting needs the Decision section written
// (acceptBlock), so it is a part too, after the drivers, with the status the working state keeps for it.
export function reviewParts(adr) {
  const parts = (adr?.parts || []).filter((p) => p?.id)
  if (adr?.points?.length || parts.some((p) => p.id === 'decision')) return parts
  const ids = parts.map((p) => p.id)
  const at = Math.max(ids.indexOf('drivers'), ids.indexOf('context')) + 1
  return [...parts.slice(0, at), { id: 'decision', status: adr?.state?.parts?.decision || 'pending' }, ...parts.slice(at)]
}

const SEEN = ['approved', 'edited']

// Where a review opens: the first part still to see (pending or deferred), else the first.
export const firstOpen = (parts) => ((parts || []).find((p) => !SEEN.includes(p.status)) ?? parts?.[0])?.id ?? null

// The part a refused accept points at (acceptBlock): the point it names, or the Decision section; null if not shown.
export function blockedPart(block, parts) {
  if (!block) return null
  const id = block.point ? `point:${String(block.point).toLowerCase()}` : 'decision'
  return (parts || []).some((p) => (p?.id ?? p) === id) ? id : null
}

// A keydown on the review as presentKey's action. Not with a modifier held (the app's ⌘K, the system's own), not while
// typing, not for the letter that ends a `g` chord (App.jsx goes to a section then: `g d` must not defer). A capital
// (Shift, Caps Lock) is its letter.
export function reviewKey(e, ctx) {
  if (!e?.key || e.metaKey || e.ctrlKey || e.altKey || ctx?.chord) return null
  return presentKey(/^[A-Z]$/.test(e.key) ? e.key.toLowerCase() : e.key, ctx)
}

// What an action does on the part in view: {go}, {present}, {pick: option id}, {edit: 'text' | 'rationale'},
// {defer: 'part' | 'point'}, {accept: true} (confirm first), or, when accept is refused, {go, blocked} to the part in
// the way. A decided ADR only moves and presents; null when the action has nothing to do here.
// ctx.adding (the add-point form is in view) and ctx.editing (the part's text is being written): Esc closes that first,
// as it does a dialog, and P still presents. With the form open no key reaches the part behind it; while editing none
// defers, chooses or accepts, which would act on or drop the text unsaved. Moving keeps it: drafts are kept by part.
export function keyEffect(adr, current, act, ctx) {
  if (!act) return null
  const present = !!ctx?.present
  if (act.do === 'toggle') return { present: !present }
  if (act.do === 'exit') return ctx?.adding ? { close: 'adding' } : ctx?.editing ? { close: 'editing' } : present ? { present: false } : null
  if (ctx?.adding) return null
  if (act.do === 'next' || act.do === 'prev') return { go: nextPart(reviewParts(adr), current, act.do === 'next' ? 1 : -1) }
  if (decided(adr)) return null
  if (ctx?.editing) return act.do === 'edit' ? { edit: 'text' } : null
  const kind = partKind(current)
  if (act.do === 'choose') {
    const option = kind === 'point' ? pointOf(adr, current)?.options?.[act.n - 1] : null
    return option ? { pick: option.id } : null
  }
  if (act.do === 'edit') return kind === 'affected' ? null : { edit: kind === 'point' ? 'rationale' : 'text' }
  if (act.do === 'defer') return kind === 'affected' ? null : { defer: kind === 'point' ? 'point' : 'part' }
  if (act.do === 'accept') {
    const block = acceptBlock(adr)
    return block ? { go: blockedPart(block, reviewParts(adr)) ?? current, blocked: block } : { accept: true }
  }
  return null
}

// A refusal the file outran (409 with the sha it has now): read the ADR again. A 409 without it is the ADR's lock being
// busy, a message to show as it is, like any other refusal.
export const stale = (e) => e?.status === 409 && !!e?.data?.sha

const line = (s) => String(s ?? '').replace(/\s+/g, ' ').trim()
const lines = (s) => String(s ?? '').split(/\r?\n/).map(line).filter(Boolean)

// The option a point has picked on screen (a draft), else the one it was decided with; 'other' is one typed in.
export const pickOf = (point, draft) => draft?.picked ?? (point?.other ? 'other' : point?.chosen) ?? null

// The body that decides a point (`point choose`): the option picked, or the one typed, and its one-line why; null while
// there is nothing to choose.
export function choiceBody(point, draft) {
  const picked = pickOf(point, draft)
  const base = { op: 'choose', point: point?.id, rationale: line(draft?.rationale ?? point?.rationale) }
  if (picked === 'other') {
    const other = line(draft?.other ?? point?.other)
    return other ? { ...base, other } : null
  }
  return (point?.options || []).some((o) => o.id === picked) ? { ...base, chosen: picked } : null
}

// The body of a new point (`point add`) from its form: the question and every named option, pros and cons one per
// line; null until it has a question and two options.
export function newPointBody(form) {
  const question = line(form?.question)
  const options = (form?.options || []).map((o) => ({ name: line(o?.name), pros: lines(o?.pros), cons: lines(o?.cons) }))
    .filter((o) => o.name)
  return question && options.length >= 2 ? { op: 'add', question, options } : null
}

// The attendees with the ones typed added (several at once, split by commas); a name already there, whatever its case,
// is not added twice.
export function addAttendees(list, typed) {
  const out = [...(list || [])]
  for (const name of String(typed ?? '').split(',').map(line).filter(Boolean))
    if (!out.some((n) => n.toLowerCase() === name.toLowerCase())) out.push(name)
  return out
}

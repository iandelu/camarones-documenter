// Pure helpers of the Historias view (no React): the instant hints (a port of lib/stories.py `lint`, same codes in the
// same order, checked against tests/fixtures/story_lint_cases.json), the wizard's draft and its steps, and the draft
// kept in localStorage. The word lists come from GET /api/stories → lint_words (the kit's story-lint.yaml files).

const TOO_LONG = 280                  // characters of the three clauses together (stories.py TOO_LONG)
const REPEAT_SHARE = 0.6              // share of the "so" content words already in the "want" (stories.py REPEAT_SHARE)
const CONTENT_MIN = 4                 // letters a word needs to count as a content word (stories.py CONTENT_MIN)
const ARTICLES = { es: ['el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas'], en: ['a', 'an', 'the'] }
const INFINITIVE = /(?:ar|er|ir)(?:se|me|te|lo|la|los|las|le|les|nos)?$/
// Python's [^\W\d_]+ (letters, plus the numeric symbols str.isalnum accepts) joined by one ' ’ or - inside a word.
const LETTER = '[\\p{L}\\p{No}\\p{Nl}]'
const WORD = new RegExp(`${LETTER}+(?:['’-]${LETTER}+)*`, 'gu')

const size = (s) => [...s].length                                   // characters, as Python's len, not UTF-16 units
const clean = (s) => String(s ?? '').split(/\s+/).filter(Boolean).join(' ')
const tokens = (s) => String(s ?? '').toLowerCase().match(WORD) || []
const list = (words, key) => new Set((words && words[key]) || [])

const content = (text, stop) => tokens(text).filter((w) => size(w) >= CONTENT_MIN && !stop.has(w))

function genericRole(as, lang, words) {
  let toks = tokens(as)
  while (toks.length > 1 && ARTICLES[lang].includes(toks[0])) toks = toks.slice(1)
  return list(words, 'generic_roles').has(toks.join(' '))
}

function twoGoals(want, lang, words) {
  const toks = tokens(want)
  const conj = list(words, 'conjunctions')
  const at = toks.flatMap((w, i) => (conj.has(w) && i > 0 && i < toks.length - 1 ? [i] : []))
  if (lang === 'es') {
    const short = list(words, 'short_verbs')
    const nouns = list(words, 'not_verbs')
    const verb = (w) => short.has(w) || (!nouns.has(w) && size(w) >= 4 && INFINITIVE.test(w))
    return at.some((i) => toks.slice(i + 1, i + 3).some(verb))
  }
  const skip = new Set([...list(words, 'stopwords'), ...list(words, 'function_words')])
  const verbs = list(words, 'verbs')
  return at.some((i) => !skip.has(toks[i + 1])) && toks.filter((w) => verbs.has(w)).length >= 2
}

function repeats(want, so, words) {
  const stop = list(words, 'stopwords')
  const mine = content(so, stop)
  if (!mine.length) return false
  const theirs = new Set(content(want, stop))
  return mine.filter((w) => theirs.has(w)).length / mine.length > REPEAT_SHARE
}

function hasSolution(want, words) {
  const padded = ` ${tokens(want).join(' ')} `
  return [...list(words, 'solution_words')].some((w) => padded.includes(` ${tokens(w).join(' ')} `))
}

// The hints for the three clauses, in the Python order: empty, generic-role, two-goals, so-repeats-want, too-long,
// solution-in-want, no-footprint. Each code appears at most once; checks over a blank clause are skipped.
// → [{ code, field }]; the text of a hint is the i18n key stories.hint.<code>.
export function lint(as, want, so, lang, words, touches = []) {
  lang = lang === 'es' ? 'es' : 'en'
  as = clean(as); want = clean(want); so = clean(so)
  const found = []
  const blank = [['as', as], ['want', want], ['so', so]].filter(([, v]) => !v).map(([k]) => k)
  if (blank.length) found.push(['empty', blank[0]])
  if (as && genericRole(as, lang, words)) found.push(['generic-role', 'as'])
  if (want && twoGoals(want, lang, words)) found.push(['two-goals', 'want'])
  if (want && so && repeats(want, so, words)) found.push(['so-repeats-want', 'so'])
  if (size(as) + size(want) + size(so) > TOO_LONG) found.push(['too-long', 'story'])
  if (want && hasSolution(want, words)) found.push(['solution-in-want', 'want'])
  if (!(touches || []).some(Boolean)) found.push(['no-footprint', 'touches'])
  return found.map(([code, field]) => ({ code, field }))
}

// ── the draft ─────────────────────────────────────────────────────────────────────────────────────────────────────

// A new story, or the draft of an existing one from GET /api/stories/item. `tasks` stays null until the person has
// seen the proposals; `sha` is what `save` gets back as base_sha to notice a story changed meanwhile, and `baseTitle`
// / `baseTouches` (the title and footprint as loaded; null for a new story) let save keep what someone else changed.
export function initialDraft(item) {
  const it = item || {}
  return { id: it.id || null, sha: it.sha || null, as: it.as_ || '', want: it.want || '', so: it.so || '', title: it.title || '',
    epic: it.epic || '', criteria: [...(it.criteria || [])], touches: [...(it.touches || [])], tasks: null, step: 1,
    baseTitle: it.id ? it.title || '' : null, baseTouches: it.id ? [...(it.touches || [])] : null }
}

// The step the wizard's Next leads to: 1 while the story lacks one of its three parts; otherwise one on from the
// current step (3 is the last), held where it is while the tasks wait on each other in a cycle or share a key.
export function nextStep(draft, analysis) {
  if (!analysis || (analysis.hints || []).some((h) => h.code === 'empty')) return 1
  const at = Math.min(3, Math.max(1, draft.step || 1))
  if (at === 2 && ((analysis.cycle || []).length || (analysis.duplicates || []).length)) return 2
  return Math.min(3, at + 1)
}

// The story text as the analysis compares it (stories.py `fingerprint` without the hash): lower case, spaces collapsed,
// each clause trimmed, joined by a line break.
const normal = (t) => [t.as, t.want, t.so].map((p) => clean(p).toLowerCase()).join('\n')

// Has the text changed since the analysis ran? `analysed` is the {as, want, so} that was sent; none yet counts as stale.
export function outdated(draft, analysed) {
  return !analysed || normal(draft) !== normal(analysed)
}

// The Save button: the story and how many of its tasks are ticked (a task is ticked unless `checked` is false).
export function primaryLabel(draft, t) {
  const n = (draft.tasks || []).filter((task) => task.checked !== false).length
  return draft.id ? t('stories.save.existing', { id: draft.id, n }) : t('stories.save.new', { n })
}

// ── the draft in this browser ─────────────────────────────────────────────────────────────────────────────────────

export const draftKey = (id) => `cam-story-draft:${id || 'new'}`

export function loadDraft(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key))
    return value && typeof value === 'object' && !Array.isArray(value) ? value : null
  } catch { return null }
}

export function saveDraft(key, draft) {
  try { localStorage.setItem(key, JSON.stringify(draft)); return true } catch { return false }
}

export function dropDraft(key) {
  try { localStorage.removeItem(key); return true } catch { return false }
}

// ── the AI's suggestions in this browser ──────────────────────────────────────────────────────────────────────────

// What the AI proposed for a story waits here until it is accepted or dismissed: asking for another kind, opening
// another story, leaving Historias or reloading loses none of it. Dismissed texts stay too, so they never come back.
export const suggestKey = (id) => `cam-story-ai:${id || 'new'}`
export const noSuggestions = () => ({ rewrite: null, criteria: [], tasks: [], gone: {} })
const same = (x) => clean(x?.title ?? x).toLowerCase()
const isText = (x) => typeof x === 'string' && !!x.trim()

export function loadSuggestions(key) {
  const v = loadDraft(key)
  if (!v) return noSuggestions()
  const list = (xs) => (Array.isArray(xs) ? xs : [])
  const gone = v.gone && typeof v.gone === 'object' && !Array.isArray(v.gone) ? v.gone : {}
  return {
    rewrite: v.rewrite && typeof v.rewrite === 'object' && !Array.isArray(v.rewrite) ? v.rewrite : null,
    criteria: list(v.criteria).filter(isText),
    tasks: list(v.tasks).filter((x) => isText(x?.title)).map((x) => ({ ...x, touches: list(x.touches) })),
    gone: Object.fromEntries(Object.entries(gone).map(([k, xs]) => [k, list(xs).filter(isText)])),
  }
}
export const saveSuggestions = saveDraft
export const dropSuggestions = dropDraft

// An answer joins what is kept: a list grows by what is new to it and was never dismissed; a rewrite replaces the last.
export function keepSuggestions(kept, what, res) {
  if (what === 'rewrite') return res?.rewrite ? { ...kept, rewrite: res.rewrite } : kept
  const seen = new Set([...kept[what], ...(kept.gone[what] || [])].map(same))
  const fresh = (res?.[what] || []).filter((x) => { const k = same(x); return k && !seen.has(k) && seen.add(k) })
  return { ...kept, [what]: [...kept[what], ...fresh] }
}

// Accepted or dismissed: off the list, and remembered so the AI is not asked for it again.
export function dismissSuggestion(kept, what, text) {
  const gone = { ...kept.gone, [what]: [...(kept.gone[what] || []), text] }
  if (what === 'rewrite') return { ...kept, rewrite: null, gone }
  return { ...kept, [what]: kept[what].filter((x) => same(x) !== same(text)), gone }
}

// What the AI must not propose: what the story has, what it proposed already and what the person dismissed.
export function suggestExclude(draft, kept, what) {
  const have = what === 'criteria' ? draft.criteria : what === 'tasks' ? (draft.tasks || []).map((x) => x.title) : []
  const shown = what === 'rewrite' ? [] : kept[what].map((x) => x.title ?? x)
  return [...have, ...shown, ...(kept.gone[what] || [])].filter(isText)
}

// ── the wizard's edits (Stories.jsx) ──────────────────────────────────────────────────────────────────────────────

const TITLE_MAX = 80                  // a new story's title (stories.py TITLE_MAX)
const DOCS_REPO = 'cam-docs'
const uniq = (xs) => [...new Set((xs || []).filter(Boolean))]
const sorted = (xs) => uniq(xs).sort()
const repoOf = (touch) => String(touch).split(':')[0]
const without = (xs, gone) => (xs || []).filter((x) => !gone.includes(x))

// A new story's title from its want (stories.py `title_for`): one line, cut at 80 characters on a word boundary,
// without trailing punctuation, first letter upper-cased.
export function titleFrom(want) {
  let text = clean(want)
  const chars = [...text]
  if (chars.length > TITLE_MAX) {
    const cut = chars.slice(0, TITLE_MAX).join('')
    text = chars[TITLE_MAX] !== ' ' && cut.includes(' ') ? cut.slice(0, cut.lastIndexOf(' ')) : cut
  }
  text = text.replace(/[ .,;:]+$/, '')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

// Toca: a picked search hit (GET /api/stories/files). A file or a page adds itself; a group adds its files, never the
// group's own touch (save refuses it). → the touches, sorted, once each.
export function pickHit(touches, hit) {
  const more = hit.kind === 'group' ? hit.files || [] : [hit.touch]
  return sorted([...(touches || []), ...more])
}

// Toca's "Añadir «…» (nuevo)": the query as the touch of a file a task will create, when it reads `repo:path` for one
// of `repos` and the search had no exact hit (nor is it picked already). Save checks that its folder exists. The path
// is cleaned as the kit cleans a touch (`/` separators, no `./`, no empty segment); a folder, an absolute path or a
// `..` is never offered. → the touch, or null.
export function newTouch(q, repos, hits, touches) {
  const m = String(q ?? '').trim().match(/^([^:\s]+):(.+)$/)
  if (!m || !(repos || []).includes(m[1])) return null
  const raw = m[2].trim().replace(/\\/g, '/')
  if (!raw || raw.startsWith('/') || raw.endsWith('/') || raw.includes(':')) return null
  const parts = raw.split('/').filter((p) => p && p !== '.')
  if (!parts.length || parts.includes('..')) return null
  const touch = `${m[1]}:${parts.join('/')}`
  if ((hits || []).some((h) => h.touch === touch) || (touches || []).includes(touch)) return null
  return touch
}

// The chips of Toca, one row per group: the code-map group a search hit or a task named (`groups`: {touch: group}),
// else the repo and folder; doc pages under "docs". Rows and chips sorted.
export function chipGroups(touches, groups = {}) {
  const rows = {}
  for (const touch of sorted(touches)) {
    const [repo, ...rest] = touch.split(':')
    const path = rest.join(':')
    const group = groups[touch] || (repo === DOCS_REPO ? 'docs' : [repo, ...path.split('/').slice(0, -1)].join('/'))
    ;(rows[group] ||= []).push(touch)
  }
  return Object.keys(rows).sort().map((group) => ({ group, touches: rows[group] }))
}

// The footprint line: "3 grupos · 9 archivos · 1 repo · 2 páginas" (pages are counted apart, as INVEST's S does).
export function footprintOf(touches, groups = {}) {
  const all = sorted(touches)
  const code = all.filter((t) => repoOf(t) !== DOCS_REPO)
  return { groups: chipGroups(code, groups).length, files: code.length, repos: new Set(code.map(repoOf)).size,
    pages: all.length - code.length }
}

// The tasks analyze returned, with the ticks the person left on the same keys (new ones come ticked), followed by the
// unticked ones, which were not sent (they have no wave and wait for nothing until they are ticked again).
export function withChecks(tasks, previous) {
  const was = Object.fromEntries((previous || []).map((t) => [t.key, t.checked !== false]))
  const fresh = (tasks || []).map((t) => ({ ...t, checked: was[t.key] ?? true }))
  const back = new Set(fresh.map((t) => t.key))
  const off = (previous || []).filter((t) => t.checked === false && !back.has(t.key))
    .map((t) => ({ ...t, wave: -1, deps: [], conflicts: [] }))
  return [...fresh, ...off]
}

// Any change to a task marks it edited: analyze then keeps it as given instead of proposing it afresh.
export function editTask(tasks, key, patch) {
  return (tasks || []).map((t) => (t.key === key ? { ...t, ...patch, edited: true } : t))
}

// ✕ on a "depende de" chip: an added dependency is taken back, a derived one is dropped.
export function dropDep(tasks, key, dep) {
  const t = (tasks || []).find((x) => x.key === key)
  if (!t) return tasks
  const mine = (t.added || []).includes(dep)
  return editTask(tasks, key, { added: without(t.added, [dep]),
    dropped: mine ? t.dropped || [] : uniq([...(t.dropped || []), dep]), deps: without(t.deps, [dep]) })
}

// "+" on a task: a dependency on another task (its key) or a board item (its id); a dropped one is restored.
export function addDep(tasks, key, dep) {
  const t = (tasks || []).find((x) => x.key === key)
  if (!t || !dep || dep === key || (t.deps || []).includes(dep)) return tasks
  const back = (t.dropped || []).includes(dep)
  return editTask(tasks, key, { dropped: without(t.dropped, [dep]),
    added: back ? t.added || [] : uniq([...(t.added || []), dep]), deps: uniq([...(t.deps || []), dep]) })
}

// ✕ on a task: out of the list, its key in `removed` (analyze does not propose it again), and out of the others'
// added dependencies.
export function removeTask(draft, key) {
  const tasks = (draft.tasks || []).filter((t) => t.key !== key)
    .map((t) => ((t.added || []).includes(key) || (t.deps || []).includes(key)
      ? { ...t, added: without(t.added, [key]), deps: without(t.deps, [key]) } : t))
  return { ...draft, tasks, removed: uniq([...(draft.removed || []), key]) }
}

// "Añadir subtarea": a task of the person's own, key `added:<n>`. Without files it counts as the whole repo for agents.
export function addTask(tasks, title, touches = []) {
  const n = Math.max(0, ...(tasks || []).map((t) => Number((t.key.match(/^added:(\d+)$/) || [])[1]) || 0)) + 1
  return [...(tasks || []), { key: `added:${n}`, kind: 'change', title: clean(title), group: '', touches: sorted(touches),
    criteria: [], deps: [], conflicts: [], wave: -1, edited: true, added: [], dropped: [], checked: true }]
}

// "Fusionar": `b` folds into `a` (files, criteria and the person's dependencies of both); `b` goes to `removed`, and
// whoever waited for `b` now waits for `a`.
export function mergeTasks(draft, a, b) {
  const tasks = draft.tasks || []
  const ta = tasks.find((t) => t.key === a)
  const tb = tasks.find((t) => t.key === b)
  if (!ta || !tb || a === b) return draft
  const both = [a, b]
  const merged = { ...ta, edited: true, touches: sorted([...ta.touches, ...tb.touches]),
    criteria: uniq([...ta.criteria, ...tb.criteria]),
    added: without(uniq([...(ta.added || []), ...(tb.added || [])]), both),
    dropped: without(uniq([...(ta.dropped || []), ...(tb.dropped || [])]), both),
    deps: without(uniq([...(ta.deps || []), ...(tb.deps || [])]), both) }
  const swap = (xs) => uniq((xs || []).map((x) => (x === b ? a : x)))
  const out = tasks.filter((t) => t.key !== b).map((t) => {
    if (t.key === a) return merged
    if (!(t.added || []).includes(b) && !(t.deps || []).includes(b)) return t
    return { ...t, edited: true, added: swap(t.added), deps: swap(t.deps) }
  })
  return { ...draft, tasks: out, removed: uniq([...(draft.removed || []), b]) }
}

const storyOf = (d) => ({ id: d.id || null, as: d.as, want: d.want, so: d.so,
  criteria: (d.criteria || []).map(clean).filter(Boolean), touches: sorted(d.touches), epic: d.epic || null })
const taskOf = (t) => ({ key: t.key, kind: t.kind || 'change', title: t.title, group: t.group || '', touches: t.touches || [],
  criteria: t.criteria || [], edited: !!t.edited, added: t.added || [], dropped: t.dropped || [] })

// POST /api/stories/analyze: the story, the ticked tasks (unedited ones come back fresh) and `removed` with the keys of
// the unticked ones, so they are neither proposed again nor counted in the waves.
export function analyzeBody(draft, lang) {
  const tasks = draft.tasks || []
  const off = tasks.filter((t) => t.checked === false).map((t) => t.key)
  return { story: storyOf(draft), tasks: tasks.filter((t) => t.checked !== false).map(taskOf),
    removed: uniq([...(draft.removed || []), ...off]), lang }
}

// What the analyze effect does with the draft as it is now. `key` is the body to send, prefixed with a nonce that
// changes each time a story is opened; `last` the key whose answer is on screen. A blank want clears the analysis
// and forgets `last`, so typing the same text back runs it again; a change undone before its answer (A → B → A) is
// a skip, and nothing is pending any more. → {action: 'run' | 'skip' | 'clear', last, pending}
export function planAnalyze(last, key, want) {
  if (!clean(want)) return { action: 'clear', last: '', pending: false }
  return key === last ? { action: 'skip', last, pending: false } : { action: 'run', last, pending: true }
}

// The files the story's linked doc pages cite (GET /api/stories/item → doc_sources) start Toca when it opens with no
// footprint (a new story, or a saved one without files), marked `fromDocs` until the person removes or keeps them. A
// saved footprint is the person's choice: files removed from it do not come back.
export function mergeDocSources(draft, sources) {
  const more = sorted(sources)
  if ((draft.touches || []).length || !more.length) return draft
  return { ...draft, touches: more, fromDocs: more }
}

// The AI button is shown wherever AI helps; it runs only when the server has a runner, its switch is on and this page
// holds the token. → {on, why: the i18n key saying why not, runner}. The switch comes first: a token would not help.
export function aiGate(meta) {
  const ai = meta?.ai || {}
  const runner = ai.runner || null
  if (ai.reason === 'off') return { on: false, why: 'stories.ai.why.off', runner }
  if (!ai.available) return { on: false, why: 'stories.ai.why.runner', runner }
  if (!meta.writable) return { on: false, why: 'stories.ai.why.token', runner }
  return { on: true, why: null, runner }
}

// Escape while an AI suggestion is on its way stops that request and nothing else: the key goes no further, so the
// form or search box under the focus keeps its state. → whether it was taken.
export function escapeAborts(e, running, stop) {
  if (e.key !== 'Escape' || !running) return false
  e.stopPropagation(); e.preventDefault(); stop()
  return true
}

// POST /api/stories/save: the ticked tasks only, each with the dependencies analyze worked out (keys of ticked tasks or
// board ids); the title; base_sha to notice a change made meanwhile; for an existing story base_title and
// base_touches, so a title or footprint the person left alone is not written over someone else's change.
export function saveBody(draft) {
  const tasks = (draft.tasks || []).filter((t) => t.checked !== false)
  const keys = new Set((draft.tasks || []).map((t) => t.key))
  const kept = new Set(tasks.map((t) => t.key))
  const existing = !!draft.id
  return { story: storyOf(draft), title: clean(draft.title) || null, base_sha: draft.sha || null,
    base_title: existing && typeof draft.baseTitle === 'string' ? draft.baseTitle : null,
    base_touches: existing && Array.isArray(draft.baseTouches) ? sorted(draft.baseTouches) : null,
    tasks: tasks.map((t) => ({ key: t.key, title: clean(t.title), touches: t.touches || [], criteria: t.criteria || [],
      deps: (t.deps || []).filter((d) => !keys.has(d) || kept.has(d)) })) }
}

// Task keys as people read them: the task's title («…» around it), else the key itself (a board id stays an id).
export function taskNames(keys, tasks) {
  const title = Object.fromEntries((tasks || []).map((t) => [t.key, clean(t.title)]))
  return (keys || []).map((k) => (title[k] ? `«${title[k]}»` : k))
}

// Why the primary button is off (an i18n key and its values), or null. `sent` is the {as, want, so} of the analysis on
// screen; null while one is on its way.
export function saveBlock(draft, analysis, sent) {
  const no = (key, vars = {}) => ({ key, vars })
  if (!analysis || outdated(draft, sent)) return no('stories.block.pending')
  if ((analysis.hints || []).some((h) => h.code === 'empty')) return no('stories.block.empty')
  if ((analysis.cycle || []).length) return no('stories.block.cycle', { keys: taskNames(analysis.cycle, draft.tasks).join(' → ') })
  if ((analysis.duplicates || []).length) return no('stories.block.duplicates', { keys: analysis.duplicates.join(', ') })
  const blank = (draft.tasks || []).find((t) => t.checked !== false && !clean(t.title))
  return blank ? no('stories.block.title', { key: blank.key }) : null
}

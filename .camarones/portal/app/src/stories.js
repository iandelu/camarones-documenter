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
// seen the proposals; `sha` is what `save` gets back as base_sha to notice a story changed meanwhile.
export function initialDraft(item) {
  const it = item || {}
  return { id: it.id || null, sha: it.sha || null, as: it.as_ || '', want: it.want || '', so: it.so || '', title: it.title || '',
    epic: it.epic || '', criteria: [...(it.criteria || [])], touches: [...(it.touches || [])], tasks: null, step: 1 }
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

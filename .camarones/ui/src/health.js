// The pure part of the HealthBoard: what the snapshot of lib/health.py says, as words and rows. No React, no DOM, so it
// is tested in node. A value that cannot be read is "—" (never 0); a source that failed is `{error}` and its message
// travels with the row.

const DASH = '—'
const SEVERITIES = ['critical', 'high', 'medium', 'moderate', 'low', 'unknown']
const IMPACTS = ['high', 'medium', 'low', 'unknown']          // worst first
const STATES = ['ok', 'warn', 'bad']

export const AREAS = ['machine', 'docs', 'code']

// A link the snapshot gives us (Sonar's dashboard) is opened only when it is http(s); anything else (javascript:, data:) is text.
export const safeUrl = (u) => (typeof u === 'string' && /^https?:\/\//i.test(u) ? u : null)

const failed = (block) => !!block && typeof block === 'object' && typeof block.error === 'string'
const good = (block) => !!block && typeof block === 'object' && !Array.isArray(block) && !failed(block)
const count = (n) => (typeof n === 'number' && Number.isFinite(n) ? String(n) : null)
const num = (n) => typeof n === 'number' && Number.isFinite(n)
const unknown = (id) => ({ id, state: null, figure: null })       // a fact the snapshot does not hold: "—", neutral
const worst = (states) => states.reduce((a, s) => (STATES.indexOf(s) > STATES.indexOf(a) ? s : a), 'ok')

// One reason of the verdict or of a tile: "Pages to review: 3". A reason with no number says it without one.
export function reasonText({ key, n }, t) {
  return t(`hb.reason.${key}`).replace('{n}', n ?? DASH)
}

// The one line at the top: every reason of every area that is not ok, or that all is well.
export function verdictText(snapshot, t) {
  const verdict = Array.isArray(snapshot?.verdict) ? snapshot.verdict : []
  const allOk = Object.values(snapshot?.areas ?? {}).every((a) => a?.state === 'ok')
  return verdict.length === 0 && allOk ? t('hb.verdictOk') : verdict.map((v) => reasonText(v, t)).join(' · ')
}

// The word that goes with a state's colour. ok reads differently per area; a repo uses the code's words; null is "no
// state" (a repo that is not cloned or could not be read), never green.
export function stateWord(area, state, t) {
  if (!STATES.includes(state)) return t('hb.state.none')
  return state === 'ok' ? t(`hb.state.ok.${area}`) : t(`hb.state.${state}`)
}

// "5 min ago". `now` is a Date or epoch milliseconds; an unreadable date is a dash.
export function fmtAgo(iso, now, t) {
  const then = Date.parse(iso)
  if (Number.isNaN(then)) return DASH
  const minutes = Math.max(0, Math.floor((+now - then) / 60000))
  if (minutes < 1) return t('hb.ago.now')
  if (minutes < 60) return t('hb.ago.min').replace('{n}', minutes)
  if (minutes < 1440) return t('hb.ago.hour').replace('{n}', Math.floor(minutes / 60))
  return t('hb.ago.day').replace('{n}', Math.floor(minutes / 1440))
}

function figureOf(snapshot, area, key) {
  return count(snapshot?.areas?.[area]?.figures?.find((f) => f.key === key)?.n)
}

// The rows of one area, in the order of the spec. `state` null = no fact to rate (blocks, ab).
export function rowsFor(area, snapshot) {
  const unread = (ids, block) => ids.map((id) => ({ id, state: 'warn', figure: null, ...(failed(block) && { error: block.error }) }))
  if (area === 'machine') {
    const m = snapshot?.machine
    if (!good(m)) return unread(['doctor', 'drift'], m)
    return [Array.isArray(m.missing) ? { id: 'doctor', state: m.missing.length ? 'bad' : 'ok', figure: String(m.missing.length) } : unknown('doctor'),
            num(m.drift) ? { id: 'drift', state: m.drift ? 'warn' : 'ok', figure: String(m.drift) } : unknown('drift')]
  }
  if (area === 'docs') {
    const d = snapshot?.docs
    if (!good(d)) return [...unread(['fresh', 'evals', 'context', 'review'], d), { id: 'blocks', state: null, figure: null }, { id: 'ab', state: null, figure: null }]
    const { stale, suspect, evals, context, review } = d
    const err = (...blocks) => blocks.find(failed)
    const row = (id, blocks, rate) => {
      const bad = err(...blocks)
      return bad ? { id, state: 'warn', figure: null, error: bad.error } : rate()
    }
    return [
      row('fresh', [stale, suspect], () => Array.isArray(stale) && Array.isArray(suspect)
        ? { id: 'fresh', state: stale.length ? 'bad' : suspect.length ? 'warn' : 'ok', figure: String(stale.length) }
        : unknown('fresh')),
      row('evals', [evals], () => good(evals) && num(evals.confirmed) && num(evals.total)
        ? { id: 'evals', state: evals.confirmed ? 'ok' : 'warn', figure: `${evals.confirmed}/${evals.total}` }
        : unknown('evals')),
      row('context', [context], () => good(context) && num(context.total) && num(context.budget)
        ? { id: 'context', state: context.over ? 'warn' : 'ok', figure: `${context.total}/${context.budget}` }
        : unknown('context')),
      row('review', [review], () => Number.isInteger(review)
        ? { id: 'review', state: review > 0 ? 'warn' : 'ok', figure: String(review) }
        : unknown('review')),
      { id: 'blocks', state: null, figure: null },
      { id: 'ab', state: null, figure: null },
    ]
  }
  return codeRows(snapshot)
}

function codeRows(snapshot) {
  const repos = snapshot?.repos
  let repoRowOf
  if (failed(repos)) repoRowOf = { id: 'repos', state: 'warn', figure: null, error: repos.error }
  else if (!good(repos)) repoRowOf = { id: 'repos', state: 'warn', figure: null }
  else {
    const known = Object.keys(repos).map((n) => snapshot.repo_state?.[n]).filter((s) => STATES.includes(s))
    const unreadable = Object.values(repos).some(failed)
    repoRowOf = { id: 'repos', figure: String(Object.keys(repos).length),
      state: known.length || unreadable ? worst([...known, ...(unreadable ? ['warn'] : [])]) : null }
  }
  const inv = snapshot?.inventory
  const figure = figureOf(snapshot, 'code', 'code.libraries')
  let libs
  if (failed(inv)) libs = { id: 'libs', state: 'warn', figure, error: inv.error }
  else if (!good(inv)) libs = { id: 'libs', state: null, figure }
  else {
    const tallies = good(repos) ? Object.values(repos).filter((r) => good(r) && r.cloned !== false && good(r.vulns)).map((r) => r.vulns) : []
    const sum = (...keys) => tallies.reduce((a, v) => a + keys.reduce((b, k) => b + (v[k] || 0), 0), 0)
    const old = (snapshot.verdict ?? []).some((v) => v.key === 'code.oldScan')
    libs = { id: 'libs', figure, state: sum('critical', 'high') ? 'bad' : sum('medium') || !inv.scanned || old ? 'warn' : 'ok' }
  }
  return [repoRowOf, libs]
}

const sevText = (vulns, t) => SEVERITIES.concat(Object.keys(vulns).filter((k) => !SEVERITIES.includes(k)))
  .filter((k) => vulns[k] > 0).map((k) => `${SEVERITIES.includes(k) ? t(`hb.sev.${k}`) : k} ${vulns[k]}`).join(' · ')

function debtText(items, t) {
  if (!Array.isArray(items) || !items.length) return DASH
  const rank = (d) => IMPACTS.indexOf(IMPACTS.includes(d.impact) ? d.impact : 'unknown')
  const top = items.reduce((a, d) => (rank(d) < rank(a) ? d : a))
  const trust = ['draft', 'confirmed', 'suspect', 'stale'].includes(top.trust) ? t(`hb.trust.${top.trust}`) : top.trust
  return [items.length, t(`hb.impact.${IMPACTS[rank(top)]}`), trust].filter(Boolean).join(' · ')
}

// One line of the per-repo table, as strings. `scanned`: the inventory was checked for vulnerabilities at least once,
// else "no vulnerabilities" would be a claim nobody checked. `note` says why a repo has no figures; `error` is a
// source's message.
export function repoRow(name, repo, state, t, scanned = true) {
  const row = { name, sonar: DASH, coverage: DASH, vulns: DASH, debt: DASH, state: state ?? null }
  if (failed(repo)) return { ...row, error: repo.error }
  if (!good(repo)) return row
  if (repo.cloned === false) return { ...row, note: t('hb.notCloned') }
  // a sub-block that failed reads "unread" (not a dash: the fact exists, it just could not be read) and its message rides along
  const sub = (block, cell) => {
    if (!failed(block)) return false
    row[cell] = t('hb.unread')
    row.error ??= block.error
    return true
  }
  if (!sub(repo.sonar, 'sonar') && good(repo.sonar)) {
    row.sonar = repo.sonar.used ? t('hb.yes') : t('hb.no')
    if (repo.sonar.used && repo.sonar.link) row.sonarLink = repo.sonar.link
  }
  const cov = repo.coverage
  if (!sub(cov, 'coverage') && good(cov) && typeof cov.percent === 'number') {
    row.coverage = `${cov.percent}%`
    const note = [cov.source, typeof cov.at === 'string' ? cov.at.slice(0, 10) : ''].filter(Boolean).join(' · ')
    if (note) row.coverageNote = note
  }
  if (!sub(repo.vulns, 'vulns') && scanned !== false && good(repo.vulns)) row.vulns = sevText(repo.vulns, t) || '0'
  if (!sub(repo.debt, 'debt')) row.debt = debtText(repo.debt, t)
  return row
}

// What a tile's next-action button does. The app's action wins: it opens that row (the action renders there, once);
// the portal has no actions, so it links; with neither the tile has no button.
export function tileTarget(next, actions, links) {
  if (!next) return null
  if (actions?.[next.row]) return { kind: 'open', row: next.row }
  return links?.[next.row] ? { kind: 'link', href: links[next.row] } : null
}

// A tile's reason with its number. The snapshot's `next` is {key, row}; the number is in the verdict's entry for that key.
export function nextReason(next, verdict, t) {
  return reasonText({ key: next.key, n: (Array.isArray(verdict) ? verdict : []).find((v) => v.key === next.key)?.n }, t)
}

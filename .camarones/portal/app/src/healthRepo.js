// The per-repo health page, pure: what the snapshot of lib/health.py says about one repo, ready to draw. No React, no DOM,
// so it is tested in node. A sub-block that failed (`{error}`) becomes an empty block plus its message in `errors`;
// a value that is not there stays absent (the view writes "—"), never 0.

import { fmtDebt, sonarGone } from '@camaron/ui/health.js'

const STATES = ['ok', 'warn', 'bad']
const RANK = { critical: 0, high: 1, medium: 2, moderate: 2, low: 3 }          // anything else (unknown) goes last

const failed = (block) => !!block && typeof block === 'object' && typeof block.error === 'string'
const good = (block) => !!block && typeof block === 'object' && !Array.isArray(block) && !failed(block)
const object = (x) => !!x && typeof x === 'object' && !Array.isArray(x)          // a list item may carry its own error
const list = (block) => (Array.isArray(block) ? block : [])
const rank = (v) => RANK[v?.severity] ?? 4

// `repo:path` (the form `evidence` and `x-sources` use) → the portal's file view, or null when it is not a file path:
// a folder, a pattern, prose, a URL. The code view finds the file by its path (views/code.js fileIdByPath).
export function evidenceHref(ref) {
  if (typeof ref !== 'string') return null
  const cut = ref.indexOf(':')
  if (cut < 1) return null
  const repo = ref.slice(0, cut)
  const path = ref.slice(cut + 1).replace(/(?::\d+(?:-\d+)?|#L\d+(?:-L?\d+)?)$/, '')          // a line suffix is not part of the path
  const segments = path.split('/')
  const plain = path.includes('/') ? true : /^[\w.-]+$/.test(path)                          // a bare name must be one token ("Dockerfile")
  if (!/^[\w.-]+$/.test(repo) || !path || path.startsWith('/') || path.endsWith('/') || /[*?[\]{}]/.test(path) || !plain
    || segments.some((s) => !s || s === '..')) return null
  return `#/code/${encodeURIComponent(repo)}/f/${segments.map(encodeURIComponent).join('/')}`
}

// The nine figures SonarQube gave for a repo, in the order the page draws them. A figure the server did not give is
// `value: null` (the view writes a dash), never 0; the debt is days and hours.
const percent = (n) => (typeof n === 'number' && Number.isFinite(n) ? `${n}%` : null)
const amount = (n) => (typeof n === 'number' && Number.isFinite(n) ? String(n) : null)
const grade = (g) => (typeof g === 'string' && g ? g : null)
export function sonarFigures(server) {
  if (!object(server)) return []
  const r = object(server.ratings) ? server.ratings : {}
  const debt = fmtDebt(server.debt_minutes)
  return [['coverage', percent(server.coverage)], ['bugs', amount(server.bugs)], ['vulnerabilities', amount(server.vulnerabilities)],
    ['security_hotspots', amount(server.security_hotspots)], ['code_smells', amount(server.code_smells)],
    ['debt_minutes', debt === '—' ? null : debt], ['maintainability', grade(r.maintainability)], ['reliability', grade(r.reliability)],
    ['security', grade(r.security)]].map(([key, value]) => ({ key, value }))
}

// One repo of the snapshot as a page, or null when the project has no such repo.
export function repoPage(snapshot, name) {
  const repos = snapshot?.repos
  if (!good(repos) || !Object.hasOwn(repos, name)) return null
  const repo = repos[name]
  const state = STATES.includes(snapshot.repo_state?.[name]) ? snapshot.repo_state[name] : null
  const page = { name, state, scanned: snapshot.inventory?.scanned === true, sonar: null, coverage: null, reports: [],
    vulnerable: [], debt: {}, pages: [], errors: {}, gate: null, sonarFigures: [], sonarAt: null }
  if (failed(repo)) return { ...page, error: repo.error }
  if (!good(repo)) return page
  if (repo.cloned === false) return { ...page, cloned: false }

  // a block is taken as it is when it can be read; else its message is kept and the block stays empty
  const read = (key, block, ok, empty) => {
    if (failed(block)) { page.errors[key] = block.error; return empty }
    return ok(block)
  }
  // only `{error}` is a Sonar block that could not be read; `used` with `error` is a block whose last read failed: its
  // facts, the figures kept from before and the reason all travel in it
  const sonar = repo.sonar
  if (sonarGone(sonar)) page.errors.sonar = sonar.error
  else if (object(sonar)) {
    page.sonar = sonar
    page.gate = object(sonar.server) && typeof sonar.server.gate === 'string' ? sonar.server.gate : null
    page.sonarFigures = sonarFigures(sonar.server)
    page.sonarAt = object(sonar.server) && typeof sonar.server.at === 'string' ? sonar.server.at : null
    if (typeof sonar.error === 'string') page.sonarError = sonar.error
    if (sonar.connect === true && typeof sonar.host === 'string' && sonar.host) page.connect = sonar.host
  }
  page.coverage = read('coverage', repo.coverage, (b) => (good(b) ? b : null), null)
  page.reports = read('reports', repo.reports, (b) => list(b).filter(object), [])
  page.vulnerable = read('vulnerable', repo.vulnerable, (b) => list(b).filter(object).sort((a, b2) => rank(a) - rank(b2)), [])
  page.debt = read('debt', repo.debt, (b) => {
    const bySource = {}
    for (const d of list(b).filter(object)) (bySource[d.source ?? ''] ??= []).push(d)
    return bySource
  }, {})

  // the pages that cite this repo: stale first, then suspect; either side (or the whole block) may have failed
  const docs = snapshot.docs
  if (failed(docs)) page.errors.pages = docs.error
  else if (good(docs)) {
    for (const state of ['stale', 'suspect']) {
      const block = docs[state]
      if (failed(block)) { page.errors.pages ??= block.error; continue }
      for (const p of list(block)) if (list(p?.repos).includes(name)) page.pages.push({ path: p.path, state })
    }
  }
  return page
}

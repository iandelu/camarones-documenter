import { readFileSync } from 'node:fs'
import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { S, t as text } from '../i18n/index.js'
import { HealthBoard } from './index.js'
import { fmtAgo, fmtDebt, gateWord, nextReason, reasonText, repoRow, rowsFor, safeUrl, sonarConnectHash, sonarReason, sourceWord, tileTarget, verdictText } from './health.js'

const en = (k) => text(k, 'en')
const es = (k) => text(k, 'es')

const repo = (over = {}) => ({ cloned: true, libraries: 4, vulns: {}, vulnerable: [],
  sonar: { used: false, project: '', organization: '', host: '', link: '' }, coverage: null, reports: [], debt: [], ...over })

const snapshot = (over = {}) => ({
  v: 1, at: '2026-10-26T10:00:00Z',
  areas: {
    machine: { state: 'ok', figures: [{ key: 'machine.tools', n: 12 }, { key: 'machine.missing', n: 0 }], next: null },
    docs: { state: 'ok', figures: [{ key: 'docs.stale', n: 0 }, { key: 'docs.review', n: 0 }], next: null },
    code: { state: 'ok', figures: [{ key: 'code.libraries', n: 30 }, { key: 'code.vulnHigh', n: 0 }], next: null },
  },
  verdict: [], repo_state: { api: 'ok' },
  machine: { at: 'x', missing: [], drift: 0, tools: 12 },
  docs: { at: 'x', stale: [], suspect: [], evals: { total: 5, confirmed: 3 }, context: { total: 900, budget: 2000, over: false }, review: 0 },
  inventory: { at: '2026-10-20T00:00:00Z', scanned: true },
  repos: { api: repo() },
  ...over,
})

const bad = (over = {}) => snapshot({
  areas: {
    machine: { state: 'bad', figures: [{ key: 'machine.tools', n: 12 }, { key: 'machine.missing', n: 2 }], next: { key: 'machine.missing', row: 'doctor' } },
    docs: { state: 'warn', figures: [{ key: 'docs.stale', n: null }, { key: 'docs.review', n: 3 }], next: { key: 'docs.review', row: 'review' } },
    code: { state: 'ok', figures: [{ key: 'code.libraries', n: 30 }, { key: 'code.vulnHigh', n: 0 }], next: null },
  },
  verdict: [{ key: 'machine.missing', n: 2 }, { key: 'docs.review', n: 3 }, { key: 'machine.unchecked', n: null }],
  ...over,
})

test('verdictText lists each reason with its number', () => {
  const out = verdictText(bad(), en)
  expect(out).toContain('Missing tools: 2')
  expect(out).toContain('Pages to review: 3')
  expect(out).toContain('Machine not checked yet')
  expect(out).not.toContain('{n}')
  expect(verdictText(bad(), es)).toContain('Herramientas que faltan: 2')
})

test('verdictText says all is well only when every area is ok', () => {
  expect(verdictText(snapshot(), en)).toBe(en('hb.verdictOk'))
  expect(verdictText(bad(), en)).not.toBe(en('hb.verdictOk'))
})

test('fmtAgo says how long ago, in the reader\'s language', () => {
  const now = Date.parse('2026-10-26T12:00:00Z')
  expect(fmtAgo('2026-10-26T11:59:40Z', now, en)).toBe('just now')
  expect(fmtAgo('2026-10-26T11:55:00Z', now, en)).toBe('5 min ago')
  expect(fmtAgo('2026-10-26T09:00:00Z', now, en)).toBe('3 h ago')
  expect(fmtAgo('2026-10-23T12:00:00Z', now, es)).toBe('hace 3 d')
  expect(fmtAgo('nonsense', now, en)).toBe('—')
  expect(fmtAgo(undefined, now, en)).toBe('—')
})

test('repoRow of a repo without Sonar, coverage or debt shows no, and dashes (never 0)', () => {
  const r = repoRow('api', repo(), 'ok', en)
  expect(r).toMatchObject({ name: 'api', sonar: 'no', coverage: '—', debt: '—', vulns: '0', state: 'ok' })
})

test('repoRow of a repo not cloned has a dash in every figure and says so', () => {
  const r = repoRow('web', repo({ cloned: false }), null, en)
  expect(r).toMatchObject({ name: 'web', sonar: '—', coverage: '—', vulns: '—', debt: '—', state: null })
  expect(r.note).toBe(en('hb.notCloned'))
})

test('repoRow of a repo that could not be read carries the message', () => {
  const r = repoRow('web', { error: 'boom' }, null, en)
  expect(r).toMatchObject({ sonar: '—', coverage: '—', vulns: '—', debt: '—', state: null, error: 'boom' })
})

test('repoRow draws coverage with its source and date, vulnerabilities by severity and the worst debt', () => {
  const r = repoRow('api', repo({
    sonar: { used: true, project: 'k', organization: '', host: '', link: 'https://sonar/k' },
    coverage: { percent: 63.4, at: '2026-10-20T08:00:00Z', source: 'jacoco', path: 'target/x.xml' },
    vulns: { medium: 1, high: 2 },
    debt: [{ impact: 'low', trust: 'confirmed' }, { impact: 'high', trust: 'draft' }],
  }), 'bad', en)
  expect(r).toMatchObject({ sonar: 'yes', sonarLink: 'https://sonar/k', coverage: '63.4%', coverageNote: 'jacoco · 2026-10-20',
    vulns: 'high 2 · medium 1', debt: '2 · high · draft', state: 'bad' })
})

test('repoRow keeps unknowns apart from zero: a library list never scanned is a dash', () => {
  expect(repoRow('a', repo(), 'ok', en, false).vulns).toBe('—')
})

test('repoRow shows a failed sub-block as unread and carries the first message', () => {
  const r = repoRow('a', repo({ vulns: { error: 'osv down' }, sonar: { error: 'no radar' }, coverage: { error: 'bad xml' }, debt: { error: 'no page' } }), 'ok', en)
  expect(r).toMatchObject({ sonar: 'unread', coverage: 'unread', vulns: 'unread', debt: 'unread', error: 'no radar' })
  expect(repoRow('a', repo({ vulns: { error: 'osv down' } }), 'ok', en, false)).toMatchObject({ vulns: 'unread', error: 'osv down', sonar: 'no' })
  expect(repoRow('a', repo({ debt: { error: 'no page' } }), 'ok', es)).toMatchObject({ debt: 'sin leer', error: 'no page' })
  expect(repoRow('a', repo(), 'ok', en).error).toBeUndefined()
})

test('the board shows a repo sub-block failure in the table', () => {
  const s = snapshot({ repos: { api: repo({ coverage: { error: 'bad xml' } }) } })
  const out = renderToStaticMarkup(h(HealthBoard, { snapshot: s, initialTab: 'code' }))
  expect(out).toContain('bad xml')
  expect(out).toContain('unread')
})

test('a tile\'s reason carries its number, taken from the verdict (the area\'s next has none)', () => {
  const s = bad()
  expect(s.areas.docs.next).toEqual({ key: 'docs.review', row: 'review' })          // as lib/health.py writes it
  const out = render({})
  expect(out).toContain('<p class="cu-hb-next-why">Pages to review: 3</p>')
  expect(out).toContain('<p class="cu-hb-next-why">Missing tools: 2</p>')
  expect(out).not.toMatch(/cu-hb-next-why">[^<]*—/)
  expect(nextReason({ key: 'docs.review', row: 'review' }, [], en)).toBe('Pages to review: —')    // not in the verdict: unknown
})

test('every state carries its word, not only a colour: rows, tabs and the verdict', () => {
  const s = snapshot({ machine: { at: 'x', missing: ['uv'], drift: 0, tools: 12 } })
  s.areas.machine.state = 'bad'
  s.verdict = [{ key: 'machine.missing', n: 1 }]
  const out = renderToStaticMarkup(h(HealthBoard, { snapshot: s, links: { doctor: '#/d', drift: '#/f' } }))
  const row = (id) => out.match(new RegExp(`data-row="${id}">(.*?)<div class="cu-hb-row-main"`))[1]
  expect(row('doctor')).toContain('<span class="sr-only">At risk</span>')
  expect(row('drift')).toContain('<span class="sr-only">Ready</span>')
  expect(out).toMatch(/cu-hb-tab[^>]*>.*?<span class="sr-only">At risk<\/span>.*?Machine/)
  expect(out).toMatch(/cu-hb-verdict[^>]*>.*?<span class="sr-only">At risk<\/span>/)
  expect(rowsFor('docs', snapshot()).find((r) => r.id === 'blocks').state).toBeNull()
})

test('a fact the snapshot does not hold is a dash and a neutral state, never 0 or undefined', () => {
  const unknown = (id) => ({ id, state: null, figure: null })
  const m = (over) => rowsFor('machine', snapshot({ machine: { at: 'x', missing: [], drift: 0, tools: 1, ...over } }))
  expect(m({ missing: undefined })[0]).toEqual(unknown('doctor'))
  expect(m({ drift: 'n/a' })[1]).toEqual(unknown('drift'))
  expect(m({ drift: undefined })[1]).toEqual(unknown('drift'))
  expect(m({ missing: ['uv'], drift: 0 }).map((r) => r.figure)).toEqual(['1', '0'])
  const d = (over) => Object.fromEntries(rowsFor('docs', snapshot({ docs: { ...snapshot().docs, ...over } })).map((r) => [r.id, r]))
  expect(d({ evals: {} }).evals).toEqual(unknown('evals'))
  expect(d({ evals: { total: 3 } }).evals).toEqual(unknown('evals'))
  expect(d({ evals: { confirmed: 1 } }).evals).toEqual(unknown('evals'))
  expect(d({ context: { over: true } }).context).toEqual(unknown('context'))
  expect(d({ context: { total: 5 } }).context).toEqual(unknown('context'))
  expect(d({ review: undefined }).review).toEqual(unknown('review'))
  expect(d({ stale: undefined }).fresh).toEqual(unknown('fresh'))
  const out = renderToStaticMarkup(h(HealthBoard, { snapshot: snapshot({ docs: { ...snapshot().docs, evals: {} } }), initialTab: 'docs', links: { evals: '#/e' } }))
  expect(out).not.toContain('undefined')
})

test('rowsFor docs gives the six rows in spec order, with the error message of a failed source', () => {
  const s = snapshot()
  s.docs = { ...s.docs, stale: { error: 'no index' }, suspect: { error: 'no index' }, evals: { error: 'bad yaml' } }
  const rows = rowsFor('docs', s)
  expect(rows.map((r) => r.id)).toEqual(['fresh', 'evals', 'context', 'review', 'blocks', 'ab'])
  expect(rows[0]).toMatchObject({ state: 'warn', figure: null, error: 'no index' })
  expect(rows[1]).toMatchObject({ state: 'warn', figure: null, error: 'bad yaml' })
  expect(rows[2]).toMatchObject({ state: 'ok', figure: '900/2000' })
  expect(rows[3]).toMatchObject({ state: 'ok', figure: '0' })
  expect(rows[4]).toEqual({ id: 'blocks', state: null, figure: null })        // no fact in the snapshot
  expect(rows[5]).toEqual({ id: 'ab', state: null, figure: null })
})

test('rowsFor docs rates stale pages bad, suspect and unconfirmed questions warn', () => {
  const s = snapshot()
  s.docs = { ...s.docs, stale: [{ path: 'a.md', repos: [] }], suspect: [{ path: 'b.md', repos: [] }], evals: { total: 4, confirmed: 0 },
    context: { total: 3000, budget: 2000, over: true }, review: 2 }
  const rows = Object.fromEntries(rowsFor('docs', s).map((r) => [r.id, r]))
  expect(rows.fresh).toMatchObject({ state: 'bad', figure: '1' })
  expect(rows.evals).toMatchObject({ state: 'warn', figure: '0/4' })
  expect(rows.context).toMatchObject({ state: 'warn', figure: '3000/2000' })
  expect(rows.review).toMatchObject({ state: 'warn', figure: '2' })
})

test('rowsFor docs with the whole block failed puts the message in every real row', () => {
  const rows = rowsFor('docs', snapshot({ docs: { error: 'down' } }))
  expect(rows.filter((r) => r.error).map((r) => r.id)).toEqual(['fresh', 'evals', 'context', 'review'])
})

test('rowsFor machine and code', () => {
  const m = rowsFor('machine', snapshot({ machine: { at: 'x', missing: ['uv', 'git'], drift: 3, tools: 12 } }))
  expect(m.map((r) => r.id)).toEqual(['doctor', 'drift'])
  expect(m[0]).toMatchObject({ state: 'bad', figure: '2' })
  expect(m[1]).toMatchObject({ state: 'warn', figure: '3' })
  expect(rowsFor('machine', snapshot({ machine: undefined })).map((r) => [r.state, r.figure])).toEqual([['warn', null], ['warn', null]])
  const c = rowsFor('code', snapshot({ repo_state: { api: 'ok', web: 'bad' }, repos: { api: repo(), web: repo() } }))
  expect(c.map((r) => r.id)).toEqual(['repos', 'libs'])
  expect(c[0]).toMatchObject({ state: 'bad', figure: '2' })
  expect(c[1]).toMatchObject({ state: 'ok', figure: '30' })
  expect(rowsFor('code', snapshot({ inventory: { error: 'torn' } }))[1]).toMatchObject({ state: 'warn', error: 'torn' })
  expect(rowsFor('code', snapshot({ inventory: { at: null, scanned: false } }))[1].state).toBe('warn')
  expect(rowsFor('code', snapshot({ repos: { error: 'no workspace' }, repo_state: {} }))[0]).toMatchObject({ state: 'warn', error: 'no workspace' })
})

const render = (props) => renderToStaticMarkup(h(HealthBoard, { snapshot: bad(), ...props }))

test('the board hides a row with neither an action nor a link, and keeps the repo table', () => {
  const out = render({ links: { doctor: '#/doctor' } })
  expect(out).toContain('data-row="doctor"')
  expect(out).not.toContain('data-row="drift"')
  const code = render({ initialTab: 'code' })
  expect(code).toContain('cu-hb-table')
  expect(code).not.toContain('data-row="libs"')
  expect(render({ initialTab: 'code', links: { libs: '#/libs' } })).toContain('data-row="libs"')
})

test('tileTarget: the action wins over the link, a link alone links, neither is nothing', () => {
  const next = { key: 'machine.missing', row: 'doctor' }
  expect(tileTarget(next, { doctor: () => null }, { doctor: '#/d' })).toEqual({ kind: 'open', row: 'doctor' })
  expect(tileTarget(next, {}, { doctor: '#/d' })).toEqual({ kind: 'link', href: '#/d' })
  expect(tileTarget(next, undefined, { doctor: '#/d' })).toEqual({ kind: 'link', href: '#/d' })
  expect(tileTarget(next, { drift: () => null }, {})).toBeNull()
  expect(tileTarget(next, undefined, undefined)).toBeNull()
  expect(tileTarget(null, { doctor: () => null }, {})).toBeNull()
})

const fix = () => h('button', { id: 'fix' }, 'Fix')

test('an app action is drawn once, only inside its row and only while the row is open', () => {
  const closed = render({ actions: { doctor: fix } })
  expect(closed).not.toContain('id="fix"')                      // the tile does not draw it either
  expect(closed).toContain('aria-expanded="false"')
  expect(closed).toContain('cu-hb-next-act')                    // the tile has a button that opens the row
  const open = render({ actions: { doctor: fix }, initialOpen: ['doctor'] })
  expect(open.match(/id="fix"/g)).toHaveLength(1)
  expect(open).toContain('aria-expanded="true"')
})

test('in the portal the tile and the row link, and nothing runs', () => {
  const out = render({ links: { doctor: '#/doctor' } })
  expect(out.match(/href="#\/doctor"/g)).toHaveLength(2)        // tile + row
  expect(out).not.toContain('aria-expanded')
  expect(render({})).not.toContain('cu-hb-next-act')
})

test('Check everything shows only where onRefresh exists', () => {
  expect(render({ onRefresh: () => {} })).toContain(en('hb.refresh'))
  expect(render({})).not.toContain(en('hb.refresh'))
  expect(render({ onRefresh: () => {}, refreshing: true })).toContain('disabled')
})

test('a repo that is not cloned or unread gets a neutral dot and state, never green', () => {
  const s = snapshot({ repos: { web: repo({ cloned: false }) }, repo_state: { web: null } })
  const out = renderToStaticMarkup(h(HealthBoard, { snapshot: s, initialTab: 'code', repoHref: (n) => `#/health/${n}` }))
  expect(out).toContain('cu-hb-dot--none')
  expect(out).toContain(en('hb.state.none'))
  expect(out).toContain(en('hb.notCloned'))
  expect(out).toContain('href="#/health/web"')
})

test('without a snapshot the board says how to get one', () => {
  expect(renderToStaticMarkup(h(HealthBoard, { snapshot: null }))).toContain(en('hb.never'))
})

test('a failed source shows its message in its row', () => {
  const s = snapshot({ docs: { error: 'index unreadable' } })
  const out = renderToStaticMarkup(h(HealthBoard, { snapshot: s, initialTab: 'docs', links: { fresh: '#/review' } }))
  expect(out).toContain('index unreadable')
})

// ---- strings ----

const here = (f) => readFileSync(new URL(f, import.meta.url), 'utf-8')
const IDS = { machine: ['doctor', 'drift'], docs: ['fresh', 'evals', 'context', 'review', 'blocks', 'ab'], code: ['repos', 'libs'] }
const REASONS = ['machine.missing', 'machine.drift', 'machine.unchecked', 'docs.stale', 'docs.suspect', 'docs.context', 'docs.noEvals',
  'docs.review', 'docs.unread', 'code.vulnHigh', 'code.vulnMedium', 'code.noScan', 'code.oldScan', 'code.lowCoverage', 'code.highDebt',
  'code.gateFailed', 'code.unread']
const FIGURES = ['machine.tools', 'machine.missing', 'docs.stale', 'docs.review', 'code.libraries', 'code.vulnHigh']

test('every hb.* key the board names exists in es and en, dynamic families included', () => {
  const used = new Set(['health.jsx', 'health.js'].flatMap((f) => [...here(f).matchAll(/\bt\('(hb\.[\w.-]+)'\s*[,)]/g)].map((m) => m[1])))
  const families = {
    'hb.reason': REASONS, 'hb.fig': FIGURES, 'hb.row': Object.values(IDS).flat(), 'hb.rowWhat': Object.values(IDS).flat(),
    'hb.area': Object.keys(IDS), 'hb.state': ['ok.machine', 'ok.docs', 'ok.code', 'warn', 'bad', 'none'], 'hb.sev': ['critical', 'high', 'medium', 'moderate', 'low', 'unknown'],
    'hb.impact': ['high', 'medium', 'low', 'unknown'], 'hb.trust': ['draft', 'confirmed', 'suspect', 'stale'],
    'hb.col': ['repo', 'sonar', 'coverage', 'vulns', 'debt'], 'hb.ago': ['now', 'min', 'hour', 'day'],
    'hb.gate': ['OK', 'WARN', 'ERROR'], 'hb.source': ['sonar', 'report'],
  }
  for (const [f, ks] of Object.entries(families)) for (const k of ks) used.add(`${f}.${k}`)
  for (const l of ['es', 'en']) expect([...used].filter((k) => !S[l][k]), l).toEqual([])
  expect(Object.keys(S.es).sort()).toEqual(Object.keys(S.en).sort())
})

test('the failed quality gate has its reason in both languages', () => {
  expect(en('hb.reason.code.gateFailed')).toContain('{n}')
  expect(es('hb.reason.code.gateFailed')).toContain('{n}')
  expect(reasonText({ key: 'code.gateFailed', n: 2 }, en)).toContain('2')
})

test('the area words follow the spec in Spanish and English', () => {
  expect([es('hb.state.ok.machine'), es('hb.state.ok.docs'), es('hb.state.ok.code'), es('hb.state.warn'), es('hb.state.bad')])
    .toEqual(['Lista', 'Al día', 'Sano', 'Revisar', 'Riesgo'])
  expect([en('hb.state.ok.machine'), en('hb.state.ok.docs'), en('hb.state.ok.code'), en('hb.state.warn'), en('hb.state.bad')])
    .toEqual(['Ready', 'Up to date', 'Healthy', 'Review', 'At risk'])
})

test('safeUrl keeps http(s) links only', () => {
  expect(safeUrl('https://sonar.example.com/dashboard?id=k')).toBe('https://sonar.example.com/dashboard?id=k')
  expect(safeUrl('http://localhost:9000/x')).toBe('http://localhost:9000/x')
  for (const bad of ['javascript:alert(1)', 'data:text/html,x', '//evil.example', '', null, undefined, 7]) expect(safeUrl(bad)).toBeNull()
})

// ---- step (c): the figures of the SonarQube server ----

const server = (over = {}) => ({ at: '2026-10-26T08:00:00Z', host: 'https://sonar.acme.test', gate: 'OK', coverage: 81.5, bugs: 2, vulnerabilities: 0,
  security_hotspots: 1, code_smells: 40, debt_minutes: 1500, ratings: { maintainability: 'A', reliability: 'B', security: 'A' }, ...over })
const sonar = (over = {}) => ({ used: true, project: 'acme_api', organization: '', host: 'https://sonar.acme.test', link: 'https://sonar.acme.test/dashboard?id=acme_api', ...over })
const NOW = Date.parse('2026-10-26T11:00:00Z')

test('the gate word, in the reader\'s language; a gate nobody gave is a dash', () => {
  expect([gateWord('OK', en), gateWord('WARN', en), gateWord('ERROR', en)]).toEqual(['Passed', 'Warning', 'Failed'])
  expect([gateWord('OK', es), gateWord('WARN', es), gateWord('ERROR', es)]).toEqual(['Aprobado', 'Aviso', 'Suspendido'])
  for (const g of [null, undefined, 'NONE', 7]) expect(gateWord(g, en)).toBe('—')
})

test('the coverage source is a word: Sonar, report/informe; a source we do not know stays as it is', () => {
  expect([sourceWord('sonar', en), sourceWord('report', en), sourceWord('report', es)]).toEqual(['Sonar', 'report', 'informe'])
  expect(sourceWord('jacoco', en)).toBe('jacoco')
  expect(sourceWord(undefined, en)).toBe('')
})

test('debt time in working days of 8 h: "2 d 3 h", minutes under an hour, 0 min, and a dash for nothing', () => {
  expect(fmtDebt(1500)).toBe('3 d 1 h')
  expect(fmtDebt(2 * 480 + 3 * 60)).toBe('2 d 3 h')
  expect(fmtDebt(480)).toBe('1 d')
  expect(fmtDebt(60)).toBe('1 h')
  expect(fmtDebt(479)).toBe('7 h')
  expect(fmtDebt(59)).toBe('59 min')
  expect(fmtDebt(45)).toBe('45 min')
  expect(fmtDebt(0)).toBe('0 min')
  for (const bad of [null, undefined, NaN, Infinity, -5, '90', true]) expect(fmtDebt(bad)).toBe('—')
})

test('a repo row shows the gate word and Sonar\'s coverage with Sonar as its source', () => {
  const r = repoRow('api', repo({ sonar: { ...sonar(), server: server() }, coverage: { percent: 81.5, at: '2026-10-26T08:00:00Z', source: 'sonar', path: null } }), 'ok', en, true, NOW)
  expect(r.sonar).toBe('Passed')
  expect(r.gateState).toBe('ok')
  expect(r.sonarLink).toBe('https://sonar.acme.test/dashboard?id=acme_api')
  expect(r.coverage).toBe('81.5%')
  expect(r.coverageNote).toBe('Sonar · 2026-10-26')
  expect(r.error).toBeUndefined()
  const gone = repoRow('api', repo({ sonar: { ...sonar(), server: server({ gate: 'ERROR' }) } }), 'bad', es, true, NOW)
  expect([gone.sonar, gone.gateState]).toEqual(['Suspendido', 'bad'])
  expect(repoRow('api', repo({ sonar: { ...sonar(), server: server({ gate: 'WARN' }) } }), 'warn', en, true, NOW).gateState).toBe('warn')
  expect(repoRow('api', repo({ sonar: { ...sonar(), server: server({ gate: null }) } }), 'ok', en, true, NOW).sonar).toBe('—')
})

test('the coverage source of a report reads as a word, not as the raw key', () => {
  const r = repoRow('api', repo({ coverage: { percent: 71, at: '2026-10-20', source: 'report', path: 'x' } }), 'ok', es, true, NOW)
  expect(r.coverageNote).toBe('informe · 2026-10-20')
})

test('a Sonar repo without server figures says yes (or no); the gate never shows 0 or a made-up word', () => {
  expect(repoRow('api', repo({ sonar: sonar() }), 'ok', en, true, NOW).sonar).toBe('yes')
  expect(repoRow('api', repo(), 'ok', en, true, NOW).sonar).toBe('no')
})

test('a repo with connect: true exposes the host to connect, and #/machine asks for the token of that host', () => {
  const r = repoRow('api', repo({ sonar: sonar({ connect: true }) }), 'ok', en, true, NOW)
  expect(r.connect).toBe('https://sonar.acme.test')
  expect(repoRow('api', repo({ sonar: sonar() }), 'ok', en, true, NOW).connect).toBeUndefined()
  const bare = repoRow('api', repo({ sonar: sonar({ connect: true, host: '' }) }), 'ok', en, true, NOW)
  expect(bare.connect).toBe('')                                          // SonarCloud or the team's host: none in the block
  expect(sonarConnectHash('')).toBe('#/machine?kind=sonarqube')
  expect(sonarConnectHash('https://sonar.acme.test/a b')).toBe('#/machine?host=https%3A%2F%2Fsonar.acme.test%2Fa%20b&kind=sonarqube')
})

test('a Sonar error with kept values shows the gate, how old they are and the reason', () => {
  const r = repoRow('api', repo({ sonar: { ...sonar(), server: server({ gate: 'ERROR' }), error: 'sin conexión' } }), 'bad', en, true, NOW)
  expect(r.sonar).toBe('Failed')
  expect(r.sonarNote).toBe('from 3 h ago')
  expect(r.error).toBe('No connection')
  expect(repoRow('api', repo({ sonar: { ...sonar(), server: server(), error: 'sin conexión' } }), 'ok', es, true, NOW).sonarNote).toBe('de hace 3 h')
})

test('a Sonar error without values is the reason alone: unread in the cell, the message under the repo', () => {
  const r = repoRow('api', repo({ sonar: { ...sonar(), error: 'proyecto no encontrado' } }), 'warn', en, true, NOW)
  expect(r.sonar).toBe(en('hb.unread'))
  expect(r.sonarNote).toBeUndefined()
  expect(r.error).toBe('Project not found')
  expect(r.sonarLink).toBe('https://sonar.acme.test/dashboard?id=acme_api')
  expect(repoRow('api', repo({ sonar: { error: 'torn' } }), 'warn', en, true, NOW)).toMatchObject({ sonar: en('hb.unread'), error: 'torn' })
})

test('the board draws the gate word, its age and the connect link only where the app gives connectHref', () => {
  const s = snapshot({ repos: { api: repo({ sonar: { ...sonar(), server: server({ gate: 'ERROR' }), error: 'sin conexión' } }), web: repo({ sonar: sonar({ connect: true }) }) },
    repo_state: { api: 'bad', web: 'ok' } })
  const code = (props) => renderToStaticMarkup(h(HealthBoard, { snapshot: s, initialTab: 'code', ...props }))
  const app = code({ connectHref: sonarConnectHash })
  expect(app).toContain('Failed')
  expect(app).toContain('No connection')
  expect(app).toContain(`href="#/machine?host=${encodeURIComponent('https://sonar.acme.test')}&amp;kind=sonarqube"`)
  expect(app).toContain(en('hb.connect'))
  expect(code({})).not.toContain(en('hb.connect'))
  const bare = snapshot({ repos: { web: repo({ sonar: sonar({ connect: true, host: '' }) }) }, repo_state: { web: 'ok' } })
  const out = renderToStaticMarkup(h(HealthBoard, { snapshot: bare, initialTab: 'code', connectHref: sonarConnectHash }))
  expect(out).toContain('href="#/machine?kind=sonarqube"')
  expect(out).not.toContain('host=')
})

test('the six reasons a Sonar read gives are said in the reader\'s language; anything else stays as it came', () => {
  const ids = { 'token no válido': ['Invalid token', 'Token no válido'], 'proyecto no encontrado': ['Project not found', 'Proyecto no encontrado'],
    'sin conexión': ['No connection', 'Sin conexión'], 'respuesta no válida': ['Invalid response', 'Respuesta no válida'],
    'solo https': ['HTTPS only', 'Solo https'], 'host no válido': ['Invalid host', 'Host no válido'] }
  for (const [raw, [inEn, inEs]] of Object.entries(ids)) {
    expect(sonarReason(raw, en)).toBe(inEn)
    expect(sonarReason(raw, es)).toBe(inEs)
  }
  expect(sonarReason('error 502', en)).toBe('error 502')
  expect(sonarReason('error 502', es)).toBe('error 502')
  expect(sonarReason(undefined, en)).toBeUndefined()
})

test('a repo row carries the Sonar reason in the language of the screen', () => {
  const row = (t) => repoRow('api', repo({ sonar: { ...sonar(), error: 'sin conexión' } }), 'warn', t, true, NOW)
  expect(row(en).error).toBe('No connection')
  expect(row(es).error).toBe('Sin conexión')
  expect(repoRow('api', repo({ sonar: { ...sonar(), error: 'error 502' } }), 'warn', en, true, NOW).error).toBe('error 502')
})

import { expect, test } from 'vitest'
import { evidenceHref, repoPage } from './healthRepo.js'

const v = (name, severity, over = {}) => ({ name, version: '1.0', severity, id: `GHSA-${name}`, cve: `CVE-${name}`, fixed: '2.0', ...over })
const item = (source, over = {}) => ({ source, trust: 'draft', item: 'Old ORM', impact: 'high', effort: 'M', evidence: ['api:src/Dao.java'], owner: 'ana', recommendation: 'Replace it', ...over })
const snapshot = {
  inventory: { at: '2026-10-26', scanned: true },
  repo_state: { api: 'bad', web: null, off: 'ok' },
  repos: {
    api: {
      cloned: true, libraries: 3, vulns: { critical: 1, high: 1, medium: 1, low: 1 },
      vulnerable: [v('low-lib', 'low'), v('crit-lib', 'critical'), v('mod-lib', 'moderate'), v('high-lib', 'high'), v('unk-lib', 'unknown'), v('med-lib', 'medium')],
      sonar: { used: true, project: 'org_api', organization: 'org', host: 'sonarcloud.io', link: 'https://sonarcloud.io/dashboard?id=org_api' },
      coverage: { percent: 71.5, at: '2026-10-20', source: 'report', path: 'target/site/jacoco/jacoco.xml' },
      reports: [{ type: 'jacoco', path: 'target/site/jacoco/jacoco.xml', percent: 71.5, at: '2026-10-20' }, { type: 'lcov', path: 'lcov.info', error: 'unreadable' }],
      debt: [item('quality/tech-debt.md'), item('quality/architecture-review.md', { item: 'God class' }), item('quality/tech-debt.md', { item: 'No retries', impact: 'low' })],
    },
    web: { cloned: true, libraries: 0, vulns: {}, vulnerable: [], sonar: { used: false }, coverage: null, reports: [], debt: [] },
    broken: { error: 'cannot read' },
  },
  docs: {
    stale: [{ path: 'repos/api/wiki/a.md', repos: ['api'] }, { path: 'domain/x.md', repos: ['web', 'api'] }, { path: 'domain/y.md', repos: ['web'] }],
    suspect: [{ path: 'guides/s.md', repos: ['api'] }, { path: 'guides/t.md', repos: ['web'] }],
  },
}

test('an unknown repo has no page', () => {
  expect(repoPage(snapshot, 'nope')).toBeNull()
  expect(repoPage(null, 'api')).toBeNull()
  expect(repoPage({}, 'api')).toBeNull()
  expect(repoPage({ repos: { error: 'x' } }, 'api')).toBeNull()
})

test('the state and the sonar, coverage and report blocks come as the snapshot has them', () => {
  const p = repoPage(snapshot, 'api')
  expect(p.name).toBe('api')
  expect(p.state).toBe('bad')
  expect(p.sonar).toMatchObject({ used: true, project: 'org_api' })
  expect(p.coverage).toEqual({ percent: 71.5, at: '2026-10-20', source: 'report', path: 'target/site/jacoco/jacoco.xml' })
  expect(p.reports).toHaveLength(2)
  expect(p.errors).toEqual({})
  expect(repoPage(snapshot, 'web').state).toBeNull()                      // no state is never green
  expect(repoPage(snapshot, 'web').coverage).toBeNull()
})

test('vulnerable libraries come worst first: critical, high, medium (moderate with it), low, unknown', () => {
  expect(repoPage(snapshot, 'api').vulnerable.map((x) => x.name)).toEqual(['crit-lib', 'high-lib', 'mod-lib', 'med-lib', 'low-lib', 'unk-lib'])
})

test('debt is grouped by the page it comes from', () => {
  const { debt } = repoPage(snapshot, 'api')
  expect(Object.keys(debt).sort()).toEqual(['quality/architecture-review.md', 'quality/tech-debt.md'])
  expect(debt['quality/tech-debt.md'].map((d) => d.item)).toEqual(['Old ORM', 'No retries'])
  expect(debt['quality/architecture-review.md']).toHaveLength(1)
  expect(repoPage(snapshot, 'web').debt).toEqual({})
})

test('pages are the stale and suspect ones that cite this repo', () => {
  expect(repoPage(snapshot, 'api').pages).toEqual([
    { path: 'repos/api/wiki/a.md', state: 'stale' }, { path: 'domain/x.md', state: 'stale' }, { path: 'guides/s.md', state: 'suspect' }])
  expect(repoPage(snapshot, 'web').pages.map((x) => x.path)).toEqual(['domain/x.md', 'domain/y.md', 'guides/t.md'])
})

test('a block that failed carries its message and leaves the rest alone', () => {
  const broken = { ...snapshot, repos: { api: { ...snapshot.repos.api, sonar: { error: 'no token' }, coverage: { error: 'bad xml' }, reports: { error: 'walk failed' },
    vulnerable: { error: 'osv down' }, debt: { error: 'page unreadable' } } }, docs: { error: 'docs unreadable' } }
  const p = repoPage(broken, 'api')
  expect(p.errors).toEqual({ sonar: 'no token', coverage: 'bad xml', reports: 'walk failed', vulnerable: 'osv down', debt: 'page unreadable', pages: 'docs unreadable' })
  expect(p).toMatchObject({ sonar: null, coverage: null, reports: [], vulnerable: [], debt: {}, pages: [] })
  expect(repoPage({ ...broken, docs: { stale: { error: 'x' }, suspect: [{ path: 'a.md', repos: ['api'] }] } }, 'api'))
    .toMatchObject({ pages: [{ path: 'a.md', state: 'suspect' }], errors: { pages: 'x' } })
})

test('a repo that could not be read, or is not cloned, says so', () => {
  expect(repoPage(snapshot, 'broken')).toMatchObject({ error: 'cannot read', state: null, vulnerable: [], debt: {} })
  expect(repoPage({ ...snapshot, repos: { off: { cloned: false } } }, 'off')).toMatchObject({ cloned: false, state: 'ok' })
})

test('scanned says whether vulnerabilities were ever looked for', () => {
  expect(repoPage(snapshot, 'api').scanned).toBe(true)
  expect(repoPage({ ...snapshot, inventory: { scanned: false } }, 'api').scanned).toBe(false)
  expect(repoPage({ ...snapshot, inventory: { error: 'x' } }, 'api').scanned).toBe(false)
})

test('evidence repo:path opens the file in the code view; anything else is plain text', () => {
  expect(evidenceHref('api:src/main/Dao.java')).toBe('#/code/api/f/src/main/Dao.java')
  expect(evidenceHref('api:src/my dir/Dao.java')).toBe('#/code/api/f/src/my%20dir/Dao.java')
  expect(evidenceHref('api:Dockerfile')).toBe('#/code/api/f/Dockerfile')
  expect(evidenceHref('api:src/main/')).toBeNull()                        // a folder
  expect(evidenceHref('api:src/**/*.java')).toBeNull()                    // a pattern
  expect(evidenceHref('api:the whole service')).toBeNull()                // prose
  expect(evidenceHref('https://example.com/a.java')).toBeNull()
  expect(evidenceHref('src/Dao.java')).toBeNull()                         // no repo
  expect(evidenceHref('api:')).toBeNull()
  expect(evidenceHref(7)).toBeNull()
})

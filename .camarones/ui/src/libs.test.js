import { expect, test } from 'vitest'
import { advisories, applyFilter, compareVersions, fixTarget, isMajor, latestOf, matrix, outdated, placesOf, proposal, rowsOf, versionSpan } from './libs.js'

const vite = [
  { id: 'GHSA-a', cve: 'CVE-1', severity: 'medium', fixed: '8.3.3', ranges: [{ introduced: '8.0.0', fixed: '8.3.3' }] },
  { id: 'GHSA-b', cve: 'CVE-2', severity: 'high', fixed: '8.3.2' },
  { id: 'GHSA-a', cve: 'CVE-1', severity: 'medium', fixed: '8.3.3' },
  { id: 'GHSA-c', severity: 'low', fixed: null },
]

test('versions compare by their numbers, a pre-release before its release', () => {
  expect(compareVersions('8.3.10', '8.3.9')).toBeGreaterThan(0)
  expect(compareVersions('v1.2.0', '1.2')).toBe(0)
  expect(compareVersions('2.0.0-rc.1', '2.0.0')).toBeLessThan(0)
  expect(compareVersions('42.7.2', '42.7.10')).toBeLessThan(0)
})

test('the version to update to is the lowest that fixes every advisory that has a fix', () => {
  expect(fixTarget(vite)).toBe('8.3.3')
  expect(fixTarget([{ fixed: null }])).toBeNull()
  expect(fixTarget([])).toBeNull()
})

test('advisories: once each, the worst first', () => {
  expect(advisories(vite).map((v) => v.id)).toEqual(['GHSA-b', 'GHSA-a', 'GHSA-c'])
})

test('the rows behind one library of the table: where each repo declares it', () => {
  const rows = [{ ecosystem: 'npm', name: 'vite', repo: 'web' }, { ecosystem: 'npm', name: 'vite', repo: 'docs' },
    { ecosystem: 'PyPI', name: 'vite', repo: 'api' }]
  expect(rowsOf(rows, 'npm|vite').map((r) => r.repo)).toEqual(['docs', 'web'])
})

const lib = (repo, vulns = [], name = 'org.springframework:spring-webmvc') => ({ ecosystem: 'Maven', name, repo, version: '6.1.21',
  declared: '', scope: 'runtime', category: 'framework', language: 'Java', drift: false, vulns })
const hit = [{ id: 'GHSA-x', severity: 'high', fixed: '6.2.19' }]

test('where a library is: the repos it is flagged in first, then the others up to three names', () => {
  const rows = ['wallet-adapter', 'lobby-service', 'backoffice-app', 'content-service', 'integration-service']
    .map((r) => lib(r, ['wallet-adapter', 'integration-service'].includes(r) ? hit : []))
  expect(placesOf(matrix(rows).items[0])).toEqual({
    shown: [{ repo: 'integration-service', flagged: true }, { repo: 'wallet-adapter', flagged: true }, { repo: 'backoffice-app', flagged: false }],
    more: 2,
  })
  const flaggedEverywhere = ['a', 'b', 'c', 'd'].map((r) => lib(r, hit))
  expect(placesOf(matrix(flaggedEverywhere).items[0]).shown.map((p) => p.repo)).toEqual(['a', 'b', 'c', 'd'])
})

test('a repo with several modules keeps every module\'s advisories in its cell', () => {
  const item = matrix([lib('integration-service', hit), lib('integration-service')]).items[0]
  expect(item.cells['integration-service'].vulns).toEqual(hit)
  expect(placesOf(item).shown).toEqual([{ repo: 'integration-service', flagged: true }])
})

// The latest version (lib/latest.py, `inventory.json` key `latest`): the version column, behind or not, what to propose.
const L = { at: '2026-11-11T10:00:00+00:00', checked: 2, found: 2, failed: [], versions: { 'Maven|org.x:boot': '3.4.1', 'npm|left-pad': '2.0.0' } }
const boot = (repo, version, extra = {}) => ({ repo, ecosystem: 'Maven', name: 'org.x:boot', version, declared: version || '',
  scope: 'runtime', category: 'framework', vulns: [], ...extra })

test('the version column: one version, a range when repos differ, the manifest when none is exact', () => {
  expect(versionSpan(matrix([boot('a', '3.2.0')]).items[0])).toBe('3.2.0')
  expect(versionSpan(matrix([boot('a', '3.2.0'), boot('b', '3.1.5')]).items[0])).toBe('3.1.5 – 3.2.0')
  expect(versionSpan(matrix([boot('a', '3.10.0'), boot('b', '3.9.0'), boot('c', '3.9.0')]).items[0])).toBe('3.9.0 – 3.10.0')
  expect(versionSpan(matrix([boot('a', null, { managedBy: 'org.x:parent:1' })]).items[0])).toBe('managed')
  expect(versionSpan(matrix([boot('a', null, { declared: '^1.2.0' })]).items[0])).toBe('^1.2.0')
})

test('outdated only when an exact version is behind; unknown otherwise', () => {
  const two = matrix([boot('a', '3.4.1'), boot('b', '3.1.5')]).items[0]
  expect(latestOf(L, two)).toBe('3.4.1')
  expect(latestOf(null, two)).toBe(null)
  expect(outdated(two, latestOf(L, two))).toBe(true)
  expect(outdated(matrix([boot('a', '3.4.1')]).items[0], '3.4.1')).toBe(false)
  expect(outdated(matrix([boot('a', null, { managedBy: 'p' })]).items[0], '3.4.1')).toBe(null)
  expect(outdated(two, null)).toBe(null)
})

test('a major jump is marked', () => {
  expect(isMajor('16.2.1', '19.0.5')).toBe(true)
  expect(isMajor('v1.2.0', '1.9.0')).toBe(false)
  expect(isMajor(null, '1.0.0')).toBe(false)
})

test('the proposed version: the latest when higher, else the CVE fix, else nothing', () => {
  const vuln = boot('a', '3.2.0', { vulns: [{ id: 'G', severity: 'high', fixed: '3.2.5' }] })
  expect(proposal(vuln, '3.4.1')).toEqual({ version: '3.4.1', fix: '3.2.5', latest: '3.4.1' })
  expect(proposal(vuln, null)).toEqual({ version: '3.2.5', fix: '3.2.5', latest: null })
  expect(proposal(boot('a', '3.4.1'), '3.4.1')).toEqual({ version: '', fix: null, latest: null })
  expect(proposal(boot('a', null), '3.4.1').version).toBe('3.4.1')
})

test('only outdated keeps the rows behind their latest', () => {
  const rows = [boot('a', '3.4.1'), boot('b', '3.1.5')]
  expect(applyFilter(rows, { outdated: true }, L).map((r) => r.repo)).toEqual(['b'])
  expect(applyFilter(rows, { outdated: true }, null)).toEqual([])
  expect(applyFilter(rows, {}, null)).toHaveLength(2)
})

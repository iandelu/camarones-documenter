import { expect, test } from 'vitest'
import { advisories, compareVersions, fixTarget, matrix, placesOf, rowsOf } from './libs.js'

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

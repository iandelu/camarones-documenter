import { describe, expect, it } from 'vitest'
import { applyFilter, facets, matrix, worst } from './libs.js'

const v = (severity, id = 'CVE-1') => ({ id, cve: id, severity, fixed: '2.0' })
const rows = [
  { repo: 'api', ecosystem: 'Maven', name: 'org.postgresql:postgresql', version: '42.7.1', declared: '', scope: 'runtime', category: 'data', language: 'Java', drift: false, vulns: [v('critical')] },
  { repo: 'api', ecosystem: 'npm', name: 'lodash', version: '4.17.20', declared: '4.17.20', scope: 'runtime', category: 'other', language: 'JavaScript', drift: true, vulns: [v('high')] },
  { repo: 'web', ecosystem: 'npm', name: 'lodash', version: '4.17.21', declared: '4.17.21', scope: 'runtime', category: 'other', language: 'JavaScript', drift: true, vulns: [] },
  { repo: 'web', ecosystem: 'npm', name: 'vitest', version: '1.0.4', declared: '^1.0.0', scope: 'dev', category: 'testing', language: 'JavaScript', drift: false },
]

describe('Libraries tab', () => {
  it('ranks severities', () => {
    expect(worst([v('medium'), v('critical'), v('low')])).toBe('critical')
    expect(worst([])).toBeNull()
    expect(worst(undefined)).toBeNull()
  })

  it('builds one row per library with a cell per repo', () => {
    const m = matrix(rows)
    expect(m.repos).toEqual(['api', 'web'])
    const lodash = m.items.find((x) => x.name === 'lodash')
    expect(lodash.cells.api.version).toBe('4.17.20')
    expect(lodash.cells.web.version).toBe('4.17.21')
    expect(lodash.drift).toBe(true)
    expect(lodash.worst).toBe('high')
    expect(m.items[0].name).toBe('org.postgresql:postgresql')      // the worst vulnerability first
  })

  it('filters by category, language, repo, scope and vulnerable only', () => {
    expect(applyFilter(rows, { category: 'testing' }).map((r) => r.name)).toEqual(['vitest'])
    expect(applyFilter(rows, { language: 'Java' })).toHaveLength(1)
    expect(applyFilter(rows, { repo: 'web' })).toHaveLength(2)
    expect(applyFilter(rows, { scope: 'dev' })).toHaveLength(1)
    expect(applyFilter(rows, { vulnerable: true }).map((r) => r.repo)).toEqual(['api', 'api'])
    expect(applyFilter(rows, { q: 'POSTGRES' })).toHaveLength(1)
    expect(applyFilter(rows, {})).toHaveLength(4)
  })

  it('counts each facet for the filter chips', () => {
    const f = facets(rows)
    expect(f.category).toEqual([['other', 2], ['data', 1], ['testing', 1]])
    expect(f.language).toEqual([['JavaScript', 3], ['Java', 1]])
  })
})

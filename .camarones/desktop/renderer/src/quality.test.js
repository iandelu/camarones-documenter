import { expect, test } from 'vitest'
import { BOARD_ACTIONS, doctorRows, inventoryArgs, pytestSummary, scanProgress, seconds, setupProgress } from './quality.js'

const fix = (cmd, args = {}) => ({ cmd, args })

test('the doctor\'s findings: what is missing first, with its fix; what is optional apart; what is fine last', () => {
  const r = {
    prerequisites: [{ name: 'git', ok: true, need: true }, { name: 'node', ok: false, need: true, fix: fix('doctor', { install: 'node' }) },
      { name: 'docker', ok: false, need: false, hint: 'Docker Desktop' }],
    tools: [{ name: 'likec4', ok: false, found: '1.0.0', pinned: '1.2.0', fix: fix('setup') }, { name: 'mmdc', ok: true, found: '11.4.1', pinned: '11.4.1' }],
    drift: [],
  }
  const { missing, optional, fine } = doctorRows(r)
  expect(missing.map((x) => [x.name, x.kind, x.fix?.cmd])).toEqual([['node', 'pre', 'doctor'], ['likec4', 'tool', 'setup']])
  expect(optional.map((x) => x.name)).toEqual(['docker'])
  expect(fine.map((x) => x.name)).toEqual(['git', 'mmdc'])
  expect(doctorRows(null)).toEqual({ missing: [], optional: [], fine: [] })
})

test('pytest\'s last tally, as counts', () => {
  expect(pytestSummary(['...', '== 3 failed, 120 passed, 2 skipped in 9.1s =='])).toEqual([['failed', '3'], ['passed', '120'], ['skipped', '2']])
  expect(pytestSummary(['collecting'])).toEqual([])
})

test('setup\'s progress: the steps it reports done against the steps it will take', () => {
  expect(setupProgress(['  ✔ git', '  ✔ node', 'installing likec4…'], 4)).toEqual({ done: 2, pct: 50 })
  expect(setupProgress(['✔ a', '✔ b', '✔ c'], 2)).toEqual({ done: 3, pct: 100 })
  expect(setupProgress([], 0)).toEqual({ done: 0, pct: 0 })
})

test('a check\'s time in seconds, for "checked n min ago"', () => {
  expect(seconds('2026-10-25T10:00:00Z')).toBe(Date.UTC(2026, 9, 25, 10) / 1000)
  expect(seconds('nonsense')).toBeNull()
})

test('the board rows whose controls the app owns; review is a link and repos a table, neither an action', () => {
  expect(BOARD_ACTIONS).toEqual(['doctor', 'drift', 'fresh', 'evals', 'context', 'blocks', 'ab', 'libs'])
  expect(BOARD_ACTIONS).not.toContain('review')
  expect(BOARD_ACTIONS).not.toContain('repos')
})

// `inventory --cves` logs `[n/total] repo: …` as it starts each repo; its --json result also lands in the log.
test('the vulnerability scan\'s progress: the repo it reads, the ones before it done', () => {
  expect(scanProgress([])).toEqual({ n: 0, total: 0, repo: '', done: [] })
  const lines = ['[1/3] api: scanning for known vulnerabilities (offline database)…', '[2/3] web: scanning for known vulnerabilities…']
  expect(scanProgress(lines)).toEqual({ n: 2, total: 3, repo: 'web', done: ['api'] })
  const end = [...lines, '[3/3] worker: scanning…', '✔ 2 libraries with known vulnerabilities', '{', '  "libraries": [],', '}']
  expect(scanProgress(end)).toEqual({ n: 3, total: 3, repo: 'worker', done: ['api', 'web'] })
  expect(scanProgress(undefined).total).toBe(0)
})

// Back on Libraries while a scan runs (started here, then the section was left): the same arguments attach to it.
test('a running inventory job gives back the arguments that attach to it', () => {
  const job = (kind) => ({ id: '1', kind, status: 'running' })
  expect(inventoryArgs([job('cmd:inventory --json --cves')])).toEqual({ json: true, cves: true })
  expect(inventoryArgs([job('cmd:inventory --json')])).toEqual({ json: true, cves: false })
  expect(inventoryArgs([job('cmd:inventory --json --cves --fail-on high')])).toBeNull()     // not ours: it fails CI
  expect(inventoryArgs([job('cmd:doctor --json')])).toBeNull()
  expect(inventoryArgs([])).toBeNull()
  expect(inventoryArgs(undefined)).toBeNull()
})

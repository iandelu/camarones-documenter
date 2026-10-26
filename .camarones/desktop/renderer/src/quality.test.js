import { expect, test } from 'vitest'
import { BOARD_ACTIONS, doctorRows, pytestSummary, seconds, setupProgress } from './quality.js'

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

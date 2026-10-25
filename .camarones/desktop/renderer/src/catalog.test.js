import { expect, test } from 'vitest'
import { inPanel, others, sectionFor, ZONES } from './catalog.js'

const c = (name, zone, more = {}) => ({ name, zone, verdict: 'app', destructive: false, ...more })

test('each section reads the catalog zones of its work', () => {
  expect(ZONES).toMatchObject({ plan: ['generate'], interviews: ['interviews'], team: ['team'], quality: ['check', 'analyze'],
    machine: ['machine'] })
})

test('quality and machine leave out what their panels run', () => {
  const cmds = ['doctor', 'eval', 'ab', 'inventory', 'fresh', 'blocks', 'check', 'radar'].map((n) => c(n, n === 'radar' ? 'analyze' : 'check'))
  expect(others(cmds, 'quality').safe.map((x) => x.name)).toEqual(['check', 'radar'])
  const m = ['setup', 'config', 'sync', 'detect', 'stack', 'profile', 'self-update', 'repair', 'version'].map((n) => c(n, 'machine'))
  expect(others([...m, c('uninstall', 'machine', { destructive: true }), c('unlink', 'machine', { destructive: true })], 'machine'))
    .toEqual({ safe: [m[8]], careful: [c('unlink', 'machine', { destructive: true })] })
})

test('all the commands of a section, but the ones its panels already run; what deletes goes last', () => {
  const cmds = [c('run', 'generate'), c('autopilot', 'generate'), c('wiki', 'generate'), c('pr', 'generate'),
    c('remote', 'team'), c('ci', 'team'), c('confirm', 'generate', { verdict: 'portal' }),
    c('unlink', 'team', { destructive: true })]
  expect(others(cmds, 'plan')).toEqual({ safe: [cmds[2], cmds[3]], careful: [] })
  expect(others(cmds, 'team')).toEqual({ safe: [cmds[5]], careful: [cmds[7]] })
  expect(others(cmds, 'summary')).toEqual({ safe: [], careful: [] })
  expect(others(null, 'plan')).toEqual({ safe: [], careful: [] })
})

// The ⌘K palette takes you to a command: the section whose panel runs it, else the one whose "All commands" lists it.
test('where the app runs each command', () => {
  expect(sectionFor(c('doctor', 'check'))).toBe('quality')
  expect(inPanel(c('doctor', 'check'))).toBe(true)
  expect(sectionFor(c('radar', 'analyze'))).toBe('quality')
  expect(inPanel(c('radar', 'analyze'))).toBe(false)
  expect(sectionFor(c('uninstall', 'machine', { destructive: true }))).toBe('machine')
  expect(sectionFor(c('confirm', 'generate', { verdict: 'portal' }))).toBeNull()
  expect(sectionFor(c('up', 'docs'))).toBeNull()
  expect(sectionFor(c('ci', 'team'), ['summary', 'plan'])).toBeNull()      // a section this window lacks
})

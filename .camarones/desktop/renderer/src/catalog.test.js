import { expect, test } from 'vitest'
import { others, ZONES } from './catalog.js'

const c = (name, zone, more = {}) => ({ name, zone, verdict: 'app', destructive: false, ...more })

test('each section reads the catalog zones of its work', () => {
  expect(ZONES).toMatchObject({ plan: ['generate'], interviews: ['interviews'], team: ['team'] })
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

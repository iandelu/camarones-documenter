import { expect, test } from 'vitest'
import { chord, entries, GO, keyFor, pick, typing } from './palette.js'

const ALL = ['summary', 'board', 'plan', 'interviews', 'team', 'quality', 'libs', 'docs', 'machine', 'guide', 'kitdev']
const t = (k) => `<${k}>`

test('one letter per section, each section once', () => {
  expect(GO).toEqual({ s: 'summary', b: 'board', p: 'plan', i: 'interviews', t: 'team', q: 'quality', l: 'libs', d: 'docs', m: 'machine', h: 'guide', k: 'kitdev' })
  expect(keyFor('guide')).toBe('h')
  expect(GO.b).toBe('board')
  expect(keyFor('board')).toBe('b')
  expect(keyFor('quality')).toBe('q')
  expect(keyFor('nope')).toBeUndefined()
})

test('g and then a letter goes to its section, while the g is fresh', () => {
  const g = chord(0, 'g', 1000, ALL)
  expect(g).toEqual({ pending: 1000, go: null })
  expect(chord(g.pending, 'p', 1800, ALL)).toEqual({ pending: 0, go: 'plan' })
  expect(chord(g.pending, 'p', 3000, ALL).go).toBeNull()           // too late: a lone p
  expect(chord(0, 'p', 1000, ALL).go).toBeNull()                    // no g first
  expect(chord(g.pending, 'x', 1200, ALL)).toEqual({ pending: 0, go: null })
  expect(chord(g.pending, 'g', 1200, ALL)).toEqual({ pending: 1200, go: null })   // g g: the second g starts again
})

test('a section this window does not have is no shortcut', () => {
  const without = ALL.filter((s) => s !== 'kitdev')
  expect(chord(1000, 'k', 1100, without).go).toBeNull()
})

test('keys typed into a field or a dialog are text, not shortcuts', () => {
  const el = (tagName, more = {}) => ({ tagName, isContentEditable: false, closest: () => null, ...more })
  expect(typing(el('INPUT'))).toBe(true)
  expect(typing(el('TEXTAREA'))).toBe(true)
  expect(typing(el('SELECT'))).toBe(true)
  expect(typing(el('DIV', { isContentEditable: true }))).toBe(true)
  expect(typing(el('BUTTON', { closest: (s) => (s === 'dialog' ? {} : null) }))).toBe(true)
  expect(typing(el('A'))).toBe(false)
  expect(typing(null)).toBe(false)
})

const cmd = (name, zone, more = {}) => ({ name, zone, verdict: 'app', es: `es ${name}`, en: `en ${name}`, ...more })

test('the sections with their shortcut, the other projects that exist, the actions and the reachable commands', () => {
  const groups = entries({
    sections: ['summary', 'plan', 'quality', 'machine'], t, lang: 'es',
    projects: [{ name: 'api', path: '/a', exists: true, current: true }, { name: 'web', path: '/w', exists: true },
      { name: 'old', path: '/o', exists: false }],
    commands: [cmd('doctor', 'check'), cmd('radar', 'analyze'), cmd('confirm', 'generate', { verdict: 'portal' }),
      cmd('ci', 'team')],
  })
  const by = Object.fromEntries(groups.map((g) => [g.id, g]))
  expect(groups.map((g) => g.id)).toEqual(['sections', 'projects', 'actions', 'commands', 'guide'])
  expect(by.sections.label).toBe('<pal.sections>')
  expect(by.sections.items[1]).toEqual({ id: 'go:plan', label: '<nav.plan>', keys: ['g', 'p'], href: '#/plan' })
  expect(by.projects.items.map((i) => i.label)).toEqual(['web'])
  expect(by.projects.items[0].project.path).toBe('/w')
  expect(by.actions.items.map((i) => i.id)).toEqual(['read', 'review', 'search', 'add', 'tour'])
  expect(by.actions.items[0].href).toBe('../#/')
  // doctor runs in a Quality panel; radar sits in Quality's "All commands"; confirm is the portal's; team is not here
  expect(by.commands.items).toEqual([
    { id: 'cmd:doctor', label: 'es doctor', sub: 'camaron doctor', href: '#/quality' },
    { id: 'cmd:radar', label: 'es radar', sub: 'camaron radar', href: '#/quality/radar' },
  ])
})

test('with no query, everything but the commands; typing finds them too', () => {
  const groups = entries({ sections: ['summary', 'machine'], t: (k) => ({ 'nav.machine': 'Máquina' })[k] || k, lang: 'es',
    commands: [cmd('setup', 'machine', { es: 'Preparar la máquina' }), cmd('version', 'machine', { es: 'Versión' })] })
  expect(pick(groups, '').map((g) => g.id)).toEqual(['sections', 'actions'])
  const found = pick(groups, 'maquina')                              // accents and case aside
  expect(found.map((g) => [g.id, g.items.map((i) => i.label)])).toEqual([
    ['sections', ['Máquina']], ['commands', ['Preparar la máquina']]])
})

test('every word must match, in the label or its hint; labels that start with the query come first', () => {
  const groups = [{ id: 'commands', label: 'C', items: [
    { id: 'a', label: 'Revisar el radar', sub: 'camaron radar' },
    { id: 'b', label: 'Radar de tecnologías', sub: 'camaron radar' },
    { id: 'c', label: 'Doctor', sub: 'camaron doctor' }] }]
  expect(pick(groups, 'radar')[0].items.map((i) => i.id)).toEqual(['b', 'a'])
  expect(pick(groups, 'camaron doc')[0].items.map((i) => i.id)).toEqual(['c'])
  expect(pick(groups, 'zzz')).toEqual([])
})

test('the guide chapters show once you type, like the commands', () => {
  const guide = [{ id: 'guide:app/plan', label: 'Plan', sub: 'The app', href: '#/guide/app/plan' }]
  const groups = entries({ sections: ALL, t, guide })
  expect(pick(groups, '').map((g) => g.id)).not.toContain('guide')
  const found = pick(groups, 'plan').find((g) => g.id === 'guide')
  expect(found.label).toBe('<pal.guide>')
  expect(found.items).toEqual(guide)
})

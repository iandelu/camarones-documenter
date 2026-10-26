import { expect, test } from 'vitest'
import { firstRunPending, firstRunRoute, initials, MACHINE, PROJECT, sectionOf, sections } from './nav.js'

test('a project has its sections; this machine has its own, Kit dev only in a kit checkout', () => {
  expect(PROJECT).toEqual(['summary', 'plan', 'interviews', 'team', 'quality', 'docs'])
  expect(sections({ kitdev: false }).machine).toEqual(['machine'])
  expect(sections({ kitdev: true }).machine).toEqual(MACHINE)
})

test('the address picks the section; anything else is the summary', () => {
  expect(sectionOf('#/plan', {})).toBe('plan')
  expect(sectionOf('#/plan/unit-x', {})).toBe('plan')
  expect(sectionOf('#/kitdev', { kitdev: true })).toBe('kitdev')
  expect(sectionOf('#/kitdev', { kitdev: false })).toBe('summary')
  expect(sectionOf('', {})).toBe('summary')
  expect(sectionOf('#/nope', {})).toBe('summary')
})

// The first-run wizard is a place of its own (#/start), never listed in the nav.
test('start is a known section, not in the nav', () => {
  expect(sectionOf('#/start', {})).toBe('start')
  expect([...PROJECT, ...MACHINE]).not.toContain('start')
})

// A project whose first run is unfinished opens on the wizard; a finished one stays where it was asked (the summary).
test('a finished first run opens on summary', () => {
  expect(firstRunRoute({ done: true }, '#/summary')).toBeNull()
  expect(firstRunRoute({ done: true }, '')).toBeNull()
})

test('an unfinished first run goes to the wizard', () => {
  expect(firstRunRoute({ done: false }, '#/plan')).toBe('#/start')
  expect(firstRunRoute({ done: false }, '')).toBe('#/start')
  expect(firstRunRoute({ done: false }, '#/start')).toBeNull()
  expect(firstRunRoute(null, '#/plan')).toBeNull()            // no state (the read failed): stay
})


test('the rail names a project by its initials', () => {
  expect(initials('petclinic')).toBe('PE')
  expect(initials('spring-petclinic-rest')).toBe('SP')
  expect(initials('api pagos')).toBe('AP')
  expect(initials('')).toBe('?')
})

// Someone who left the wizard for another section sees, on the Summary, a way back while the first run is unfinished.
test('the first run is pending only while the state says done: false', () => {
  expect(firstRunPending({ done: false })).toBe(true)
  expect(firstRunPending({ done: true })).toBe(false)
  expect(firstRunPending(null)).toBe(false)                    // no state (the read failed): no notice
  expect(firstRunPending({})).toBe(false)
})

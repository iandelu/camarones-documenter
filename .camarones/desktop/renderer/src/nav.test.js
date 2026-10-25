import { expect, test } from 'vitest'
import { initials, MACHINE, PROJECT, sectionOf, sections } from './nav.js'

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


test('the rail names a project by its initials', () => {
  expect(initials('petclinic')).toBe('PE')
  expect(initials('spring-petclinic-rest')).toBe('SP')
  expect(initials('api pagos')).toBe('AP')
  expect(initials('')).toBe('?')
})

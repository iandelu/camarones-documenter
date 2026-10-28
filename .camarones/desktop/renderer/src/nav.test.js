import { expect, test } from 'vitest'
import { firstRunPending, firstRunRoute, initials, MACHINE, PROJECT, sectionOf, sections, termOf, tokenPrefill } from './nav.js'

test('a project has its sections; this machine has its own, Kit dev only in a kit checkout', () => {
  expect(PROJECT).toEqual(['summary', 'board', 'decisions', 'plan', 'interviews', 'team', 'quality', 'libs', 'docs'])
  expect(sections({ kitdev: false }).machine).toEqual(['machine', 'guide'])
  expect(sections({ kitdev: true }).machine).toEqual(MACHINE)
  expect(MACHINE).toEqual(['machine', 'guide', 'kitdev'])
})

test('the guide is a place of this app, with a guide and a chapter in its address', () => {
  expect(sectionOf('#/guide', {})).toBe('guide')
  expect(sectionOf('#/guide/app/plan', {})).toBe('guide')
})

test('the board sits right after the summary', () => {
  expect(PROJECT[1]).toBe('board')
  expect(sectionOf('#/board', {})).toBe('board')
})

test('the decisions sit right after the board, and every place inside them is theirs', () => {
  expect(PROJECT[2]).toBe('decisions')
  expect(sectionOf('#/decisions', {})).toBe('decisions')
  expect(sectionOf('#/decisions/0012', {})).toBe('decisions')
  expect(sectionOf('#/decisions/new', {})).toBe('decisions')
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

// Quality links to the Tokens card with the host and the kind to fill in: #/machine?host=<h>&kind=sonarqube.
test('the Machine address can prefill the token form', () => {
  expect(tokenPrefill('#/machine?host=https%3A%2F%2Fsonar.example.com%2Fsonar&kind=sonarqube'))
    .toEqual({ host: 'https://sonar.example.com/sonar', kind: 'sonarqube' })
  expect(tokenPrefill('#/machine?host=gitlab.example.com')).toEqual({ host: 'gitlab.example.com', kind: '' })
  expect(tokenPrefill('#/machine?kind=nope&host=x')).toEqual({ host: 'x', kind: '' })
  expect(tokenPrefill('#/machine')).toEqual({ host: '', kind: '' })
  expect(tokenPrefill('#/plan?host=x&kind=sonarqube')).toEqual({ host: '', kind: '' })
  expect(tokenPrefill('')).toEqual({ host: '', kind: '' })
  expect(sectionOf('#/machine?host=x&kind=sonarqube', {})).toBe('machine')
})

test('an address can ask the Plan for one terminal', () => {
  expect(termOf('#/plan?term=t-explain_api-2')).toBe('t-explain_api-2')
  expect(termOf('#/plan')).toBe(null)
  expect(termOf('#/plan?term=../x')).toBe(null)
  expect(termOf('#/board?term=t-a-1')).toBe(null)
})

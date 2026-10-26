import { expect, test } from 'vitest'
import { action, doctorNote } from './summary.js'

test('the last doctor check, as one notice: what is missing and how many kit files drifted; nothing when all is fine', () => {
  expect(doctorNote({ missing: ['node'], tools: ['likec4', 'mmdc'], drift: 2 })).toEqual({ names: ['node', 'likec4', 'mmdc'], drift: 2 })
  expect(doctorNote({ missing: [], tools: [], drift: 1 })).toEqual({ names: [], drift: 1 })
  expect(doctorNote({ missing: [], tools: [], drift: 0 })).toBeNull()
  expect(doctorNote(null)).toBeNull()                                     // never checked: the Summary says nothing
})

const unit = (id, runner, type = id) => ({ id, runner, type, title: `Title of ${id}` })

test('an agent unit opens a session with the agent; one left half done continues it', () => {
  expect(action({ kind: 'next', unit: unit('discovery-api', 'agent', 'discovery') }))
    .toEqual({ kind: 'agent', unit: 'discovery-api', mode: 'new', label: 'next.start' })
  expect(action({ kind: 'resume', unit: unit('discovery-api', 'agent', 'discovery') }))
    .toEqual({ kind: 'agent', unit: 'discovery-api', mode: 'continue', label: 'next.resume' })
})

test('the units the wizard runs go where that work is done', () => {
  expect(action({ kind: 'next', unit: unit('setup', 'wizard') })).toEqual({ kind: 'link', href: '#/machine', label: 'next.machine' })
  expect(action({ kind: 'next', unit: unit('answers', 'wizard') })).toEqual({ kind: 'link', href: '#/interviews', label: 'next.answers' })
  expect(action({ kind: 'next', unit: unit('ci', 'wizard') })).toEqual({ kind: 'link', href: '#/team', label: 'next.ci' })
  expect(action({ kind: 'next', unit: unit('confirm', 'wizard') })).toEqual({ kind: 'link', href: '../#/review', label: 'next.review' })
  expect(action({ kind: 'next', unit: unit('portal', 'wizard') })).toEqual({ kind: 'link', href: '../#/', label: 'next.read' })
  expect(action({ kind: 'next', unit: unit('odd', 'wizard') })).toEqual({ kind: 'link', href: '#/plan', label: 'next.plan' })
})

test('then review in the portal, then read', () => {
  expect(action({ kind: 'review', count: 3 })).toEqual({ kind: 'link', href: '../#/review', label: 'next.review' })
  expect(action({ kind: 'done' })).toEqual({ kind: 'link', href: '../#/', label: 'next.read' })
  expect(action(null)).toEqual({ kind: 'link', href: '../#/', label: 'next.read' })
})

test('an interview unit sends you to choose how interviews run until someone chose it', () => {
  const iv = { kind: 'next', unit: unit('interview-context', 'agent') }
  expect(action(iv, { interviews: null })).toEqual({ kind: 'link', href: '#/interviews', label: 'iv.choose' })
  expect(action(iv, { interviews: 'team' }).kind).toBe('agent')
  expect(action(iv).kind).toBe('agent')
})

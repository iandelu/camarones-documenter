import { expect, test } from 'vitest'
import { action } from './summary.js'

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

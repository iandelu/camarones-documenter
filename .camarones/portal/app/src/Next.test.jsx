// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { STRINGS } from './i18n.js'
import Native from './Native.jsx'

// The landing view rendered for real (React in jsdom, the server's answers mocked).
globalThis.IS_REACT_ACT_ENVIRONMENT = true
const unit = (id, status, available, extra = {}) => ({ id, title: `Title of ${id}`, status, available, runner: 'agent', ...extra })
const ANSWERS = {
  pipeline: { units: [unit('setup', 'done', false), unit('discovery:api', 'todo', true, { repo: 'api', type: 'discovery', phase: 1 })], run: null },
  tree: { docs: [{ path: 'overview/index.md', space: 'docs', type: 'doc' }], views: [], kitGuides: [] },
  'status?check=0': { queue: [{}, {}, {}], plan: { done: 1, total: 2 } },
  build: { id: '1', label: 'First look (no AI)', status: 'running' },
  'jobs/1': { id: '1', status: 'done', log: [] },
  'app/agents': { agents: [{ id: 'claude', label: 'Claude Code' }], last: 'claude' },
  'app/onboard/state': { name: 'shop', mode: 'new', kind: 'legacy', steps: ['repos', 'intro'], step: 'repos', done: false, repos: [], found: [] },
}
const DEFAULTS = structuredClone(ANSWERS)
let host, root

beforeEach(() => {
  Object.assign(ANSWERS, structuredClone(DEFAULTS))                 // each test starts from the same project
  vi.stubGlobal('fetch', vi.fn(async (url) => new Response(JSON.stringify(ANSWERS[String(url).replace(/^api\//, '')] ?? {}),
    { status: 200, headers: { 'Content-Type': 'application/json' } })))
  host = document.body.appendChild(document.createElement('div'))
  root = createRoot(host)
})
afterEach(() => { act(() => root.unmount()); host.remove(); vi.unstubAllGlobals() })

// The views load lazily (a dynamic import, slow the first time): wait for what the test looks at, not a fixed number of ticks.
const until = async (check) => { for (let i = 0; i < 160 && !check(); i++) await act(async () => { await new Promise((r) => setTimeout(r, 25)) }) }

test('Next step offers the first available unit, the review count and the way to another unit', async () => {
  await act(async () => root.render(createElement(Native, { view: 'next', arg: null })))
  await until(() => host.querySelector('.nx-review'))
  const text = host.textContent
  expect(text).toContain('Next step')
  expect(text).toContain('The plan has 2 units; 1 done.')
  expect(text).toContain('Title of discovery:api')
  expect(text).not.toContain('Title of setup')
  expect(text).toContain('Phase 1 · discovery · api')                 // one line on the unit: where it sits in the plan
  expect(host.querySelector('.nx-first')).toBeNull()                  // the docs are not empty: no first-look card
  expect(text).toContain('3 drafts wait for review')
  expect(host.querySelector('a[href="#/pipeline"]').textContent).toBe(STRINGS.en.nxAnother)
  expect(host.querySelector('a[href="#/review"]')).not.toBeNull()
})

test('#/start keeps rendering the first-run wizard, not Next step', async () => {
  await act(async () => root.render(createElement(Native, { view: 'start', arg: null })))
  await until(() => host.querySelector('.ob'))
  expect(host.querySelector('.ob')).not.toBeNull()
  expect(host.querySelector('.nx')).toBeNull()
})

test('a finished plan says so instead of offering a unit', async () => {
  ANSWERS.pipeline = { units: [unit('setup', 'done', false)], run: null }
  await act(async () => root.render(createElement(Native, { view: 'next', arg: null })))
  await until(() => host.querySelector('.nx-card'))
  expect(host.textContent).toContain(STRINGS.en.nxAllDone)
  expect(host.querySelector('.agent-launch')).toBeNull()
})

test('the note on a unit is its one-line description', async () => {
  ANSWERS.pipeline = { units: [unit('fix', 'todo', true, { notes: 'Apply the review feedback\nsecond line', type: 'review-fixes', phase: 7 })], run: null }
  await act(async () => root.render(createElement(Native, { view: 'next', arg: null })))
  await until(() => host.querySelector('.nx-review'))
  expect(host.querySelector('.nx-card h3 + p').textContent).toBe('Apply the review feedback')
})

test('an empty project offers the first look without AI, runs it as a job and reloads', async () => {
  ANSWERS.tree = { docs: [], views: [], kitGuides: [] }
  await act(async () => root.render(createElement(Native, { view: 'next', arg: null })))
  await until(() => host.querySelector('.nx-first'))
  const go = [...host.querySelectorAll('button')].find((b) => b.textContent === STRINGS.en.nxFirstGo)
  expect(go).toBeTruthy()
  ANSWERS.tree = { docs: [{ path: 'architecture/first-look.md', space: 'docs', type: 'doc' }], views: [], kitGuides: [] }   // what the job writes
  await act(async () => go.click())
  await until(() => !host.querySelector('.nx-first'))
  expect(host.querySelector('.nx-first')).toBeNull()
  expect(fetch.mock.calls.some(([u, o]) => String(u) === 'api/build' && JSON.parse(o.body).what === 'first-look')).toBe(true)
})

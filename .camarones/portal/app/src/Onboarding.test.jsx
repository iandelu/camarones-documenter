// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { STRINGS } from './i18n.js'
import Onboarding from './Onboarding.jsx'

// The repos step rendered for real (React in jsdom, the server's answers mocked): Continue follows the ticks.
globalThis.IS_REACT_ACT_ENVIRONMENT = true
const STATE = { name: 'shop', mode: 'new', kind: 'legacy', steps: ['repos', 'tools', 'setup', 'stack', 'arch', 'intro'],
  step: 'repos', done: false, repos: [], found: [{ name: 'api', url: '', branch: 'main', kind: 'service' }] }
let host, root

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (url) => new Response(JSON.stringify(String(url).endsWith('onboard/state') ? STATE : {}),
    { status: 200, headers: { 'Content-Type': 'application/json' } })))
  host = document.body.appendChild(document.createElement('div'))
  root = createRoot(host)
})
afterEach(() => { act(() => root.unmount()); host.remove(); vi.unstubAllGlobals() })

const flush = () => act(async () => { for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, 0)) })
const button = (label) => [...host.querySelectorAll('button')].find((b) => b.textContent === label)

test('legacy with nothing ticked: Continue is off and says why; ticking a repo turns it on', async () => {
  await act(async () => root.render(createElement(Onboarding)))
  await flush()
  const go = button(STRINGS.en.obContinue)
  expect(host.querySelector('.ob-head').textContent).toContain('shop')
  expect(go.disabled).toBe(true)
  expect(host.querySelector('.ob-next').textContent).toContain(STRINGS.en.obNeedRepo)
  await act(async () => host.querySelector('.ob-rows input[type=checkbox]').click())
  expect(button(STRINGS.en.obContinue).disabled).toBe(false)
  expect(host.querySelector('.ob-next').textContent).not.toContain(STRINGS.en.obNeedRepo)
})

test('a repo added by URL comes with its name and branch, and the branch stays editable', async () => {
  await act(async () => root.render(createElement(Onboarding)))
  await flush()
  const set = (el, v) => act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await set(host.querySelector(`input[aria-label="${STRINGS.en.obAddLabel}"]`), 'https://gitlab.com/shop/payments.git')
  expect(host.querySelector(`input[aria-label="${STRINGS.en.obAddName}"]`).value).toBe('payments')
  await set(host.querySelector(`input[aria-label="${STRINGS.en.obAddBranch}"]`), 'develop')
  await act(async () => button(STRINGS.en.obAddRepo).click())
  const branch = host.querySelector(`input[aria-label="${STRINGS.en.obBranchOf.replace('{repo}', 'payments')}"]`)
  expect(branch.value).toBe('develop')
  expect(button(STRINGS.en.obContinue).disabled).toBe(false)              // added repos come ticked
})

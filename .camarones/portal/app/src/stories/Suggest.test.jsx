import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { I18N } from '../i18n/portal.js'
import { Suggest } from './Suggest.jsx'

// The AI button of Historias: in each place AI helps (rewrite, criteria, subtasks), marked ✨ like Ask's, even when it
// cannot run — then it is disabled and says why.
const ai = { state: null, run: () => {}, dismiss: () => {} }
const html = (gate) => renderToStaticMarkup(<Suggest ai={ai} what="criteria" gate={gate} onAccept={() => {}} />)
const button = (out) => out.match(/<button[^>]*>[^<]*<\/button>/)[0]
const ON = { on: true, why: null, runner: 'claude' }
const at = (a, what) => renderToStaticMarkup(<Suggest ai={a} what={what} gate={ON} onAccept={() => {}} />)

test('the button is marked ✨ with its runner and runs when it can', () => {
  const b = button(html({ on: true, why: null, runner: 'claude' }))
  expect(b).toContain(`✨ ${I18N.en['stories.ai.suggest']} · claude`)
  expect(b).not.toContain('disabled')
})

test('when it cannot run the button stays, disabled, with the reason next to it', () => {
  for (const why of ['stories.ai.why.off', 'stories.ai.why.runner', 'stories.ai.why.token']) {
    const out = html({ on: false, why, runner: null })
    const b = button(out)
    expect(b).toContain('disabled=""')
    expect(b).toContain(`✨ ${I18N.en['stories.ai.suggest']}<`)
    const id = b.match(/aria-describedby="([^"]+)"/)[1]
    expect(out).toContain(`id="${id}"`)
    expect(out).toContain(I18N.en[why])
  }
})

// While it thinks, the button that started it is the indicator (the pending button of React Aria, the shimmering
// "Thinking" of ChatGPT and Claude): it keeps the focus, cannot be pressed again and says how to cancel next to it.
test('while it thinks its button shimmers, is pending and cannot be pressed again', () => {
  const out = at({ ...ai, state: { what: 'criteria', running: true } }, 'criteria')
  const b = out.match(/<button[^>]*>.*?<\/button>/)[0]
  expect(b).toContain('aria-disabled="true"')
  expect(b).toContain('aria-busy="true"')
  expect(b).not.toContain('disabled=""')
  expect(b).toContain(`<span class="cu-thinking">${I18N.en['stories.ai.thinking']}</span>`)
  expect(out).toMatch(new RegExp(`role="status"[^>]*>.*${I18N.en['stories.ai.escape']}`))
})

test('while one kind thinks the others wait, disabled and still', () => {
  const b = button(at({ ...ai, state: { what: 'criteria', running: true } }, 'tasks'))
  expect(b).toContain('disabled=""')
  expect(b).not.toContain('aria-busy')
  expect(b).toContain(`✨ ${I18N.en['stories.ai.suggest']} · claude`)
})

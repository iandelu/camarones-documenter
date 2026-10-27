import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { I18N } from '../i18n/portal.js'
import { Suggest } from './Suggest.jsx'

// The AI button of Historias: in each place AI helps (rewrite, criteria, subtasks), marked ✨ like Ask's, even when it
// cannot run — then it is disabled and says why.
const ai = { state: null, run: () => {}, dismiss: () => {} }
const html = (gate) => renderToStaticMarkup(<Suggest ai={ai} what="criteria" gate={gate} onAccept={() => {}} />)
const button = (out) => out.match(/<button[^>]*>[^<]*<\/button>/)[0]

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

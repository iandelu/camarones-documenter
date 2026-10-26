import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { FirstRunNotice } from './sections/Summary.jsx'
import { setLang } from './i18n.js'

afterEach(() => setLang('es'))

// While the first run is unfinished, the Summary offers the way back to the wizard (#/start), in both languages.
test('an unfinished first run gets a notice with a button back to the wizard', () => {
  const out = renderToStaticMarkup(<FirstRunNotice />)
  expect(out).toContain('El primer arranque del proyecto está a medias.')
  expect(out).toMatch(/<a [^>]*href="#\/start"[^>]*>Seguir con la preparación<\/a>/)
  setLang('en')
  const en = renderToStaticMarkup(<FirstRunNotice />)
  expect(en).toContain('first run is not finished.')
  expect(en).toMatch(/>Continue setting it up<\/a>/)
})

import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import App from './App.jsx'

afterEach(() => { delete globalThis.window })

// WCAG 2.4.1: a project's window starts with a link past the rail and the sidebar, to its main landmark, which can
// take the focus (the link moves it there itself: the hash is the router's).
test('a project window skips to its content', () => {
  globalThis.window = { camaronApp: { token: 't' } }
  const out = renderToStaticMarkup(<App />)
  expect(out).toMatch(/^<div class="dk"><a class="cu-skip" href="#main">[^<]+<\/a>/)
  expect(out).toContain('<main class="dk-main" id="main" tabindex="-1">')
})

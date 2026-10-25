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

// The palette has a button for who does not know ⌘K, and each section shows its g shortcut (drawn, not read twice).
test('the header opens the palette and the sidebar shows the shortcuts', () => {
  globalThis.window = { camaronApp: { token: 't' } }
  const out = renderToStaticMarkup(<App />)
  expect(out).toMatch(/<button type="button" class="dk-find" aria-haspopup="dialog">[^<]+<span class="cu-keys">/)
  expect(out).toContain('<span class="dk-hint" aria-hidden="true"><span class="cu-keys"><kbd class="cu-kbd">g</kbd><kbd class="cu-kbd">p</kbd></span></span>')
  expect(out).toContain('<dialog class="dk-pal"></dialog>')
})

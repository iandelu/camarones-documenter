import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import Shell from './Shell.jsx'

// WCAG 2.4.1: the portal starts with a link past the header and the sidebar to its main landmark, which can take the
// focus (the link moves it there itself: the hash is the router's).
test('the portal skips to its content', () => {
  const out = renderToStaticMarkup(<Shell />)
  expect(out).toMatch(/^<a class="cu-skip" href="#native">[^<]+<\/a><header class="top">/)
  expect(out).toContain('<main id="native" class="main native" tabindex="-1">')
})

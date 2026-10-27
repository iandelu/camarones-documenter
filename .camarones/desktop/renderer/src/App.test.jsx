import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import App from './App.jsx'

afterEach(() => { delete globalThis.window; delete globalThis.location })

// The first-run wizard (#/start) is full width: no rail of projects, no section nav; the header and status bar stay.
test('the first-run wizard has the window to itself', () => {
  globalThis.window = { camaronApp: { token: 't' } }
  globalThis.location = { hash: '#/start' }
  const out = renderToStaticMarkup(<App />)
  expect(out).toMatch(/^<div class="dk dk-full">/)
  expect(out).not.toContain('dk-rail')
  expect(out).not.toContain('dk-side')
  expect(out).toContain('<header class="dk-top">')
  expect(out).toContain('<main class="dk-main" id="main" tabindex="-1">')
  globalThis.location = { hash: '#/plan' }
  expect(renderToStaticMarkup(<App />)).toContain('dk-rail')
})

// WCAG 2.4.1: a project's window starts with a link past the rail and the sidebar, to its main landmark, which can
// take the focus (the link moves it there itself: the hash is the router's).
test('a project window skips to its content', () => {
  globalThis.window = { camaronApp: { token: 't' } }
  const out = renderToStaticMarkup(<App />)
  expect(out).toMatch(/^<div class="dk"><a class="cu-skip" href="#main">[^<]+<\/a>/)
  expect(out).toContain('<main class="dk-main" id="main" tabindex="-1">')
})

// main (d2c94ca): the header is the window's title bar; with no menu bar on screen, ⋯ opens the app menu.
test('the project header offers the app menu when the window has one', () => {
  globalThis.window = { camaronApp: { token: 't', menu: () => {} } }
  expect(renderToStaticMarkup(<App />)).toMatch(/<button type="button" class="dk-icon" aria-label="[^"]+" title="[^"]+">⋯<\/button><\/header>/)
  globalThis.window = { camaronApp: { token: 't' } }
  expect(renderToStaticMarkup(<App />)).not.toContain('⋯')
})

test('the hub has the same title bar', () => {
  globalThis.window = { camaronHub: { list: () => new Promise(() => {}) } }
  expect(renderToStaticMarkup(<App />)).toMatch(/^<header class="dk-titlebar"><a class="cu-brand"/)
})

// The start screen (sketch A): what to document, two ways in, no more create / add.
test("the hub asks what to document and offers a folder or the team's docs", () => {
  globalThis.window = { camaronHub: { list: () => new Promise(() => {}) } }
  const out = renderToStaticMarkup(<App />)
  expect(out).toContain('<h1 class="t-impact">¿Qué quieres documentar?</h1>')
  expect(out).toMatch(/<button type="button" class="cu-btn cu-btn--primary">Elegir…<\/button>/)
  expect(out).toMatch(/<button type="button" class="cu-btn cu-btn--secondary">Unirme…<\/button>/)
  expect(out).not.toContain('Crear proyecto')
  expect(out).not.toContain('Añadir carpeta')
})

// The palette has a button for who does not know ⌘K, and each section shows its g shortcut (drawn, not read twice).
test('the header opens the palette and the sidebar shows the shortcuts', () => {
  globalThis.window = { camaronApp: { token: 't' } }
  const out = renderToStaticMarkup(<App />)
  expect(out).toMatch(/<button type="button" class="dk-find" aria-haspopup="dialog">[^<]+<span class="cu-keys">/)
  expect(out).toContain('<span class="dk-hint" aria-hidden="true"><span class="cu-keys"><kbd class="cu-kbd">g</kbd><kbd class="cu-kbd">p</kbd></span></span>')
  expect(out).toContain('<dialog class="dk-pal"></dialog>')
})

// I3: the portal is the reader and has no token; a project's header has the way to it, in the system browser (a button
// calling app.openExternal, never a link the window would navigate).
test('the project header has Ver portal, a button that opens the browser', () => {
  globalThis.window = { camaronApp: { token: 't', openExternal: () => {} } }
  const out = renderToStaticMarkup(<App />)
  expect(out).toMatch(/<button type="button" class="cu-btn cu-btn--ghost cu-btn--sm">Ver portal[^<]*(<svg[^>]*>.*?<\/svg>)?<\/button>/)
  expect(out.split('<header')[1].split('</header>')[0]).not.toMatch(/<a [^>]*href="\.\.\//)
})

// CAMARON.md: breadcrumbs on every view. Inside Decisiones the section itself is a step back, then the place.
test('a place inside the decisions adds its crumb and links back to the list', () => {
  globalThis.window = { camaronApp: { token: 't' } }
  globalThis.location = { hash: '#/decisions/0012' }
  const crumbs = renderToStaticMarkup(<App />).split('<nav class="cu-crumbs"')[1].split('</nav>')[0]
  expect(crumbs).toContain('<a href="#/decisions">Decisiones</a>')
  expect(crumbs).toContain('<span aria-current="page">ADR 0012</span>')
  globalThis.location = { hash: '#/decisions' }
  expect(renderToStaticMarkup(<App />)).toContain('<span aria-current="page">Decisiones</span>')
  globalThis.location = { hash: '#/plan' }
  expect(renderToStaticMarkup(<App />)).toContain('<span aria-current="page">Plan</span>')
})

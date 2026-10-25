import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

// The views take every colour from the theme (public/theme/tokens.css): a raw colour here would skip the dark theme
// and the contrast guard of tokens.test.js.
const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '')

test.each(['../public/legacy/app.css', './styles.css'])('%s defines no raw colours', (rel) => {
  expect(read(rel).match(/#[0-9a-f]{3,8}\b|rgba?\(\s*\d/gi) ?? []).toEqual([])
})

test('legacy variables alias the theme in one place', () => {
  const css = read('../public/legacy/app.css')
  for (const v of ['--bg', '--raise', '--ink', '--muted', '--line', '--accent', '--on-accent', '--ok', '--warn', '--danger'])
    expect(css).toMatch(new RegExp(`${v}:\\s*var\\(--`))
  expect(css).not.toMatch(/prefers-color-scheme/)          // theming lives in theme/tokens.css only
})

test('in the desktop app the header is the window\'s title bar', () => {
  const css = read('../public/legacy/app.css')
  const rule = (sel) => { const i = css.indexOf(`${sel} {`); return i < 0 ? '' : css.slice(i, css.indexOf('}', i)) }
  expect(rule(':root.in-app')).toMatch(/--top:[^;]*env\(titlebar-area-height/)          // as tall as the system controls
  const top = rule('.in-app .top')
  expect(top).toMatch(/-webkit-app-region:\s*drag/)
  expect(top).toMatch(/background:\s*var\(--bg\)/)                                  // solid, like the controls drawn over it
  expect(top).toMatch(/padding-left:[^;]*env\(titlebar-area-x/)                      // macOS traffic lights
  expect(top).toMatch(/padding-right:[^;]*env\(titlebar-area-width/)                 // Windows / Linux controls
  expect(css).toMatch(/\.in-app \.top :is\([^)]*button[^)]*\)\s*\{[^}]*-webkit-app-region:\s*no-drag/)
})

test('the app header has View portal and Projects, both hidden until the app shows them', () => {
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf-8')
  expect(html).toMatch(/<button id="view-portal"[^>]*\shidden/)
  expect(html).toMatch(/<button id="projects"[^>]*\shidden/)
})

test('the app nav lives in the shell, hidden until the app shows it, and keeps the narrow drawer', () => {
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf-8')
  expect(html).toMatch(/<aside class="side appnav" id="app-nav" hidden>/)         // .side: the #menu drawer opens it
  const css = read('../public/legacy/app.css')
  expect(css).toMatch(/body\.app-mode \.side\.appnav\s*\{\s*display:\s*block/)     // wins over native-mode / bare hiding .side
  expect(css).toMatch(/body\.app-mode #side, body\.app-mode \.toc\s*\{\s*display:\s*none/)   // the docs tree is portal-only
  expect(css).toMatch(/@media \(max-width: 900px\)\s*\{\s*body\.app-mode \.layout[^}]*minmax\(0, 1fr\)[^}]*\}\s*body\.app-mode \.menu/)
})

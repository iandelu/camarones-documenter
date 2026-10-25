import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

// The views take every colour from the theme (.camarones/ui/theme/tokens.css): a raw colour here would skip the dark
// theme and the contrast guard of ui/theme/tokens.test.js.
const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '')

test.each(['./portal.css', './styles.css', './shell/shell.css', './views/views.css'])('%s defines no raw colours', (rel) => {
  expect(read(rel).match(/#[0-9a-f]{3,8}\b|rgba?\(\s*\d/gi) ?? []).toEqual([])
})

// WCAG 2.4.7: a rule that drops the outline gives the focus another visible mark (a border or a shadow) itself.
test.each(['./portal.css', './styles.css', './shell/shell.css', './views/views.css'])('%s never hides the focus', (rel) => {
  for (const [, sel, body] of read(rel).matchAll(/([^{}]+)\{([^}]*outline:\s*(?:none|0)\b[^}]*)\}/g)) {
    expect(sel, sel.trim()).toMatch(/:focus/)
    expect(body, sel.trim()).toMatch(/box-shadow|border/)
  }
})

// WCAG 2.5.8: the portal's own small and icon buttons, the tree's section titles and the audience switch are 24 px
// targets or more (links inside a sentence are exempt).
test('small and icon buttons are 24 px targets', () => {
  const css = read('./portal.css')
  for (const sel of ['button.small', 'button.icon', '.side .group-title', '.audience button']) {
    const body = css.match(new RegExp(`(?:^|\\n)${sel.replace(/\./g, '\\.')}[^{]*\\{([^}]*)\\}`))[1]
    expect(parseFloat((body.match(/min-height:\s*([\d.]+)rem/) || [0, 0])[1]) * 16, sel).toBeGreaterThanOrEqual(24)
  }
})

// WCAG 2.4.11: the sticky header never covers what an anchor or the keyboard scrolls to.
test('the sticky header leaves room above a scrolled-to target', () => {
  expect(read('./portal.css')).toMatch(/html\s*\{[^}]*scroll-padding-top:\s*calc\(var\(--top\)/)
})

test('legacy variables alias the theme in one place', () => {
  const css = read('./portal.css')
  for (const v of ['--bg', '--raise', '--ink', '--muted', '--line', '--accent', '--on-accent', '--ok', '--warn', '--danger'])
    expect(css).toMatch(new RegExp(`${v}:\\s*var\\(--`))
  expect(css).not.toMatch(/prefers-color-scheme/)          // theming lives in theme/tokens.css only
})

test('page links in the KPIs lists and tables are 24 px targets', () => {
  expect(read('./styles.css')).toMatch(/#native \.kpi-table td a, #native a\.more,\s*#native ul\.plain li > a\s*\{[^}]*min-height:\s*1\.5rem/)
})

// WCAG 2.4.7 / 4.1.2: React Flow makes every edge focusable, with no ring and nothing to do; the nodes keep the focus
// (and Enter or Space on one opens its drawer like a click).
test('the pipeline graph does not stop the keyboard on its edges', () => {
  const src = readFileSync(new URL('./Pipeline.jsx', import.meta.url), 'utf-8')
  expect(src).toContain('edgesFocusable={false}')
  expect(src).toMatch(/closest\?\.\('\.react-flow__node'\)[\s\S]{0,80}e\.key === 'Enter' \|\| e\.key === ' '/)
  expect(read('./styles.css')).toMatch(/#native \.react-flow__node:focus-visible\s*\{[^}]*outline:\s*2px solid var\(--color-acento-texto\)/)
})

test('in the desktop app the header is the window\'s title bar', () => {
  const css = read('./portal.css')
  const rule = (sel) => { const i = css.indexOf(`${sel} {`); return i < 0 ? '' : css.slice(i, css.indexOf('}', i)) }
  expect(rule(':root.in-app')).toMatch(/--top:[^;]*env\(titlebar-area-height/)          // as tall as the system controls
  const top = rule('.in-app .top')
  expect(top).toMatch(/-webkit-app-region:\s*drag/)
  expect(top).toMatch(/background:\s*var\(--bg\)/)                                  // solid, like the controls drawn over it
  expect(top).toMatch(/padding-left:[^;]*env\(titlebar-area-x/)                      // macOS traffic lights
  expect(top).toMatch(/padding-right:[^;]*env\(titlebar-area-width/)                 // Windows / Linux controls
  expect(css).toMatch(/\.in-app \.top :is\([^)]*button[^)]*\)\s*\{[^}]*-webkit-app-region:\s*no-drag/)
})

// The React shell does what the plain scripts did: marks the app's window, opens the app menu from ⋯ (no menu bar on
// screen) and tells the window the reader's theme, so the controls drawn over the header match it.
test('the shell drives the title bar in the desktop app', () => {
  const shell = readFileSync(new URL('./shell/Shell.jsx', import.meta.url), 'utf-8')
  expect(shell).toContain("classList.toggle('in-app', !!APP)")
  expect(shell).toMatch(/APP\?\.menu && <button[^>]*aria-label=\{t\('appMenu'\)\}/)
  expect(readFileSync(new URL('./core.js', import.meta.url), 'utf-8')).toMatch(/APP\?\.theme\?\.\(isDark\(\) \? 'dark' : 'light'\)/)
})

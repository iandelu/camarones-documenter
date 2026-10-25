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

// WCAG 2.5.8: the portal's own small and icon buttons are 24 px targets or more.
test('small and icon buttons are 24 px targets', () => {
  const css = read('./portal.css')
  for (const sel of ['button.small', 'button.icon']) {
    const body = css.match(new RegExp(`${sel.replace('.', '\\.')}[^{]*\\{([^}]*)\\}`))[1]
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

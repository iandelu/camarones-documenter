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

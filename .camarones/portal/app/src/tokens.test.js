import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

// The theme (public/theme/tokens.css): Cofundo's tokens plus a derived dark theme. Text must stay readable in both.
const css = readFileSync(new URL('../public/theme/tokens.css', import.meta.url), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '')

// The body of the first `{ … }` block that follows `head`, nested blocks included.
function block(text, head) {
  const at = text.indexOf(head)
  if (at < 0) throw new Error(`no block ${head}`)
  const open = text.indexOf('{', at)
  let depth = 0
  for (let i = open; i < text.length; i++) {
    if (text[i] === '{') depth++
    else if (text[i] === '}' && --depth === 0) return text.slice(open + 1, i)
  }
  throw new Error(`unclosed block ${head}`)
}

const declarations = (body) => Object.fromEntries([...body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]))

function tokens(theme) {
  const light = declarations(block(css, ':root {'))
  return theme === 'light' ? light : { ...light, ...declarations(block(css, ':root[data-theme="dark"]')) }
}

function rgb(value) {
  const hex = value.match(/^#([0-9a-f]{6})$/i)
  if (!hex) throw new Error(`not a 6-digit hex colour: ${value}`)
  return [0, 2, 4].map((i) => parseInt(hex[1].slice(i, i + 2), 16) / 255)
}

function luminance(value) {
  const [r, g, b] = rgb(value).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

test.each(['light', 'dark'])('text tokens reach 4.5:1 on the canvas (%s)', (theme) => {
  const t = tokens(theme)
  for (const fg of ['--color-ink', '--color-ink-soft', '--color-ink-dim', '--color-acento-texto',
                    '--color-estado-bien', '--color-estado-aviso', '--color-estado-mal'])
    for (const bg of ['--color-canvas', '--color-canvas-elevated'])
      expect(contrast(t[fg], t[bg]), `${fg} on ${bg}`).toBeGreaterThanOrEqual(4.5)
  expect(contrast(t['--color-on-accent'], t['--color-accent'])).toBeGreaterThanOrEqual(4.5)
})

test('the dark block repeats under prefers-color-scheme', () => {
  const media = block(css, '@media (prefers-color-scheme: dark)')
  expect(declarations(block(media, ':root:not([data-theme="light"])')))
    .toEqual(declarations(block(css, ':root[data-theme="dark"]')))
})

test('fonts are self-hosted', () => {
  expect(css).not.toMatch(/fonts\.(googleapis|gstatic)\.com/)
  expect(css).toMatch(/url\(["']?fonts\/Inter\.woff2/)
  expect(css).toMatch(/url\(["']?fonts\/BigShoulders\.woff2/)
})

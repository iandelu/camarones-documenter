import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

// The theme shared by the portal and the desktop app: Cofundo's tokens plus a derived dark theme. Text must stay
// readable in both.
const css = readFileSync(new URL('./tokens.css', import.meta.url), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '')

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

// The aurora hero carries small text (eyebrow, notes). Over its strongest stop, mixed over the canvas as app.css does
// (strength 1 light, 0.5 dark), that text uses --color-ink-soft: --color-ink-dim drops to about 3.3:1 there.
const mix = (fg, pct, bg) => '#' + rgb(fg).map((c, i) => Math.round(255 * (c * pct + rgb(bg)[i] * (1 - pct))))
  .map((v) => v.toString(16).padStart(2, '0')).join('')

test.each([['light', 1], ['dark', 0.5]])('small text on the aurora stays readable (%s)', (theme, strength) => {
  const t = tokens(theme)
  for (const [stop, pct] of [['--color-aurora-cyan', 0.58], ['--color-aurora-violet', 0.62], ['--color-aurora-pink', 0.52]]) {
    const bg = mix(t[stop], pct * strength, t['--color-canvas'])
    expect(contrast(t['--color-ink-soft'], bg), `ink-soft on ${stop}`).toBeGreaterThanOrEqual(4.5)
  }
  const app = readFileSync(new URL('../../portal/app/public/legacy/app.css', import.meta.url), 'utf-8')
  expect(app).toMatch(/\.aurora-bg \.eyebrow, \.aurora-bg \.muted \{ color: var\(--color-ink-soft\); \}/)
})

test('the dark block repeats under prefers-color-scheme', () => {
  const media = block(css, '@media (prefers-color-scheme: dark)')
  expect(declarations(block(media, ':root:not([data-theme="light"])')))
    .toEqual(declarations(block(css, ':root[data-theme="dark"]')))
})

// Camarón's corners are square, not Cofundo's pills (CAMARON.md, Radii).
test('radii stay square', () => {
  const radii = Object.entries(tokens('light')).filter(([name]) => /^--(radius|consola-radio)-/.test(name))
  expect(radii.length).toBeGreaterThan(0)
  for (const [name, value] of radii) {
    const px = value.match(/^(\d+(?:\.\d+)?)(px|rem)$/)
    expect(px, `${name}: ${value}`).not.toBeNull()
    expect(px[2] === 'rem' ? Number(px[1]) * 16 : Number(px[1]), name).toBeLessThanOrEqual(6)
  }
})

test('fonts are self-hosted', () => {
  expect(css).not.toMatch(/fonts\.(googleapis|gstatic)\.com/)
  expect(css).toMatch(/url\(["']?fonts\/Inter\.woff2/)
  expect(css).toMatch(/url\(["']?fonts\/BigShoulders\.woff2/)
})

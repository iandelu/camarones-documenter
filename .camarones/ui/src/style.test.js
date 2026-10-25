import { readdirSync, readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

// The kit takes every colour from the theme, draws no emoji (text glyphs only, CAMARON.md) and sizes by svh, never vh.
const dir = new URL('./', import.meta.url)
const files = readdirSync(dir).filter((f) => /\.(css|jsx?)$/.test(f) && !f.includes('.test.'))
const read = (f) => readFileSync(new URL(f, dir), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

test('there are kit files to check', () => expect(files).toContain('ui.css'))

test.each(files)('%s has no raw colours', (f) => {
  expect(read(f).match(/#[0-9a-f]{3,8}\b|rgba?\(\s*\d|hsla?\(\s*\d/gi) ?? []).toEqual([])
})

test.each(files)('%s has no emoji', (f) => {
  expect(read(f).match(/\p{Extended_Pictographic}/gu) ?? []).toEqual([])
})

test.each(files)('%s sizes by svh, not vh', (f) => {
  expect(read(f).match(/\d(?:\.\d+)?vh\b/g) ?? []).toEqual([])
})

test('everything interactive shows a focus ring', () => {
  expect(read('ui.css')).toMatch(/:focus-visible\s*\{[^}]*outline:\s*2px solid var\(--color-acento-texto\)/)
})

// WCAG 2.4.7: one ring for every interactive element of both apps, not only the kit's own classes; --color-acento-texto
// reaches 4.5:1 on both canvases (theme/tokens.test.js), well over the 3:1 a focus indicator needs.
test('the focus ring covers links, buttons, fields, folds and anything focusable', () => {
  const rule = read('ui.css').match(/:where\(([^)]*(?:\([^)]*\)[^)]*)*)\):focus-visible\s*\{/)
  expect(rule).not.toBeNull()
  for (const sel of ['a[href]', 'button', 'input', 'select', 'textarea', 'summary', '[tabindex]'])
    expect(rule[1]).toContain(sel)
})

// WCAG 2.5.8: 24 × 24 px at least; the small button is the smallest control.
test('the small button is a 24 px target or more', () => {
  const sm = read('ui.css').match(/\.cu-btn--sm\s*\{([^}]*)\}/)[1]
  expect(parseFloat(sm.match(/min-height:\s*([\d.]+)rem/)[1]) * 16).toBeGreaterThanOrEqual(24)
})

// WCAG 2.4.1: a link to skip to the content, first in the page, hidden until it takes the focus.
test('the skip link stays off screen until it is focused', () => {
  const css = read('ui.css')
  expect(css).toMatch(/\.cu-skip\s*\{[^}]*position:\s*absolute/)
  expect(css).toMatch(/\.cu-skip:focus(-visible)?\s*\{[^}]*(top|transform)/)
  expect(css).toMatch(/main\[tabindex="-1"\]:focus\s*\{/)    // and the main it lands on takes the focus quietly
})

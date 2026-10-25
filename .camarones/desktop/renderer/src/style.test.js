import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

// The app's own CSS takes every colour from the theme and keeps the focus ring of the shared kit (ui/src/ui.css).
const css = readFileSync(new URL('./app.css', import.meta.url), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '')
const rule = (sel) => css.match(new RegExp(`${sel.replace(/[.>]/g, (c) => '\\' + c)}\\s*\\{([^}]*)\\}`))[1]
const px = (body, prop) => parseFloat((body.match(new RegExp(`(?:^|[\\s;])${prop}:\\s*([\\d.]+)rem`)) || [0, 0])[1]) * 16

test('no raw colours', () => {
  expect(css.match(/#[0-9a-f]{3,8}\b|rgba?\(\s*\d/gi) ?? []).toEqual([])
})

test('nothing hides the focus', () => {
  expect(css).not.toMatch(/outline:\s*(none|0)\b/)
})

// WCAG 2.5.8: the sidebar links, the projects of the rail, the folds and the labelled checkboxes are 24 px or more.
test.each([['.dk-nav', 'min-height'], ['.dk-proj', 'height'], ['.dk-fold > summary', 'min-height'], ['.dk-check', 'min-height']])(
  '%s is a 24 px target', (sel, prop) => {
    expect(px(rule(sel), prop)).toBeGreaterThanOrEqual(24)
  })

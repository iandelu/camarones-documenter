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

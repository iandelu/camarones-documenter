import { expect, test } from 'vitest'
import { holes, place, tourAction, tourIds, TOURS } from './tour.js'
import { S } from './i18n.js'

test('a tour of the whole app and one per section, each with something to show', () => {
  expect(tourIds()).toEqual(['app', 'summary', 'board', 'plan', 'interviews', 'team', 'quality', 'libs', 'docs', 'machine'])
  expect(TOURS.app.length).toBeGreaterThanOrEqual(14)
  for (const id of tourIds()) expect(TOURS[id].length, id).toBeGreaterThanOrEqual(3)
  for (const id of tourIds().filter((x) => x !== 'app')) expect(TOURS[id].every((s) => s.section === id), id).toBe(true)
})

test('every step has its title and text in both languages', () => {
  for (const id of tourIds()) TOURS[id].forEach((_, i) => {
    for (const lang of ['es', 'en']) {
      expect(S[lang][`tour.${id}.${i + 1}.t`], `${lang} ${id} ${i + 1}`).toBeTruthy()
      expect(S[lang][`tour.${id}.${i + 1}.b`], `${lang} ${id} ${i + 1}`).toBeTruthy()
    }
  })
})

const VIEW = { w: 800, h: 600 }
const BUBBLE = { w: 300, h: 150 }
const inside = (p, b = BUBBLE, v = VIEW) => p.left >= 8 && p.top >= 8 && p.left + b.w <= v.w - 8 && p.top + b.h <= v.h - 8

test('the bubble goes below the target when it fits, inside the window', () => {
  const p = place({ top: 100, left: 50, width: 120, height: 40 }, BUBBLE, VIEW)
  expect(p).toEqual({ top: 152, left: 50, side: 'below' })
})

test('a target at the bottom right gets its bubble above it, still inside', () => {
  const p = place({ top: 540, left: 700, width: 90, height: 40 }, BUBBLE, VIEW)
  expect(p.side).toBe('above')
  expect(inside(p)).toBe(true)
})

test('a tall target with no room above or below gets the bubble at a side', () => {
  const p = place({ top: 20, left: 20, width: 200, height: 560 }, BUBBLE, VIEW)
  expect(p.side).toBe('right')
  expect(inside(p)).toBe(true)
})

test('no target, or a window smaller than the bubble: centred, never off the top left', () => {
  expect(place(null, BUBBLE, VIEW)).toEqual({ top: 225, left: 250, side: 'center' })
  const tiny = place({ top: 10, left: 10, width: 50, height: 20 }, { w: 320, h: 180 }, { w: 300, h: 200 })
  expect(tiny.left).toBeGreaterThanOrEqual(8)
  expect(tiny.top).toBeGreaterThanOrEqual(8)
})

test('the dim is four bands around the padded target', () => {
  const r = { top: 100, left: 200, width: 100, height: 50 }
  const bands = holes(r, VIEW, 6)
  expect(bands).toHaveLength(4)
  const area = bands.reduce((a, b) => a + b.width * b.height, 0)
  expect(area).toBe(VIEW.w * VIEW.h - (100 + 12) * (50 + 12))
  expect(bands.every((b) => b.width >= 0 && b.height >= 0)).toBe(true)
})

test('on the bubble, arrows and Enter move and Escape closes', () => {
  const on = { onBubble: true }
  expect(['ArrowRight', 'Enter', 'ArrowLeft', 'Escape', 'a'].map((k) => tourAction(k, on))).toEqual(['next', 'next', 'back', 'close', null])
})

test('a focused button in the bubble presses itself with Enter; arrows still move the tour', () => {
  const inside = { inBubble: true }
  expect(tourAction('Enter', inside)).toBeNull()
  expect(tourAction('ArrowRight', inside)).toBe('next')
  expect(tourAction('Escape', inside)).toBe('close')
})

test('keys meant for the page stay with it: a field, a dialog such as the palette, the control in the hole', () => {
  for (const k of ['Enter', 'Escape', 'ArrowLeft', 'ArrowRight']) {
    expect(tourAction(k, { typing: true, onBubble: true }), k).toBeNull()
    expect(tourAction(k, {}), k).toBeNull()
  }
})

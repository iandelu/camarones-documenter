import { expect, test } from 'vitest'
import { lang, S, t } from './index.js'

test('every shared string exists in es and en', () => {
  expect(Object.keys(S.es).sort()).toEqual(Object.keys(S.en).sort())
  for (const l of ['es', 'en']) for (const [k, v] of Object.entries(S[l])) expect(v, `${l}.${k}`).toBeTruthy()
})

test('t takes an explicit language, falls back to English, then to the key', () => {
  expect(t('loading', 'es')).toBe('Cargando…')
  expect(t('loading', 'en')).toBe('Loading…')
  expect(t('loading', 'fr')).toBe('Loading…')
  expect(t('no-such-key', 'es')).toBe('no-such-key')
})

test('without a choice or a page, the language is English (the canonical docs)', () => {
  expect(lang()).toBe('en')
})

// The portal's own dictionary (React views) keeps the same rule until phase 1 moves it here.
test('the portal dictionary has the same keys in es and en', async () => {
  const { S: portal } = await import('../../portal/app/src/i18n.js')
  expect(Object.keys(portal.es).length).toBeGreaterThan(0)
  expect(Object.keys(portal.es).sort()).toEqual(Object.keys(portal.en).sort())
})

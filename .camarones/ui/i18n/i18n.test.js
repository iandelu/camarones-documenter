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

// The docs views' dictionary (moved from the plain scripts in 4.51): the same keys in es and en, and no emoji.
test('the docs views dictionary has the same keys in es and en, and draws no emoji', async () => {
  const { I18N } = await import('../../portal/app/src/i18n/portal.js')
  expect(Object.keys(I18N.es).sort()).toEqual(Object.keys(I18N.en).sort())
  for (const l of ['en', 'es']) for (const [k, v] of Object.entries(I18N[l]))
    expect(String(v).match(/\p{Extended_Pictographic}/u), `${l}.${k}: ${v}`).toBeNull()
})

// The portal's own dictionary (React views) keeps the same rule.
test('the portal dictionary has the same keys in es and en', async () => {
  const { S: portal } = await import('../../portal/app/src/i18n.js')
  expect(Object.keys(portal.es).length).toBeGreaterThan(0)
  expect(Object.keys(portal.es).sort()).toEqual(Object.keys(portal.en).sort())
})

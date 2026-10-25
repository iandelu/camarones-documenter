import { expect, test } from 'vitest'
import { S, setLang, t } from './i18n.js'

test('every string exists in es and en, and draws no emoji', () => {
  expect(Object.keys(S.en).sort()).toEqual(Object.keys(S.es).sort())
  for (const l of ['es', 'en']) for (const [k, v] of Object.entries(S[l]))
    expect(v.match(/\p{Extended_Pictographic}/u), `${l}.${k}`).toBeNull()
})

test('the language falls back to Spanish and fills placeholders', () => {
  setLang('en')
  expect(t('hub.opening', { name: 'api' })).toBe('Opening api…')
  setLang('fr')
  expect(t('nav.summary')).toBe('Resumen')
  expect(t('nope')).toBe('nope')
})

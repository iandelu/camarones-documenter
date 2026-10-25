import { expect, test } from 'vitest'
import { applyTheme } from './theme.js'

const fakeWindow = ({ pick = '', systemDark = false } = {}) => {
  const said = []
  const dataset = {}
  return {
    said, dataset,
    localStorage: { getItem: (k) => (k === 'cam-theme' ? pick : null) },
    matchMedia: () => ({ matches: systemDark }),
    document: { documentElement: { dataset } },
    camaronApp: { theme: (t) => said.push(t) },
  }
}

// The portal and the app share the window and its storage: the theme picked in the portal (cam-theme) holds here too,
// else the system's; the window controls drawn over the header are told which, so they match.
test('the theme picked in the portal wins over the system, and the window controls follow', () => {
  const w = fakeWindow({ pick: 'dark', systemDark: false })
  expect(applyTheme(w)).toBe('dark')
  expect(w.dataset.theme).toBe('dark')
  expect(w.said).toEqual(['dark'])
})

test('with nothing picked, the system decides and no theme is forced', () => {
  const w = fakeWindow({ systemDark: true })
  w.dataset.theme = 'light'                         // left over from an earlier pick
  expect(applyTheme(w)).toBe('dark')
  expect(w.dataset.theme).toBeUndefined()
  expect(w.said).toEqual(['dark'])
})

test('no storage (private mode) and no bridge (a browser) still work', () => {
  const w = { ...fakeWindow(), localStorage: { getItem: () => { throw new Error('denied') } }, camaronApp: undefined }
  expect(applyTheme(w)).toBe('light')
})

import { expect, test } from 'vitest'
import { splitElements } from './c4.js'

test('what still needs review stays open; what a person confirmed folds away', () => {
  const els = [
    { fqn: 'a', draft: true, confirmed: false },
    { fqn: 'b', draft: false, confirmed: true },
    { fqn: 'c', draft: false, confirmed: false },
    { fqn: 'd', draft: true, confirmed: true },
  ]
  const { pending, confirmed } = splitElements(els)
  expect(pending.map((e) => e.fqn)).toEqual(['a', 'c', 'd'])
  expect(confirmed.map((e) => e.fqn)).toEqual(['b'])
  expect(splitElements([])).toEqual({ pending: [], confirmed: [] })
})

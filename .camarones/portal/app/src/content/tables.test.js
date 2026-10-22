import { describe, expect, it } from 'vitest'
import { filterRows, sortRows } from './tables.js'

const rows = [['b', '10'], ['a', '9'], ['c', '100']]

describe('live tables', () => {
  it('sorts numbers as numbers and text as text, both ways', () => {
    expect(sortRows(rows, 1).map((r) => r[1])).toEqual(['9', '10', '100'])
    expect(sortRows(rows, 0, -1).map((r) => r[0])).toEqual(['c', 'b', 'a'])
  })

  it('keeps the original order for ties', () => {
    expect(sortRows([['x', '1'], ['y', '1']], 1).map((r) => r[0])).toEqual(['x', 'y'])
  })

  it('filters on every word, any column', () => {
    expect(filterRows([['GET', '/pets'], ['POST', '/pets'], ['GET', '/owners']], 'get pets')).toEqual([['GET', '/pets']])
    expect(filterRows(rows, '  ')).toBe(rows)
  })
})

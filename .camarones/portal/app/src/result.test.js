import { expect, test } from 'vitest'
import { severities, shape } from './result.js'

test('a list of rows becomes a table with the columns they have', () => {
  const s = shape([{ id: 'refund', q: 'How?', 'x-confirmed': true }, { id: 'login', q: 'Where?', extra: [1, 2] }])
  expect(s.kind).toBe('table')
  expect(s.cols).toEqual(['id', 'q', 'x-confirmed', 'extra'])
  expect(s.rows[1]).toEqual(['login', 'Where?', null, '2 items'])
})

test('an object becomes label / value pairs, nested ones summarised', () => {
  const s = shape({ score: 0.8, judge: null, questions: [{}, {}, {}], with: { tokens: 10 } })
  expect(s).toEqual({ kind: 'pairs', rows: [['score', 0.8], ['judge', null], ['questions', '3 items'], ['with', 'tokens: 10']] })
})

test('anything else is text; empty lists say so', () => {
  expect(shape('hi')).toEqual({ kind: 'text', text: 'hi' })
  expect(shape([])).toEqual({ kind: 'empty' })
  expect(shape(null)).toEqual({ kind: 'empty' })
})

test('vulnerabilities counted by severity, worst first', () => {
  const libs = [{ name: 'a', vulns: [{ severity: 'high' }, { severity: 'low' }] }, { name: 'b', vulns: [{ severity: 'critical' }] }, { name: 'c' }]
  expect(severities(libs)).toEqual([['critical', 1], ['high', 1], ['low', 1]])
  expect(severities([])).toEqual([])
})

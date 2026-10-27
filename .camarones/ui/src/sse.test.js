import { expect, test } from 'vitest'
import { parseSSE } from './sse.js'

test('server-sent events are read in pieces, with the last id seen', () => {
  let r = parseSSE('id: 1\ndata: {"type":"line","text":"a"}\n\nid: 2\ndata: {"type":"li')
  expect(r.events).toEqual([{ type: 'line', text: 'a' }])
  expect(r.id).toBe('1')
  r = parseSSE(r.rest + 'ne","text":"b"}\n\n: keep-alive\n\n')
  expect(r.events).toEqual([{ type: 'line', text: 'b' }])
  expect(r.id).toBe('2')
  expect(r.rest).toBe('')
})

test('a piece with only a keep-alive has no id', () => {
  expect(parseSSE(': keep-alive\n\n')).toEqual({ events: [], rest: '', id: null })
})

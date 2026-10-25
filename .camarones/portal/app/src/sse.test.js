import { expect, test } from 'vitest'

test('server-sent events are read from a stream in pieces', async () => {
  const { parseSSE } = await import('./sse.js')
  let r = parseSSE('id: 1\ndata: {"type":"line","text":"a"}\n\nid: 2\ndata: {"type":"li')
  expect(r.events).toEqual([{ type: 'line', text: 'a' }])
  r = parseSSE(r.rest + 'ne","text":"b"}\n\n: keep-alive\n\n')
  expect(r.events).toEqual([{ type: 'line', text: 'b' }])
  expect(r.rest).toBe('')
})

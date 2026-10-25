import { expect, test } from 'vitest'
import { follow } from './cmd.js'

// a server whose job prints two lines, then a third, then ends
function fakeServer() {
  const steps = [
    { status: 'running', log: ['one', 'two'], lines: 2 },
    { status: 'running', log: ['three'], lines: 3 },
    { status: 'done', log: [], lines: 3, rc: 0, result: { ok: true } },
  ]
  const asked = []
  return { asked, get: async (path) => { asked.push(path); return steps.shift() } }
}

test('a job is followed to its end: its lines as they come, then its status, exit code and result', async () => {
  const srv = fakeServer()
  const lines = []
  const end = await follow(srv, { id: '7' }, { onLine: (l) => lines.push(l), sleep: async () => {} })
  expect(lines).toEqual(['one', 'two', 'three'])
  expect(srv.asked).toEqual(['jobs/7?since=0', 'jobs/7?since=2', 'jobs/7?since=3'])
  expect(end).toMatchObject({ status: 'done', rc: 0, result: { ok: true } })
})

test('given up, it stops asking', async () => {
  const srv = fakeServer()
  let gone = false
  const end = await follow(srv, { id: '7' }, { sleep: async () => { gone = true }, gone: () => gone })
  expect(end).toBeNull()
  expect(srv.asked).toHaveLength(1)
})

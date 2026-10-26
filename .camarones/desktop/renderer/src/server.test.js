import { expect, test } from 'vitest'
import { server } from './server.js'

const fake = (status, body) => {
  const calls = []
  const fetcher = async (url, init) => { calls.push({ url, init }); return { ok: status < 400, status, json: async () => body } }
  return { calls, fetcher }
}

test('a read goes one folder up, with the app token', async () => {
  const f = fake(200, { project: 'bench' })
  expect(await server('tok', f.fetcher).get('tree')).toEqual({ project: 'bench' })
  expect(f.calls[0].url).toBe('../api/tree')
  expect(f.calls[0].init.headers['X-Camaron-Token']).toBe('tok')
})

test('a read can say how to answer it: the units in the language of the app', async () => {
  const f = fake(200, { units: [] })
  await server('tok', f.fetcher).get('pipeline', { lang: 'es' })
  expect(f.calls[0].url).toBe('../api/pipeline?lang=es')
})

test('a write also says it comes from the app page, as JSON', async () => {
  const f = fake(200, { launched: true })
  await server('tok', f.fetcher).post('app/agent', { unit: 'u1' })
  const { init } = f.calls[0]
  expect(init.method).toBe('POST')
  expect(init.headers).toMatchObject({ 'X-Camaron-Token': 'tok', 'X-Camarones': '1', 'Content-Type': 'application/json' })
  expect(JSON.parse(init.body)).toEqual({ unit: 'u1' })
})

test('an error carries the server message', async () => {
  const f = fake(400, { error: 'u1 is blocked' })
  await expect(server('tok', f.fetcher).post('app/agent', {})).rejects.toThrow('u1 is blocked')
})

// A refused move says why in data (the board's 409 lists the cards that block it): the error keeps the status and the body.
test('an error also carries the status and the response body', async () => {
  const f = fake(409, { error: 'blocked', blocked_by: ['WI-3'] })
  const err = await server('tok', f.fetcher).post('kanban/move', { id: 'WI-4' }).catch((e) => e)
  expect(err.message).toBe('blocked')
  expect(err.status).toBe(409)
  expect(err.data.blocked_by).toEqual(['WI-3'])
})

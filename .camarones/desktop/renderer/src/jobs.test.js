import { expect, test } from 'vitest'
import { ago, arrange, chip, jobsStore, RECENT, state } from './jobs.js'

const job = (id, status, started) => ({ id, status, started, label: `job ${id}` })

test('what runs, and the most recent first', () => {
  const list = [job('1', 'done', 10), job('2', 'running', 30), job('3', 'failed', 20)]
  const { running, recent } = arrange(list)
  expect(running.map((j) => j.id)).toEqual(['2'])
  expect(recent.map((j) => j.id)).toEqual(['2', '3', '1'])
  expect(arrange(Array.from({ length: 20 }, (_, i) => job(String(i), 'done', i))).recent).toHaveLength(RECENT)
  expect(arrange(null)).toEqual({ running: [], recent: [] })
})

test('each state has its chip and its word; a job a person stopped is stopped, not failed', () => {
  expect(['running', 'done', 'failed', 'odd'].map((s) => chip({ status: s }))).toEqual(['info', 'ok', 'bad', 'warn'])
  expect(chip({ status: 'failed', stopped: true })).toBe('warn')
  expect(['running', 'done', 'failed'].map((s) => state({ status: s }))).toEqual(['running', 'done', 'failed'])
  expect(state({ status: 'failed', stopped: true })).toBe('stopped')
})

test('how long ago, in words', () => {
  const t = (k, v) => `${k}${v ? ':' + v.n : ''}`
  expect(ago(1000, 1000 + 20, t)).toBe('ago.now')
  expect(ago(1000, 1000 + 5 * 60, t)).toBe('ago.min:5')
  expect(ago(1000, 1000 + 3 * 3600, t)).toBe('ago.h:3')
  expect(ago(1000, 1000 + 2 * 86400, t)).toBe('ago.d:2')
})

// fake timers: the store schedules its next look itself
function clock() {
  const queue = []
  return {
    queue,
    setTimeout: (fn, ms) => { queue.push({ fn, ms }); return queue.length },
    clearTimeout: (id) => { if (queue[id - 1]) queue[id - 1].fn = null },
    async next() { const t = queue.shift(); if (t?.fn) await t.fn(); return t?.ms },
  }
}

test('the store looks often while something runs, rarely otherwise, and tells its readers', async () => {
  let rows = [job('1', 'running', 1)]
  const timers = clock()
  const store = jobsStore(async () => rows, { busy: 1000, idle: 9000, timers })
  let told = 0
  store.subscribe(() => told++)
  await store.refresh()
  expect(store.get().running).toHaveLength(1)
  expect(timers.queue.at(-1).ms).toBe(1000)
  rows = [job('1', 'done', 1)]
  await timers.next()
  expect(store.get().running).toHaveLength(0)
  expect(timers.queue.at(-1).ms).toBe(9000)
  expect(told).toBe(2)
})

test('a failed look keeps the last list and says why', async () => {
  let fail = false
  const store = jobsStore(async () => { if (fail) throw new Error('down'); return [job('1', 'done', 1)] }, { timers: clock() })
  await store.refresh()
  fail = true
  await store.refresh()
  expect(store.get().recent).toHaveLength(1)
  expect(store.get().error).toBe('down')
})

test('stopped, it looks no more', async () => {
  const timers = clock()
  const store = jobsStore(async () => [], { timers })
  await store.refresh()
  store.stop()
  await timers.next()
  expect(timers.queue).toHaveLength(0)
})

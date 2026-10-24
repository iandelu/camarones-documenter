import { expect, test } from 'vitest'
import { fields, toArgs } from './cmdform.js'

const run = { name: 'run', json: false, confirm: null, args: [
  { dest: 'parallel', flag: '--parallel', kind: 'int', default: 2, choices: null, required: false, positional: false, many: false },
  { dest: 'include_interviews', flag: '--include-interviews', kind: 'bool', default: false, choices: null, required: false, positional: false, many: false },
  { dest: 'policy', flag: '--policy', kind: 'choice', default: 'on-conflict', choices: ['on-conflict', 'never'], required: false, positional: false, many: false },
  { dest: 'only', flag: '--only', kind: 'str', default: null, choices: null, required: false, positional: false, many: true },
] }
const wiki = { name: 'wiki', json: false, confirm: null, args: [
  { dest: 'repos', flag: null, kind: 'str', default: null, choices: null, required: true, positional: true, many: true },
  { dest: 'mode', flag: '--init', kind: 'const', const: 'init', default: '', choices: null, required: false, positional: false, many: false },
  { dest: 'mode', flag: '--update', kind: 'const', const: 'update', default: '', choices: null, required: false, positional: false, many: false },
] }
const uninstall = { name: 'uninstall', json: false, confirm: '--yes', args: [
  { dest: 'yes', flag: '--yes', kind: 'bool', default: false, choices: null, required: false, positional: false, many: false },
  { dest: 'dry_run', flag: '--dry-run', kind: 'bool', default: false, choices: null, required: false, positional: false, many: false },
  { dest: 'json', flag: '--json', kind: 'bool', default: false, choices: null, required: false, positional: false, many: false },
] }

test('one field per argument, with its widget; const flags sharing a dest become one choice', () => {
  expect(fields(run).map((f) => [f.dest, f.widget])).toEqual([
    ['parallel', 'number'], ['include_interviews', 'check'], ['policy', 'select'], ['only', 'list']])
  const w = fields(wiki)
  expect(w.map((f) => f.dest)).toEqual(['repos', 'mode'])
  expect(w[1]).toMatchObject({ widget: 'select', options: ['', 'init', 'update'], label: '--init | --update' })
  expect(w[0]).toMatchObject({ required: true, label: 'repos' })
})

test('--yes and --json are the app\'s business, never a field', () => {
  expect(fields(uninstall).map((f) => f.dest)).toEqual(['dry_run'])
})

test('form values become the args the server checks', () => {
  expect(toArgs(run, { parallel: '3', include_interviews: true, policy: 'on-conflict', only: 'a, b  c' }))
    .toEqual({ parallel: 3, include_interviews: true, policy: 'on-conflict', only: ['a', 'b', 'c'] })
  expect(toArgs(run, { parallel: '', only: '' })).toEqual({})
  expect(toArgs(wiki, { repos: 'api', mode: '' })).toEqual({ repos: ['api'] })
  expect(toArgs(wiki, { repos: 'api web', mode: 'update' })).toEqual({ repos: ['api', 'web'], mode: 'update' })
})

test('defaults fill the form', () => {
  expect(Object.fromEntries(fields(run).map((f) => [f.dest, f.initial])))
    .toEqual({ parallel: '2', include_interviews: false, policy: 'on-conflict', only: '' })
})

test('server-sent events are read from a stream in pieces', async () => {
  const { parseSSE } = await import('./sse.js')
  let r = parseSSE('id: 1\ndata: {"type":"line","text":"a"}\n\nid: 2\ndata: {"type":"li')
  expect(r.events).toEqual([{ type: 'line', text: 'a' }])
  r = parseSSE(r.rest + 'ne","text":"b"}\n\n: keep-alive\n\n')
  expect(r.events).toEqual([{ type: 'line', text: 'b' }])
  expect(r.rest).toBe('')
})

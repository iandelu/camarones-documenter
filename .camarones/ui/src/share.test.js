import { expect, test } from 'vitest'
import { fetchSay, shareOk, shareSay } from './share.js'

const REMOTE = 'https://gitlab-central.example.space/team/docs.git'
const fatal = "fatal: unable to access 'https://gitlab-central.example.space/team/docs.git/': Could not resolve host: gitlab-central.example.space"

test('a host that does not resolve says which one and to check the VPN, with git\'s line kept as the detail', () => {
  const r = { status: 'error', reason: 'network', host: 'gitlab-central.example.space', detail: fatal }
  expect(shareSay(r, REMOTE)).toEqual({ key: 'sy.err.network', vars: { host: 'gitlab-central.example.space', url: REMOTE },
    detail: fatal, token: '' })
})

test('credentials refused or missing point at saving a token for that host', () => {
  for (const reason of ['auth', 'no-token', 'denied']) {
    const say = shareSay({ status: 'error', reason, host: 'git.acme', detail: 'fatal: x' }, REMOTE)
    expect(say.key).toBe(`sy.err.${reason}`)
    expect(say.token).toBe('git.acme')
  }
  expect(shareSay({ status: 'error', reason: 'not-found', host: 'git.acme', detail: '' }, REMOTE).token).toBe('')
})

test('a reason without a host (a local path, an older server) names the remote instead', () => {
  expect(shareSay({ status: 'error', reason: 'network', detail: '' }, REMOTE).vars.host).toBe('gitlab-central.example.space')
  expect(shareSay({ status: 'error', reason: 'network', detail: '' }, 'git@git.acme:team/docs.git').vars.host).toBe('git.acme')
  expect(shareSay({ status: 'error', reason: 'network', detail: '' }, '/mnt/share/docs').vars.host).toBe('/mnt/share/docs')
})

test('any other result keeps its status sentence, git\'s words inside it as before', () => {
  expect(shareSay({ status: 'pushed', detail: 'main' }, REMOTE)).toEqual({ key: 'sy.pushed', vars: { detail: 'main' }, detail: '', token: '' })
  expect(shareSay({ status: 'error', reason: 'unknown', detail: 'fatal: odd' }, REMOTE).key).toBe('sy.error')
  expect(shareSay({ status: 'error', detail: 'detached HEAD' }, REMOTE).vars.detail).toBe('detached HEAD')
  expect(shareSay({ status: 'conflict', detail: 'origin/main' }, REMOTE).key).toBe('sy.conflict')
})

test('only pushed, up to date and nothing are a success', () => {
  expect(['pushed', 'up-to-date', 'nothing'].every((status) => shareOk({ status }))).toBe(true)
  expect(['error', 'blocked', 'conflict', 'no-remote'].some((status) => shareOk({ status }))).toBe(false)
  expect(shareOk(null)).toBe(false)
})

test('a failed check for news reads like a failed share; a good one, or none, says nothing', () => {
  const fetched = { ok: false, reason: 'network', host: 'gitlab-central.example.space', detail: fatal }
  expect(fetchSay(fetched, REMOTE)).toEqual(shareSay({ status: 'error', ...fetched }, REMOTE))
  expect(fetchSay({ ok: false, reason: 'network' }, REMOTE).vars.host).toBe('gitlab-central.example.space')
  expect(fetchSay({ ok: false, reason: 'unknown', detail: 'fatal: odd' }, REMOTE)).toEqual({ key: '', vars: {}, detail: 'fatal: odd', token: '' })
  expect(fetchSay({ ok: true, reason: '' }, REMOTE)).toBeNull()
  expect(fetchSay(null, REMOTE)).toBeNull()
})

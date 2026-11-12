import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { FetchLine, ShareLine } from './Sync.jsx'

const as = (l) => { globalThis.localStorage = { getItem: () => l } }
afterEach(() => { delete globalThis.localStorage })

const REMOTE = 'https://gitlab-central.example.space/team/docs.git'
const fatal = "fatal: unable to access 'https://gitlab-central.example.space/team/docs.git/': Could not resolve host: gitlab-central.example.space"
const line = (result) => renderToStaticMarkup(<ShareLine result={result} remote={REMOTE} />)

test('a share that cannot resolve the host says which one and to check the VPN, with git\'s line underneath', () => {
  as('es')
  const out = line({ status: 'error', reason: 'network', host: 'gitlab-central.example.space', detail: fatal })
  expect(out).toContain('No llego a gitlab-central.example.space: revisa la conexión, la VPN o el proxy.')
  expect(out).toContain('Could not resolve host')
  expect(out).not.toContain('ha respondido')
  as('en')
  expect(line({ status: 'error', reason: 'network', host: 'gitlab-central.example.space', detail: fatal }))
    .toContain('I can&#x27;t reach gitlab-central.example.space: check the connection, VPN or proxy.')
})

test('refused credentials send to the desktop app for a token; the portal saves none', () => {
  as('en')
  const out = line({ status: 'error', reason: 'auth', host: 'git.acme', detail: 'fatal: Authentication failed' })
  expect(out).toContain('git.acme rejected your credentials')
  expect(out).toContain('Save a token for git.acme in the desktop app (Machine › Tokens).')
})

test('a reason git did not explain, and a success, read as before', () => {
  as('en')
  expect(line({ status: 'error', reason: 'unknown', detail: 'fatal: odd' })).toContain('The team&#x27;s repo answered: fatal: odd')
  const ok = line({ status: 'pushed', detail: 'main' })
  expect(ok).toContain('class="ok"')
  expect(ok).toContain('Shared')
})

test('a failed check for news says why instead of a bare code', () => {
  as('en')
  const out = renderToStaticMarkup(<FetchLine fetched={{ ok: false, reason: 'network', host: 'gitlab-central.example.space', detail: fatal }} remote={REMOTE} />)
  expect(out).toContain('I can&#x27;t reach gitlab-central.example.space: check the connection, VPN or proxy.')
  expect(out).toContain('Could not resolve host')
  expect(out).not.toContain('I could not reach the team')
  expect(out).not.toMatch(/: network</)
  const odd = renderToStaticMarkup(<FetchLine fetched={{ ok: false, reason: 'unknown', detail: 'fatal: odd' }} remote={REMOTE} />)
  expect(odd).toContain('I could not reach the team&#x27;s repo:')
  expect(odd).toContain('fatal: odd')
  expect(renderToStaticMarkup(<FetchLine fetched={{ ok: true, reason: '' }} remote={REMOTE} />)).toBe('')
})

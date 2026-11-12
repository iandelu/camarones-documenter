import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { FetchNote, ShareResult } from './sections/Team.jsx'
import { setLang } from './i18n.js'

afterEach(() => setLang('es'))

const REMOTE = 'https://gitlab-central.example.space/team/docs.git'
const fatal = "fatal: unable to access 'https://gitlab-central.example.space/team/docs.git/': Could not resolve host: gitlab-central.example.space"
const share = (result) => renderToStaticMarkup(<ShareResult result={result} remote={REMOTE} />)

test('a share that cannot resolve the host says which one and to check the VPN, with git\'s line underneath', () => {
  const out = share({ status: 'error', reason: 'network', host: 'gitlab-central.example.space', detail: fatal })
  expect(out).toContain('No llego a gitlab-central.example.space: revisa la conexión, la VPN o el proxy.')
  expect(out).toContain('cu-aviso-detail')
  expect(out).toContain('Could not resolve host')
  expect(out).not.toContain('ha respondido')
  setLang('en')
  expect(share({ status: 'error', reason: 'network', host: 'gitlab-central.example.space', detail: fatal }))
    .toContain('I can&#x27;t reach gitlab-central.example.space: check the connection, VPN or proxy.')
})

test('refused credentials link to saving a token for that host in Machine', () => {
  const out = share({ status: 'error', reason: 'no-token', host: 'git.acme', detail: 'fatal: Authentication failed' })
  expect(out).toContain('git.acme pide iniciar sesión')
  expect(out).toContain('href="#/machine?host=git.acme"')
  expect(out).toContain('Guardar un token para git.acme')
  expect(share({ status: 'error', reason: 'network', host: 'git.acme', detail: '' })).not.toContain('#/machine')
})

test('a reason git did not explain, and a success, read as before', () => {
  expect(share({ status: 'error', reason: 'unknown', detail: 'fatal: odd' })).toContain('El repo del equipo ha respondido: fatal: odd')
  const ok = share({ status: 'pushed', detail: 'main' })
  expect(ok).toContain('role="status"')
  expect(ok).toContain('Compartido')
  expect(share(null)).toBe('')
})

test('a failed check for news says why; one that went well says nothing', () => {
  const out = renderToStaticMarkup(<FetchNote fetched={{ ok: false, reason: 'network', host: 'gitlab-central.example.space', detail: fatal }} remote={REMOTE} />)
  expect(out).toContain('No he podido mirar el repo del equipo')
  expect(out).toContain('revisa la conexión, la VPN o el proxy')
  expect(out).toContain('Could not resolve host')
  expect(out).not.toContain('>network<')
  expect(renderToStaticMarkup(<FetchNote fetched={{ ok: true, reason: '' }} remote={REMOTE} />)).toBe('')
})

import { expect, test } from 'vitest'
import { adoptSay, card, errorKey, JOIN0, joinOnce, joinStep, names } from './hub.js'
import { S, setLang, t } from './i18n.js'

// What `camaron projects --inspect --json` prints (lib/onboard.py inspect).
const found = (over = {}) => ({ case: 'empty', kind: 'greenfield', workspace: '/w/shop', docs_root: '/w/shop/cam-docs',
  name: 'shop', repos: [], siblings: [], warning: '', ...over })
const repo = (name) => ({ name, path: `/w/shop/${name}` })

// Every key the start screen can show exists in both languages (the i18n test only sees literal t('…') calls).
const known = (k) => expect(k in S.es && k in S.en, k).toBe(true)
const keysOf = (c) => [`hub.badge.${c.badge}`, c.titleKey, c.bodyKey, c.warningKey, c.warningKey && c.warningKey + 'Title',
  c.siblingsKey].filter(Boolean)

test('a folder of repos: existing code, its repos named, and Continue', () => {
  const c = card(found({ case: 'umbrella', kind: 'legacy', repos: [repo('api'), repo('web'), repo('infra')] }))
  expect(c).toMatchObject({ badge: 'existing', titleKey: 'hub.umbrellaN', titleVars: { n: 3 }, bodyKey: 'hub.umbrellaText',
    dest: '/w/shop/cam-docs', canContinue: true, askName: true })
  expect(c.lead.map((r) => r.name)).toEqual(['api', 'web', 'infra'])
  expect(c.warningKey).toBeUndefined()
  expect(c.action).toBeUndefined()
  expect(card(found({ case: 'umbrella', repos: [repo('api')] })).titleKey).toBe('hub.umbrella1')
  expect(card(found({ case: 'umbrella', repos: [] })).titleKey).toBe('hub.umbrella0')      // never "0 repos"
})

test('a repo with siblings: cam-docs goes beside it and the siblings are offered', () => {
  const c = card(found({ case: 'repo', kind: 'legacy', repos: [repo('api')], siblings: [repo('web'), repo('infra')] }))
  expect(c).toMatchObject({ badge: 'existing', titleKey: 'hub.repoTitle', titleVars: { name: 'api' }, bodyKey: 'hub.repoText',
    siblingsKey: 'hub.siblingsN', canContinue: true })
  expect(c.siblings.map((r) => r.name)).toEqual(['web', 'infra'])
  expect(card(found({ case: 'repo', repos: [repo('api')], siblings: [repo('web')] })).siblingsKey).toBe('hub.siblings1')
  expect(card(found({ case: 'repo', repos: [repo('api')] })).siblingsKey).toBeUndefined()
})

test('an empty folder is a new project', () => {
  expect(card(found())).toMatchObject({ badge: 'new', titleKey: 'hub.emptyTitle', bodyKey: 'hub.emptyText', canContinue: true,
    askName: true })
})

test('a project opens as it is, with no name to ask', () => {
  expect(card(found({ case: 'project', kind: 'legacy' }))).toMatchObject({ badge: 'documented', titleKey: 'hub.projectTitle',
    bodyKey: 'hub.projectText', canContinue: true, askName: false })
})

// I1: code without git does not continue; the card offers to initialise git, then inspects again.
test('code without git offers git init instead of Continue', () => {
  const c = card(found({ case: 'code', kind: 'legacy', warning: 'no-git' }))
  expect(c).toMatchObject({ badge: 'existing', titleKey: 'hub.codeTitle', canContinue: false, warningKey: 'hub.noGit',
    action: 'gitInit' })
})

// I2: the workspace would be home or a drive root: explained, and only "Change folder" is left.
test('home on top of a repo stops there, with no git init either', () => {
  const c = card(found({ case: 'repo', repos: [repo('dotfiles')], warning: 'home', workspace: '/home/me', docs_root: '/home/me/cam-docs' }))
  expect(c).toMatchObject({ canContinue: false, warningKey: 'hub.home', dest: '/home/me/cam-docs' })
  expect(c.action).toBeUndefined()
  const code = card(found({ case: 'code', warning: 'home' }))
  expect(code).toMatchObject({ canContinue: false, warningKey: 'hub.home' })
  expect(code.action).toBeUndefined()
})

test('every card names keys that exist', () => {
  const cases = [found(), found({ case: 'umbrella', repos: [repo('a'), repo('b')] }), found({ case: 'umbrella' }),
    found({ case: 'umbrella', repos: [repo('a')] }), found({ case: 'repo', repos: [repo('a')], siblings: [repo('b')] }),
    found({ case: 'repo', repos: [repo('a')], siblings: [repo('b'), repo('c')] }), found({ case: 'project' }),
    found({ case: 'code', warning: 'no-git' }), found({ case: 'repo', warning: 'home' }), found({ case: 'what' })]
  for (const f of cases) keysOf(card(f)).forEach(known)
})

test('errorKey words every refusal, in its place', () => {
  const codes = ['taken', 'home', 'no-git', 'folder', 'auth', 'denied', 'not-found', 'network', 'unknown', 'url', 'git-init', 'failed']
  for (const c of codes) { expect(errorKey(c), c).not.toBe('hub.failed'); known(errorKey(c)) }
  expect(errorKey('taken', { repo: true })).toBe('hub.takenParent')       // a repo's cam-docs goes in its parent folder
  expect(errorKey('taken', { join: true })).toBe('hub.joinTaken')
  expect(errorKey('ENOENT: something else')).toBe('hub.failed')          // free text from a failed open: generic
  known('hub.failed')
})

test('names lists a few and counts the rest, in the app\'s language', () => {
  expect(names([], t)).toBe('')
  expect(names([repo('api')], t)).toBe('api')
  expect(names([repo('api'), repo('web'), repo('infra')], t)).toBe('api, web y infra')
  expect(names(['a', 'b', 'c', 'd', 'e', 'f'].map(repo), t)).toBe('a, b, c, d y 2 más')
})

// The token is asked only when the host named itself; anything else drops it, and the folder is asked again.
test('the join token is dropped after any non-auth result', () => {
  const asked = { ...JOIN0, showToken: true, token: 's3cret', host: 'gitlab.com', dir: '/w/team' }
  for (const r of [{ ok: true }, { error: 'taken', detail: 'x', dir: '/w/team' }, { error: 'network', host: 'gitlab.com', dir: '/w/team' },
    { error: 'auth', host: '', dir: '/w/team' }, { cancelled: true }, { ok: false, error: 'spawn failed' }]) {
    const s = joinStep(asked, r)
    expect(s, JSON.stringify(r)).toMatchObject({ showToken: false, token: '', dir: null })
  }
  const s = joinStep({ ...JOIN0, token: '' }, { error: 'auth', host: 'gitlab.com', dir: '/w/team' })
  expect(s).toMatchObject({ showToken: true, token: '', host: 'gitlab.com', dir: '/w/team' })
  expect(s.say).toMatchObject({ key: 'hub.auth', vars: { host: 'gitlab.com' }, error: false })   // a request, not a failure
  const again = joinStep({ ...s, token: 'bad' }, { error: 'auth', host: 'gitlab.com', dir: '/w/team' })
  expect(again).toMatchObject({ showToken: true, token: '', dir: '/w/team' })
  expect(again.say).toMatchObject({ key: 'hub.authAgain', error: true })
})

test('a join result says what happened', () => {
  expect(joinStep(JOIN0, { ok: true }).say).toBeNull()
  expect(joinStep(JOIN0, { cancelled: true }).say).toBeNull()
  expect(joinStep(JOIN0, { error: 'auth', host: '' }).say).toMatchObject({ key: 'hub.authSsh', error: true })
  expect(joinStep(JOIN0, { error: 'taken', detail: 'd' }).say).toMatchObject({ key: 'hub.joinTaken', detail: 'd', error: true })
  expect(joinStep(JOIN0, { error: 'network', host: 'git.acme' }).say).toMatchObject({ key: 'hub.network', vars: { host: 'git.acme' } })
  expect(joinStep(JOIN0, { error: 'denied' }).say.vars.host).toBe(t('hub.server'))
  expect(joinStep(JOIN0, { error: 'failed', detail: 'exit 1' }).say).toMatchObject({ key: 'hub.joinFailed', detail: 'exit 1' })
  expect(joinStep(JOIN0, { ok: false, error: 'timeout' }).say).toMatchObject({ key: 'hub.openFailed', detail: 'timeout' })
})

test('an adopt result: a known refusal in words, anything else generic with its text', () => {
  const f = found({ case: 'repo', repos: [repo('api')] })
  expect(adoptSay(f, { ok: true })).toBeNull()
  expect(adoptSay(f, { error: 'taken', detail: 'd' })).toMatchObject({ key: 'hub.takenParent', detail: 'd', error: true })
  expect(adoptSay(found(), { error: 'taken', detail: 'd' }).key).toBe('hub.taken')
  expect(adoptSay(f, { error: 'home', detail: 'd' }).key).toBe('hub.home')
  expect(adoptSay(f, { error: 'no-git', detail: 'd' }).key).toBe('hub.noGit')
  expect(adoptSay(f, { ok: false, error: 'Python exited 2' })).toMatchObject({ key: 'hub.openFailed', detail: 'Python exited 2' })
  expect(adoptSay(f, { error: 'boom' })).toMatchObject({ key: 'hub.failed', detail: 'boom', error: true })
})

// A join that throws (the project window failed to load after a good token retry) or returns nothing still drops the
// token and the folder: nothing typed in the token field outlives a non-auth outcome.
test('a join that throws or returns nothing clears the token too', async () => {
  const asked = { ...JOIN0, showToken: true, token: 's3cret', host: 'gitlab.com', dir: '/w/team' }
  const thrown = joinStep(asked, new Error('loadURL failed'))
  expect(thrown).toMatchObject({ showToken: false, token: '', dir: null })
  expect(thrown.say).toMatchObject({ key: 'hub.failed', detail: 'loadURL failed', error: true })
  expect(joinStep(asked, undefined)).toMatchObject({ showToken: false, token: '', dir: null, say: null })
  const seen = []
  const rejects = { join: (...a) => { seen.push(a); return Promise.reject(new Error('gone')) } }
  const s = await joinOnce(rejects, asked, 'https://gitlab.com/t/cam-docs.git', 's3cret')
  expect(seen).toEqual([['https://gitlab.com/t/cam-docs.git', 's3cret', '/w/team']])
  expect(s).toMatchObject({ showToken: false, token: '', dir: null, say: { key: 'hub.failed', detail: 'gone' } })
  const odd = await joinOnce({ join: () => Promise.reject('nope') }, asked, 'u', 't')          // not an Error
  expect(odd).toMatchObject({ showToken: false, token: '', say: { key: 'hub.failed', detail: 'nope' } })
  const auth = await joinOnce({ join: async () => ({ error: 'auth', host: 'gitlab.com', dir: '/w/team' }) }, JOIN0, 'u', undefined)
  expect(auth).toMatchObject({ showToken: true, dir: '/w/team' })
})

test('a network failure with no host does not say "the server" as a name', () => {
  expect(joinStep(JOIN0, { error: 'network', host: '' }).say.key).toBe('hub.networkNoHost')
  expect(joinStep(JOIN0, { error: 'network', host: 'git.acme' }).say.key).toBe('hub.network')
  setLang('es')
  expect(t('hub.networkNoHost')).toMatch(/^No llego al servidor\./)
  setLang('en')
  expect(t('hub.networkNoHost')).toMatch(/^I can't reach the server\./)
  setLang('es')
})

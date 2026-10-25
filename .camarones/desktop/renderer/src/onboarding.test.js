import { expect, test } from 'vitest'
import { S } from './i18n.js'
import { STEP_KEYS, alreadyDone, canContinue, continueVariant, defaultPicks, errorKey, errorText, hostOf, manualHints, nextStep,
  prevStep, progressOf, repoBody, repoFromUrl, repoRows, reposChanged, setupChoice, stepIndex, urlName } from './onboarding.js'

const LEGACY = ['repos', 'tools', 'setup', 'stack', 'arch', 'intro']
const at = (step, steps = LEGACY) => ({ mode: 'new', kind: 'legacy', steps, step, done: false })

test('resumes at the saved step', () => {
  expect(stepIndex(at('stack'))).toBe(3)
  expect(stepIndex(at('name'))).toBe(0)            // a step this list does not show (the start screen's): the first
  expect(nextStep(at('stack'))).toBe('arch')
  expect(prevStep(at('stack'))).toBe('setup')
})

test('legacy needs a repo, greenfield does not', () => {
  const none = [{ name: 'api', checked: false }]
  expect(canContinue('repos', { kind: 'legacy', rows: none })).toEqual({ ok: false, reason: 'obNeedRepo' })
  expect(canContinue('repos', { kind: 'legacy', rows: [{ name: 'api', checked: true }] }).ok).toBe(true)
  expect(canContinue('repos', { kind: 'greenfield', rows: [] })).toEqual({ ok: true, reason: '' })
})

test('required tools block continue', () => {
  const rows = [{ id: 'git', kind: 't_required', ok: false, sys: true }, { id: 'docker', kind: 't_optional', ok: false, sys: true }]
  expect(canContinue('tools', { rows, picked: ['docker'] })).toEqual({ ok: false, reason: 'obNeedRequired' })
  expect(canContinue('tools', { rows, picked: ['git'] }).ok).toBe(true)
  expect(canContinue('tools', { rows: [{ ...rows[0], ok: true }], picked: [] }).ok).toBe(true)
  // after setup: a required tool the process still cannot see (a new PATH) blocks too, until the app is reopened
  expect(canContinue('setup', { result: { ok: true }, requiredOk: false })).toEqual({ ok: false, reason: 'obNeedRequired' })
})

test('setup must succeed', () => {
  expect(canContinue('setup', {})).toEqual({ ok: false, reason: 'obSetupFailed' })
  expect(canContinue('setup', { result: { ok: false, failed: ['java'] } })).toEqual({ ok: false, reason: 'obSetupFailed' })
  expect(canContinue('setup', { result: { ok: true, missing: [] }, requiredOk: true }).ok).toBe(true)
  expect(canContinue('stack', {}).ok).toBe(true)
})

test('the C4 draft is saved or skipped, never left behind by Continue', () => {
  expect(canContinue('arch', {})).toEqual({ ok: false, reason: 'obArchChoose' })
  expect(canContinue('arch', { saved: true }).ok).toBe(true)
})

test('join has three steps', () => {
  const join = { mode: 'join', kind: 'legacy', steps: ['tools', 'setup', 'intro'], step: 'tools', done: false }
  expect(join.steps.map((s) => STEP_KEYS[s])).toEqual(['obStepTools', 'obStepSetup', 'obStepIntro'])
  expect(nextStep(join)).toBe('setup')
  expect(nextStep({ ...join, step: 'setup' })).toBe('intro')
})

test('back from the first shown step is null', () => {
  expect(prevStep(at('repos'))).toBeNull()
  expect(prevStep({ steps: ['tools', 'setup', 'intro'], step: 'tools' })).toBeNull()
})

test('after intro comes done', () => {
  expect(nextStep(at('intro'))).toBe('done')
  expect(nextStep({ steps: ['repos', 'tools', 'setup', 'intro'], step: 'intro' })).toBe('done')
})

test('repo rows: the workspace ticked, the rest found in the folder unticked, no duplicates', () => {
  const st = { repos: [{ name: 'api', url: '', branch: 'main', kind: 'service', stack: 'java' }],
    found: [{ name: 'api', url: '', branch: 'main', kind: 'service' }, { name: 'web', url: 'u', branch: 'dev', kind: 'frontend' }] }
  expect(repoRows(st)).toEqual([
    { name: 'api', url: '', branch: 'main', kind: 'service', checked: true },
    { name: 'web', url: 'u', branch: 'dev', kind: 'frontend', checked: false }])
})

test('a code repo added by URL, with its name and branch (as add_url does)', () => {
  expect(repoFromUrl('https://gitlab.com/shop/payments.git')).toEqual(
    { name: 'payments', url: 'https://gitlab.com/shop/payments.git', branch: 'main', kind: 'service', checked: true, added: true })
  expect(repoFromUrl(' https://gitlab.com/shop/payments.git ', ' pay ', ' develop ')).toMatchObject(
    { name: 'pay', branch: 'develop', url: 'https://gitlab.com/shop/payments.git' })
  expect(urlName('https://gitlab.com/shop/payments.git/')).toBe('payments')
  expect(repoFromUrl('git@github.com:shop/web')).toMatchObject({ name: 'web' })
  expect(repoFromUrl('  ')).toBeNull()
  expect(repoFromUrl('-x')).toBeNull()                      // git would read it as an option
  // what the repos step saves: the ticked rows, only the workspace's keys
  expect(repoBody([{ ...repoFromUrl('https://h/a/x.git', '', 'dev') }, { name: 'y', url: '', branch: 'main', kind: 'service', checked: false }]))
    .toEqual([{ name: 'x', url: 'https://h/a/x.git', branch: 'dev', kind: 'service' }])
  expect(hostOf('https://gitlab.example.com/a/b.git')).toBe('gitlab.example.com')
  expect(hostOf('git@github.com:a/b.git')).toBe('github.com')
  expect(hostOf('')).toBe('')
})

test('tools: recommended picked by default, required ones always; setup gets system tools and components', () => {
  const rows = [
    { id: 'git', kind: 't_required', ok: false, rec: true, sys: true },
    { id: 'java', kind: 't_optional', ok: false, rec: true, sys: true },
    { id: 'codex', kind: 't_optional', ok: false, rec: false, sys: true },
    { id: 'node', kind: 't_required', ok: true, rec: true, sys: true },
    { id: 'graphify', kind: 't_kit', ok: true, rec: true, sys: false },
    { id: 'likec4', kind: 't_kit', ok: false, rec: true, sys: false },
    { id: 'openwiki', kind: 't_kit', ok: false, rec: true, sys: false },
  ]
  const picked = defaultPicks(rows)
  expect(picked.sort()).toEqual(['git', 'java', 'likec4', 'openwiki'])
  expect(setupChoice(rows, ['git', 'likec4'])).toEqual({ system: ['git'], components: ['graphify', 'likec4'] })
})

test('a tool that failed to install comes with how to install it by hand', () => {
  const rows = [{ id: 'java', label: 'Java 21 (brew install openjdk@21)' }, { id: 'node', label: 'Node.js 22' }]
  expect(manualHints(rows, ['java', 'gone'])).toEqual([{ id: 'java', hint: 'Java 21 (brew install openjdk@21)' }, { id: 'gone', hint: '' }])
})

test('setup progress from the [n/total] lines', () => {
  expect(progressOf([])).toEqual({ n: 0, total: 0, pct: 0, current: '' })
  expect(progressOf(['· cloning web…', '[1/4] ✔ node 22.11', 'cloning api…'])).toEqual(
    { n: 1, total: 4, pct: 25, current: 'cloning api…' })
  expect(progressOf(['[4/4] ✔ plan']).pct).toBe(100)
})

test('server codes become i18n keys in both languages', () => {
  for (const code of ['repos', 'name', 'url', 'duplicate', 'busy', 'done', 'step', 'draft'])
    expect(errorKey(code)).toMatch(/^ob/)
  expect(errorKey('something else')).toBe('')
  const ob = (l) => Object.keys(S[l]).filter((k) => /^ob/.test(k)).sort()
  expect(ob('es')).toEqual(ob('en'))
  for (const k of [...Object.values(STEP_KEYS), 'obNeedRepo', 'obNeedRequired', 'obSetupFailed', 'obArchChoose',
    ...['repos', 'name', 'url', 'duplicate', 'busy', 'done', 'step', 'draft'].map(errorKey)])
    expect(S.es[k] && S.en[k]).toBeTruthy()
})

// A rejection said to the person: a known code by its sentence, a server that cannot be reached by its own sentence
// (fetch rejects before any HTTP answer), anything else as the server said it.
test('errors: known codes, an unreachable server, the rest as they came', () => {
  expect(errorText(new Error('busy'))).toEqual({ key: 'obErrBusy', detail: '' })
  expect(errorText(new TypeError('Failed to fetch'))).toEqual({ key: 'obErrNetwork', detail: '' })
  expect(errorText({ message: 'Failed to fetch' })).toEqual({ key: 'obErrNetwork', detail: '' })   // useJob keeps the message only
  expect(errorText(new Error('NetworkError when attempting to fetch resource.')).key).toBe('obErrNetwork')
  expect(errorText(new Error('app/onboard/step: 500'))).toEqual({ key: 'obErrServer', detail: 'app/onboard/step: 500' })
  expect(S.es.obErrNetwork).toBe('No llego al servidor del proyecto.')
  expect(S.en.obErrNetwork).toBe("I can't reach the project's server.")
})

// The CLI may close the first run while the window shows Ready: the server's `done` refusal means it is closed.
test('closing a first run that is closed already counts as closed', () => {
  expect(alreadyDone(new Error('done'))).toBe(true)
  expect(alreadyDone(new Error('step'))).toBe(false)
  expect(alreadyDone(new TypeError('Failed to fetch'))).toBe(false)
})

// A changed repo list makes a finished setup (clones) and scan stale; the same list does not.
test('the repos step knows when the list changed', () => {
  const saved = [{ name: 'api', url: '', branch: 'main', kind: 'service', stack: 'java' }]
  expect(reposChanged(saved, [{ name: 'api', url: '', branch: 'main', kind: 'service' }])).toBe(false)
  expect(reposChanged(saved, [{ name: 'api', url: '', branch: 'dev', kind: 'service' }])).toBe(true)
  expect(reposChanged(saved, [...repoBody([{ name: 'api', url: '', branch: 'main', kind: 'service', checked: true }]),
    { name: 'pay', url: 'https://h/pay.git', branch: 'main', kind: 'service' }])).toBe(true)
  expect(reposChanged([], [])).toBe(false)
})

// One primary button per screen: on the arch step the draft's Save is the primary until it is saved or skipped.
test('Continue is the primary action, except on an unsaved arch step', () => {
  expect(continueVariant('arch', { saved: false })).toBe('secondary')
  expect(continueVariant('arch', { saved: true })).toBe('primary')
  expect(continueVariant('repos', {})).toBe('primary')
  expect(continueVariant('setup', {})).toBe('primary')
})

// Spec addendum §4: the arch step has no agent picker when the agent is gone, so the warning never asks to pick one.
test('the no-agent warning promises nothing disabled', () => {
  expect(S.es.obAgentMissing).toBe('No encuentro ese agente: el borrador está guardado; mejóralo luego desde el Plan.')
  expect(S.en.obAgentMissing).toBe("I can't find that agent: the draft is saved; improve it later from the Plan.")
  expect(S.es.obAgentMissing).not.toMatch(/elige/i)
  expect(S.en.obAgentMissing).not.toMatch(/pick/i)
})

// A programming TypeError is not "no network": it shows its own message; only the engines' fetch messages mean that.
test('a TypeError that is not a failed fetch shows its message', () => {
  expect(errorText(new TypeError("Cannot read properties of undefined (reading 'rows')")))
    .toEqual({ key: 'obErrServer', detail: "Cannot read properties of undefined (reading 'rows')" })
})

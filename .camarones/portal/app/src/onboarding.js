// The first-run wizard of the desktop app (#/start) as data: where it stands, what comes next, whether a step may be
// left and why not, and the shapes the server's onboarding endpoints take (lib/onboard.py, lib/serve.py). Pure: no
// React, no fetch. `state` is GET app/onboard/state: {mode, kind, steps (without `name`), step, done, repos, found}.

export const STEP_KEYS = { repos: 'obStepRepos', tools: 'obStepTools', setup: 'obStepSetup', stack: 'obStepStack',
  arch: 'obStepArch', intro: 'obStepIntro' }

// The saved step's place in this mode's list; a step the list does not show (`name`, done on the start screen) is the first.
export function stepIndex(state) {
  const i = state.steps.indexOf(state.step)
  return i < 0 ? 0 : i
}

export function nextStep(state) {
  const i = stepIndex(state)
  return i + 1 < state.steps.length ? state.steps[i + 1] : 'done'
}

export function prevStep(state) {
  const i = stepIndex(state)
  return i > 0 ? state.steps[i - 1] : null
}

const missingRequired = (rows) => (rows || []).filter((r) => r.kind === 't_required' && !r.ok)

// Whether Continue is allowed on `stepId`, and the i18n key that says why not. `data` per step: repos {kind, rows},
// tools {rows, picked}, setup {result, requiredOk}, arch {saved}; stack and intro never block.
export function canContinue(stepId, data = {}) {
  const no = (reason) => ({ ok: false, reason })
  if (stepId === 'repos' && data.kind !== 'greenfield' && !(data.rows || []).some((r) => r.checked)) return no('obNeedRepo')
  if (stepId === 'tools') {
    const picked = new Set(data.picked || [])
    if (missingRequired(data.rows).some((r) => !picked.has(r.id))) return no('obNeedRequired')
  }
  if (stepId === 'setup') {
    if (!data.result?.ok) return no('obSetupFailed')
    if (data.requiredOk === false) return no('obNeedRequired')       // installed, but this process cannot see it yet
  }
  if (stepId === 'arch' && !data.saved) return no('obArchChoose')      // Save draft, Save and improve, or Skip decide
  return { ok: true, reason: '' }
}

const REPO_KEYS = ['name', 'url', 'branch', 'kind']
const pick = (r) => Object.fromEntries(REPO_KEYS.map((k) => [k, r[k] ?? '']))

// The repos step's rows: what workspace.yaml lists (ticked), then the repos found in the folder that it does not.
export function repoRows(state) {
  const listed = (state.repos || []).map((r) => ({ ...pick(r), checked: true }))
  const names = new Set(listed.map((r) => r.name))
  return [...listed, ...(state.found || []).filter((r) => !names.has(r.name)).map((r) => ({ ...pick(r), checked: false }))]
}

// The name a repo gets from its URL: the last segment, without `.git`.
export const urlName = (url) => (url || '').trim().replace(/[/\\]+$/, '').split(/[/:\\]/).pop().replace(/\.git$/i, '')

// A code repo added by its URL, name and branch (as `add_url` does): the name defaults to the URL's, the branch to
// main, the kind is service. `added` marks it as the person's, so its branch stays editable.
export function repoFromUrl(raw, name = '', branch = '') {
  const url = (raw || '').trim()
  if (!url || url.startsWith('-')) return null
  const n = (name || '').trim() || urlName(url)
  return n ? { name: n, url, branch: (branch || '').trim() || 'main', kind: 'service', checked: true, added: true } : null
}

// POST app/onboard/repos's list: the ticked rows with the workspace's keys only.
export const repoBody = (rows) => rows.filter((r) => r.checked).map(pick)

// The tools setup could not install, each with its row's hint (how to get it by hand, as the CLI's "manual" says).
export const manualHints = (rows, failed) =>
  (failed || []).map((id) => ({ id, hint: (rows || []).find((r) => r.id === id)?.label || '' }))

// The host of a clone URL (https://host/… or git@host:…), for the token form when a clone failed.
export function hostOf(url) {
  const u = (url || '').trim()
  const ssh = u.match(/^[\w.-]+@([^:/]+):/)
  if (ssh) return ssh[1]
  try { return new URL(u).hostname } catch { return '' }
}

// What the tools step ticks at first, as "install recommended" does (onboard.install_choice "all"): the missing
// recommended system tools (one agent CLI is enough), every required one, and the kit tools not installed yet.
export function defaultPicks(rows) {
  const haveAgent = rows.some((r) => ['claude', 'codex'].includes(r.id) && r.ok)
  return rows.filter((r) => !r.ok && (r.kind === 't_required' || (r.rec && !(r.sys && haveAgent && ['claude', 'codex'].includes(r.id)))))
    .map((r) => r.id)
}

// POST app/onboard/setup's body: the picked system tools to install and the kit components to keep (the installed
// ones and the picked ones; setup saves this list as the machine's components).
export function setupChoice(rows, picked) {
  const p = new Set(picked)
  return { system: rows.filter((r) => r.sys && !r.ok && p.has(r.id)).map((r) => r.id),
    components: rows.filter((r) => !r.sys && (r.ok || p.has(r.id))).map((r) => r.id) }
}

// The setup job's bar: its last `[n/total]` line, and the newest line without the counter as "what it is doing".
export function progress(lines) {
  let n = 0
  let total = 0
  for (const l of lines) {
    const m = l.match(/^\[(\d+)\/(\d+)\]/)
    if (m) { n = +m[1]; total = +m[2] }
  }
  const current = (lines.at(-1) || '').replace(/^\[\d+\/\d+\]\s*/, '')
  return { n, total, pct: total ? Math.min(100, Math.round((n / total) * 100)) : 0, current }
}

// A server error code (400/409 `{"error": code}`) → the i18n key that says it to the person; '' for anything else.
const ERRORS = { repos: 'obErrRepos', name: 'obErrName', url: 'obErrUrl', duplicate: 'obErrDuplicate', busy: 'obErrBusy',
  done: 'obErrDone', step: 'obErrStep', draft: 'obErrDraft' }
export const errorKey = (code) => ERRORS[code] || ''

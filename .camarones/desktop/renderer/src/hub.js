// The start screen's decisions, pure: what card a picked folder gets (lib/onboard.py inspect), how a refusal is worded,
// and the join form's token state. Hub.jsx draws them; window.camaronHub (preload.cjs) does the work.
import { t as text } from './i18n.js'

// The badge's chip state (@camaron/ui Chip): existing code in the accent, a new project in success, a project in warning.
export const BADGE = { existing: 'info', new: 'ok', documented: 'warn' }

const CASES = {
  umbrella: (f) => ({ badge: 'existing', titleKey: ['hub.umbrella0', 'hub.umbrella1'][f.repos.length] || 'hub.umbrellaN',
    titleVars: { n: f.repos.length }, bodyKey: 'hub.umbrellaText', lead: f.repos }),
  repo: (f) => ({ badge: 'existing', titleKey: 'hub.repoTitle', titleVars: { name: f.repos[0]?.name || f.name },
    bodyKey: 'hub.repoText', ...(f.siblings.length ? { siblings: f.siblings,
      siblingsKey: f.siblings.length === 1 ? 'hub.siblings1' : 'hub.siblingsN' } : {}) }),
  code: () => ({ badge: 'existing', titleKey: 'hub.codeTitle', bodyKey: 'hub.codeText', canContinue: false,
    warningKey: 'hub.noGit', action: 'gitInit' }),
  empty: () => ({ badge: 'new', titleKey: 'hub.emptyTitle', bodyKey: 'hub.emptyText' }),
  project: () => ({ badge: 'documented', titleKey: 'hub.projectTitle', bodyKey: 'hub.projectText', askName: false }),
}

// What the picked folder is, as a card: badge, title, sentence, where cam-docs goes, and whether Continue is offered.
// An unknown case reads as an empty folder. Home (or a drive root) as the workspace wins over everything: only
// "Change folder" is left. A warning's card also shows `<warningKey>Title` as its heading.
export function card(found) {
  const f = { repos: [], siblings: [], ...found }
  const c = { canContinue: true, askName: true, ...(CASES[f.case] || CASES.empty)(f), dest: f.docs_root }
  if (f.warning === 'home') {
    delete c.action
    return { ...c, canContinue: false, warningKey: 'hub.home' }
  }
  return c
}

// "api, web and infra", "a, b, c, d and 2 more": repo rows or names, in the app's language.
export function names(rows, t = text, max = 4) {
  const n = rows.map((r) => (typeof r === 'string' ? r : r.name))
  if (!n.length) return ''
  if (n.length > max) return `${n.slice(0, max).join(', ')} ${t('hub.more', { n: n.length - max })}`
  return n.length === 1 ? n[0] : `${n.slice(0, -1).join(', ')}${t('hub.and')}${n[n.length - 1]}`
}

const ERRORS = { home: 'hub.home', 'no-git': 'hub.noGit', folder: 'hub.folderBad', auth: 'hub.authSsh', denied: 'hub.denied',
  'not-found': 'hub.notFound', network: 'hub.network', unknown: 'hub.unknown', url: 'hub.badUrl', 'git-init': 'hub.gitInitFailed',
  failed: 'hub.joinFailed' }

// A refusal's sentence. `taken` names the folder whose cam-docs is in the way: the team's for a join, the parent
// folder for a single repo. Anything else (a failed open returns free text) is the generic one.
export function errorKey(code, { join = false, repo = false } = {}) {
  if (code === 'taken') return join ? 'hub.joinTaken' : repo ? 'hub.takenParent' : 'hub.taken'
  return Object.hasOwn(ERRORS, code) ? ERRORS[code] : 'hub.failed'
}

// What the found screen says after Continue: nothing when the project opened.
export function adoptSay(found, r) {
  if (!r || r.ok === true || r.cancelled) return null
  if (r.ok === false) return { key: 'hub.openFailed', detail: r.error || '', error: true }
  if (!r.error) return null
  const key = errorKey(r.error, { repo: found?.case === 'repo' })
  return { key, detail: r.detail || (key === 'hub.failed' ? r.error : ''), error: true }
}

// The join form: the token field shows only after `auth` from a host the CLI could name (https), and the folder picked
// is kept for that retry. Any other result drops both: the token is never kept, the next try asks for the folder. That
// includes no result and a thrown Error (the project window failed to load after a good retry).
export const JOIN0 = { showToken: false, token: '', host: '', dir: null, say: null }

export function joinStep(state, r, t = text) {
  if (r?.error === 'auth' && r.host) {
    const again = !!(state.showToken && state.token)               // the first ask is a request, not a failure
    return { showToken: true, token: '', host: r.host, dir: r.dir || state.dir,
      say: { key: again ? 'hub.authAgain' : 'hub.auth', vars: { host: r.host }, detail: '', error: again } }
  }
  return { ...JOIN0, say: joinSay(r, t) }
}

// One try: hub.join (preload: url, token, dir) and the next state, whatever happens, a rejection included.
export async function joinOnce(hub, state, url, token, t = text) {
  let r
  try { r = await hub.join(url, token, state.dir || undefined) } catch (e) { r = e instanceof Error ? e : new Error(String(e)) }
  return joinStep(state, r, t)
}

function joinSay(r, t) {
  if (r instanceof Error) return { key: 'hub.failed', vars: {}, detail: r.message, error: true }
  if (!r || r.cancelled || r.ok === true) return null
  if (r.ok === false) return { key: 'hub.openFailed', vars: {}, detail: r.error || '', error: true }
  if (!r.error) return null
  const key = r.error === 'network' && !r.host ? 'hub.networkNoHost' : errorKey(r.error, { join: true })
  return { key, vars: { host: r.host || t('hub.server') }, detail: r.detail || (key === 'hub.failed' ? r.error : ''), error: true }
}

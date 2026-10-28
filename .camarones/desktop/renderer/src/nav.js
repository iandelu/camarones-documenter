// The app's places, pure: a project's sections, this machine's, which one an address asks for, a project's initials.

export const PROJECT = ['summary', 'board', 'decisions', 'plan', 'interviews', 'team', 'quality', 'libs', 'docs']
export const MACHINE = ['machine', 'guide', 'kitdev']

// Kit dev is the bench of a checkout of the kit (lib/kitdev.py): only there.
export const sections = ({ kitdev }) => ({ project: PROJECT, machine: kitdev ? MACHINE : MACHINE.filter((s) => s !== 'kitdev') })

// The first-run wizard (#/start): a place of its own, full width, never listed in the nav.
export const START = 'start'

export function sectionOf(hash, flags) {
  const s = ((hash || '').match(/^#\/([\w-]+)/) || [])[1]
  const all = [...PROJECT, ...sections(flags).machine, START]
  return all.includes(s) ? s : 'summary'
}

// What #/machine?host=<h>&kind=<k> asks the Tokens card to fill in (Quality links there for a repo's SonarQube).
export const TOKEN_KINDS = ['gitlab', 'github', 'sonarqube']
export function tokenPrefill(hash) {
  const [route, query = ''] = String(hash || '').split('?')
  if (route !== '#/machine') return { host: '', kind: '' }
  const q = new URLSearchParams(query)
  const kind = q.get('kind') || ''
  return { host: q.get('host') || '', kind: TOKEN_KINDS.includes(kind) ? kind : '' }
}

// Where a project window goes once it knows its first run (GET app/onboard/state): an unfinished one to the wizard,
// unless it is there already; a finished one (or no state: the read failed) stays where it was asked. null: stay.
export const firstRunPending = (state) => state?.done === false
export const firstRunRoute = (state, hash) => (firstRunPending(state) && sectionOf(hash, {}) !== START ? `#/${START}` : null)

// Two letters for the rail: the first letters of the first two words, or the first two of a single word.
export function initials(name) {
  const words = String(name || '').split(/[\s_-]+/).filter(Boolean)
  if (!words.length) return '?'
  const s = words.length > 1 ? words[0][0] + words[1][0] : words[0].slice(0, 2)
  return s.toUpperCase()
}

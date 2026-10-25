// The app's places, pure: a project's sections, this machine's, which one an address asks for, a project's initials.

export const PROJECT = ['summary', 'plan', 'interviews', 'team', 'quality', 'docs']
export const MACHINE = ['machine', 'kitdev']

// Kit dev is the bench of a checkout of the kit (lib/kitdev.py): only there.
export const sections = ({ kitdev }) => ({ project: PROJECT, machine: kitdev ? MACHINE : ['machine'] })

export function sectionOf(hash, flags) {
  const s = ((hash || '').match(/^#\/([\w-]+)/) || [])[1]
  const all = [...PROJECT, ...sections(flags).machine]
  return all.includes(s) ? s : 'summary'
}

// Where each section still lives in the portal's Taller while it is rebuilt here.
export const TALLER_OF = { summary: '#/', plan: '#/pipeline', interviews: '#/interviews', team: '#/team',
  quality: '#/check', docs: '#/docs', machine: '#/machine', kitdev: '#/kitdev' }

// Two letters for the rail: the first letters of the first two words, or the first two of a single word.
export function initials(name) {
  const words = String(name || '').split(/[\s_-]+/).filter(Boolean)
  if (!words.length) return '?'
  const s = words.length > 1 ? words[0][0] + words[1][0] : words[0].slice(0, 2)
  return s.toUpperCase()
}

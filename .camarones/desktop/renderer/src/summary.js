// The Summary's one button for the plan's next step (lib/plan.next_step): an agent unit opens a session with the
// agent in its own terminal (a half-done one continues), a unit the wizard runs goes where that work is done, and
// reviewing and reading are the portal's.
const WIZARD = {
  setup: { href: '#/machine', label: 'next.machine' },
  answers: { href: '#/interviews', label: 'next.answers' },
  ci: { href: '#/team', label: 'next.ci' },
  confirm: { href: '../#/review', label: 'next.review' },
  portal: { href: '../#/', label: 'next.read' },
}

// Where a unit the wizard runs is done in the app (the Plan's rows use it too).
export const linkFor = (u) => ({ kind: 'link', ...(WIZARD[u.type] || { href: '#/plan', label: 'next.plan' }) })

// What the last doctor check found (lib/doctor.problems), as one notice; null when all is fine or never checked.
export function doctorNote(p) {
  if (!p) return null
  const names = [...p.missing, ...p.tools]
  return names.length || p.drift ? { names, drift: p.drift } : null
}

// plan: {interviews} from the summary (null while nobody chose how they run: the agent would refuse the unit).
export const INTERVIEW_TYPES = ['interview-context', 'interview-language', 'interview-history']   // lib/plan.py
export function action(step, plan = {}) {
  const u = step?.unit
  if (u && plan.interviews === null && INTERVIEW_TYPES.includes(u.type)) return { kind: 'link', href: '#/interviews', label: 'iv.choose' }
  if (step?.kind === 'resume') return { kind: 'agent', unit: u.id, mode: 'continue', label: 'next.resume' }
  if (step?.kind === 'next' && u.runner === 'agent') return { kind: 'agent', unit: u.id, mode: 'new', label: 'next.start' }
  if (step?.kind === 'next') return linkFor(u)
  if (step?.kind === 'review') return { kind: 'link', ...WIZARD.confirm }
  return { kind: 'link', ...WIZARD.portal }
}

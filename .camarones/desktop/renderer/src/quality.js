// Pure pieces of the Quality, Machine, Kit dev and Libraries sections: the doctor's findings in the order you act on
// them, pytest's tally, setup's and the vulnerability scan's progress and a check's time.

// lib/doctor.report() → what is missing (needed prerequisites, pinned tools), with the command that fixes it; what
// is optional and absent; what is fine.
export function doctorRows(r) {
  const rows = [...(r?.prerequisites || []).map((p) => ({ ...p, kind: 'pre' })),
    ...(r?.tools || []).map((x) => ({ ...x, kind: 'tool', need: true }))]
  return { missing: rows.filter((x) => !x.ok && x.need), optional: rows.filter((x) => !x.ok && !x.need), fine: rows.filter((x) => x.ok) }
}

// The last "N passed, M failed …" line pytest prints.
export function pytestSummary(lines) {
  const last = [...(lines || [])].reverse().find((l) => /\d+ (passed|failed|error)/.test(l))
  return last ? [...last.matchAll(/(\d+) (passed|failed|errors?|skipped|deselected)/g)].map((m) => [m[2], m[1]]) : []
}

// `setup` prints ✔ per step done; lib/machine says how many steps it takes on this machine.
export function setupProgress(lines, steps) {
  const done = (lines || []).filter((l) => l.trim().startsWith('✔')).length
  return { done, pct: steps ? Math.min(100, Math.round((done / steps) * 100)) : 0 }
}

// `inventory --cves` logs `[n/total] repo: …` as it starts each repo (lib/osv.py), so the ones before it are done.
export function scanProgress(lines) {
  const p = { n: 0, total: 0, repo: '', done: [] }
  for (const l of lines || []) {
    const m = l.match(/^\[(\d+)\/(\d+)\] ([^:]+):/)
    if (!m) continue
    if (p.repo) p.done.push(p.repo)
    Object.assign(p, { n: +m[1], total: +m[2], repo: m[3] })
  }
  return p
}

// The arguments that attach to an inventory job already running (the server runs one job per command line), or null
// when none runs or it was started with others (`--fail-on` is CI's).
export function inventoryArgs(running) {
  const job = (running || []).find((j) => j.kind.split(' ')[0] === 'cmd:inventory')
  const flags = job ? job.kind.split(' ').slice(1) : null
  if (!flags || flags.some((f) => f !== '--json' && f !== '--cves')) return null
  return { json: flags.includes('--json'), cves: flags.includes('--cves') }
}

export const seconds = (iso) => { const ms = Date.parse(iso); return Number.isNaN(ms) ? null : ms / 1000 }

// The board rows (ui/src/health.js) whose control this app owns. `review` is a link into the portal and `repos` is
// the board's own table, so neither is here.
export const BOARD_ACTIONS = ['doctor', 'drift', 'fresh', 'evals', 'context', 'blocks', 'ab', 'libs']

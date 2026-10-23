// Pure helpers of the CI tab, from GET /api/ci.
const ORDER = ['umbrella', 'snippet', 'fresh', 'propose']

export function rows(s) {
  return ORDER.filter((k) => s.installed?.[k]).map((k) => {
    const x = s.installed[k]
    return { key: k, path: x.path, state: !x.path ? 'missing' : x.outdated ? 'outdated' : 'current' }
  })
}

export function pipelineState(p) {
  if (!p) return null
  const st = String(p.status || '').toLowerCase()
  if (['success', 'passed'].includes(st)) return { state: 'ok', word: 'passed' }
  if (['failure', 'failed', 'cancelled', 'canceled', 'timed_out'].includes(st)) return { state: 'bad', word: 'failed' }
  return { state: 'running', word: 'running' }
}

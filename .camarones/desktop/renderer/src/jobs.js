// The server's jobs (lib/serve.py: builds, wikis, the app's commands, Kit dev) as one store for the window. They live
// on the server, so they outlast a change of section; the panel lists them and the status bar says what runs.
export const RECENT = 6

// What runs, and the most recent first (the server keeps every job of its session).
export function arrange(list) {
  const rows = [...(list || [])].sort((a, b) => (b.started || 0) - (a.started || 0))
  return { running: rows.filter((j) => j.status === 'running'), recent: rows.slice(0, RECENT) }
}

// A job a person stopped ends failed on the server (rc ≠ 0) with stopped: true; here it is stopped, not failed.
export const state = (job) => (job.status === 'failed' && job.stopped ? 'stopped' : job.status)
export const chip = (job) => ({ running: 'info', done: 'ok', failed: 'bad' })[state(job)] || 'warn'

// started and now in seconds (the server's time.time()); t is the app's strings.
export function ago(started, now, t) {
  const s = Math.max(0, now - started)
  if (s < 60) return t('ago.now')
  if (s < 3600) return t('ago.min', { n: Math.floor(s / 60) })
  if (s < 86400) return t('ago.h', { n: Math.floor(s / 3600) })
  return t('ago.d', { n: Math.floor(s / 86400) })
}

// get: the server's GET. It looks often while something runs, rarely otherwise; refresh() looks now (after starting
// a job, so it shows at once) and keeps one look scheduled, never two.
export function jobsStore(get, { busy = 1500, idle = 8000, timers = globalThis } = {}) {
  let state = { running: [], recent: [], error: '' }
  let timer = null, stopped = false
  const listeners = new Set()
  async function refresh() {
    if (timer) timers.clearTimeout(timer)
    timer = null
    try {
      state = { ...arrange(await get('jobs')), error: '' }
    } catch (e) {
      state = { ...state, error: e.message }
    }
    listeners.forEach((f) => f())
    if (!stopped && !timer) timer = timers.setTimeout(refresh, state.running.length ? busy : idle)
  }
  return {
    get: () => state,
    subscribe(f) { listeners.add(f); return () => listeners.delete(f) },
    refresh,
    stop() { stopped = true; if (timer) timers.clearTimeout(timer); timer = null },
  }
}

// A job of the project's server (a catalog command, Kit dev…) followed to its end by asking for its new lines:
// resolves to the finished job (status, rc, result, stopped), or null when the page gave up on it.
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

export async function follow(srv, job, { onLine, every = 600, sleep = wait, gone = () => false } = {}) {
  let seen = 0
  for (;;) {
    const j = await srv.get(`jobs/${job.id}?since=${seen}`)
    seen = j.lines
    j.log.forEach((l) => onLine?.(l))
    if (j.status !== 'running') return j
    await sleep(every)
    if (gone()) return null
  }
}

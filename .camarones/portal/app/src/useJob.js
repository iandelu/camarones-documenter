import { useEffect, useRef, useState } from 'react'
import { postJSON, streamEvents } from './api.js'
import { t } from './i18n.js'

// A catalog command as a job of the app's server (lib/appapi.py): its lines as they come, then its status, exit code
// and, for --json, its result. `start` resolves to the finished job, so a panel can chain the next step. `post` starts
// the job (by default a catalog command; Kit dev passes its own).
const catalogCmd = (cmd, args, confirmed) => postJSON('app/cmd', { cmd, args, confirmed })

export function useJob(post = catalogCmd) {
  const [job, setJob] = useState(null)          // {id, status, rc, result, lines[]}
  const [error, setError] = useState('')
  const abort = useRef(null)
  useEffect(() => () => abort.current?.abort(), [])
  async function start(cmd, args, confirmed = false) {
    setError('')
    let end = null
    try {
      const j = await post(cmd, args, confirmed)
      setJob({ id: j.id, status: 'running', lines: [] })
      abort.current = new AbortController()
      await streamEvents(`app/jobs/${j.id}/events`, (ev) => {
        if (ev.type === 'line') setJob((cur) => ({ ...cur, lines: [...cur.lines, ev.text] }))
        else if (ev.type === 'end') { end = ev; setJob((cur) => ({ ...cur, status: ev.status, rc: ev.rc, result: ev.result })) }
      }, abort.current.signal)
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message)
    }
    return end
  }
  async function stop() {
    try { await postJSON(`app/jobs/${job.id}/cancel`, {}) } catch (e) { setError(e.message) }
  }
  const running = job?.status === 'running'
  const status = !job ? null : running ? t('twRunning') : job.status === 'done' ? t('twDone')
    : job.rc == null ? t('twStopped') : t('twFailed').replace('{rc}', job.rc)
  return { job, error, start, stop, running, status }
}

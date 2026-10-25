import { useEffect, useRef, useState } from 'react'
import { getJSON, postJSON } from './api.js'

// A build of the portal's server (api/build: first look, C4, wikis…) followed until it ends: its lines as they
// come, then its status. The docs views' plain scripts did this with watchJob() (legacy/core.js).
export function useBuild() {
  const [job, setJob] = useState(null)            // {label, status, lines[]}
  const [error, setError] = useState('')
  const alive = useRef(true)
  useEffect(() => () => { alive.current = false }, [])
  async function start(what, repo = '') {
    setError('')
    try {
      const j = await postJSON('build', { what, repo })
      setJob({ label: j.label, status: 'running', lines: [] })
      for (let since = 0; alive.current;) {
        const s = await getJSON(`jobs/${j.id}?since=${since}`)
        since = s.lines
        if (alive.current) setJob((cur) => ({ ...cur, status: s.status, lines: [...cur.lines, ...s.log] }))
        if (s.status !== 'running') return s
        await new Promise((ok) => setTimeout(ok, 1000))
      }
    } catch (e) { if (alive.current) setError(e.message) }
    return null
  }
  return { job, error, start, running: job?.status === 'running' }
}

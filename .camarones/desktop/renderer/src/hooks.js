import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { follow } from './cmd.js'

// A store with get() and subscribe(fn) (jobs.js) as React state.
export const useStore = (store) => useSyncExternalStore(store.subscribe, store.get)

// The agent CLIs installed on this machine (GET app/agents) and the one picked: the last one used, by default.
export function useAgents(srv) {
  const [agents, setAgents] = useState(null)
  const [agent, setAgent] = useState('')
  useEffect(() => {
    srv.get('app/agents').then((a) => {
      setAgents(a.agents)
      setAgent(a.agents.some((x) => x.id === a.last) ? a.last : a.agents[0]?.id || '')
    }, () => setAgents([]))
  }, [])
  const label = (id) => agents?.find((a) => a.id === id)?.label || id
  return { agents, agent, setAgent, label }
}

// A catalog command as a job of the server (POST app/cmd, lib/appapi.py), followed to its end: run() resolves to
// the finished job (status, rc, result, stopped), so a panel can read a --json result or chain the next step. The
// window's jobs store looks at once, so the panel below shows it; a quiet hook (a panel's background reads) stays
// out of that panel.
export function useCmd(srv, jobs, { quiet = false } = {}) {
  const [job, setJob] = useState(null)              // {status, lines[], rc, result, stopped}
  const [error, setError] = useState('')
  const alive = useRef(true)
  useEffect(() => () => { alive.current = false }, [])
  async function run(cmd, args = {}, confirmed = false) {
    setError('')
    setJob({ status: 'running', lines: [] })
    try {
      const started = await srv.post('app/cmd', { cmd, args, confirmed, quiet })
      jobs?.refresh()
      const end = await follow(srv, started, { gone: () => !alive.current,
        onLine: (l) => alive.current && setJob((j) => ({ ...j, lines: [...j.lines, l] })) })
      if (end && alive.current) setJob((j) => ({ ...j, status: end.status, rc: end.rc, result: end.result, stopped: end.stopped }))
      jobs?.refresh()
      return end
    } catch (e) {
      if (alive.current) { setError(e.message); setJob(null) }
      return null
    }
  }
  return { job, error, run, running: job?.status === 'running' }
}

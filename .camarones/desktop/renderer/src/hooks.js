import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { follow } from './cmd.js'

// The address after the #, as state: the app routes by it.
export function useHash() {
  const [hash, setHash] = useState(typeof location !== 'undefined' ? location.hash : '')
  useEffect(() => {
    const on = () => setHash(location.hash)
    addEventListener('hashchange', on)
    return () => removeEventListener('hashchange', on)
  }, [])
  return hash
}

// A store with get() and subscribe(fn) (jobs.js) as React state; the same snapshot when rendered to text (tests).
export const useStore = (store) => useSyncExternalStore(store.subscribe, store.get, store.get)

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

// A job of the server started by `start` (a POST that answers with the job), followed to its end: run() resolves to
// the finished job (status, rc, result, stopped, lines), so a panel can read a --json result or chain the next step. The
// window's jobs store looks at once, so the panel below shows it.
export function useJob(srv, jobs, start) {
  const [job, setJob] = useState(null)              // {status, lines[], rc, result, stopped}
  const [error, setError] = useState('')
  const alive = useRef(true)
  useEffect(() => () => { alive.current = false }, [])
  async function run(...args) {
    setError('')
    setJob({ status: 'running', lines: [] })
    const lines = []
    try {
      const started = await start(...args)
      if (alive.current) setJob((j) => ({ ...j, id: started.id }))
      jobs?.refresh()
      const end = await follow(srv, started, { gone: () => !alive.current,
        onLine: (l) => { lines.push(l); if (alive.current) setJob((j) => ({ ...j, lines: [...j.lines, l] })) } })
      if (end && alive.current) setJob((j) => ({ ...j, status: end.status, rc: end.rc, result: end.result, stopped: end.stopped }))
      jobs?.refresh()
      return end && { ...end, lines }
    } catch (e) {
      if (alive.current) { setError(e.message); setJob(null) }
      return null
    }
  }
  const stop = () => job?.id && srv.post(`app/jobs/${job.id}/cancel`, {}).catch((e) => setError(e.message))
  return { job, error, run, stop, running: job?.status === 'running' }
}

// A catalog command (POST app/cmd, lib/appapi.py); a quiet one (a panel's background read) stays out of the jobs panel.
export const useCmd = (srv, jobs, { quiet = false } = {}) =>
  useJob(srv, jobs, (cmd, args = {}, confirmed = false) => srv.post('app/cmd', { cmd, args, confirmed, quiet }))

// A Kit dev task (POST app/kitdev, lib/kitdev.py): the bench of a checkout of the kit.
export const useKit = (srv, jobs) => useJob(srv, jobs, (task, body = {}) => srv.post('app/kitdev', { task, ...body }))

import { useEffect, useState } from 'react'
import { getJSON } from './api.js'
import { href, parse } from './routes.js'

function useRoute() {
  const [route, setRoute] = useState(() => parse(window.location.hash))
  useEffect(() => {
    const on = () => setRoute(parse(window.location.hash))
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route
}

function Stat({ label, value, tone }) {
  return (
    <div className={`stat ${tone || ''}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

function Home() {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => { getJSON('status').then(setStatus, (e) => setError(e.message)) }, [])
  if (error) return <p className="muted">The portal server is not answering ({error}). Start it with <code>camaron up</code>.</p>
  if (!status) return <p className="muted">Loading…</p>
  const changed = Object.values(status.changes || {}).filter((c) => c.status === 'changed').length
  return (
    <section>
      <h1>Project brain</h1>
      <p className="lede">What the docs cover, what waits for a person, and what fell behind the code.</p>
      <div className="stats">
        <Stat label="plan units done" value={`${status.plan.done}/${status.plan.total}`} />
        <Stat label="pages to review" value={status.queue.length} tone={status.queue.length ? 'warn' : ''} />
        <Stat label="check errors" value={status.check.errors.length} tone={status.check.errors.length ? 'bad' : 'good'} />
        <Stat label="repos changed since documented" value={changed} tone={changed ? 'warn' : ''} />
      </div>
    </section>
  )
}

function Pipeline() {
  return (
    <section>
      <h1>Pipeline</h1>
      <p className="lede">The live view of runs (units, agents, merges) arrives here next.</p>
    </section>
  )
}

export default function App() {
  const route = useRoute()
  const views = { home: Home, pipeline: Pipeline }
  const View = views[route.view] || Home
  return (
    <div className="shell">
      <header className="top">
        <a className="brand" href={href('home')}>Camarón</a>
        <nav>
          <a className={route.view === 'home' ? 'on' : ''} href={href('home')}>Home</a>
          <a className={route.view === 'pipeline' ? 'on' : ''} href={href('pipeline')}>Pipeline</a>
          <a href="/">Classic portal</a>
        </nav>
      </header>
      <main key={route.view} className="view"><View arg={route.arg} /></main>
    </div>
  )
}

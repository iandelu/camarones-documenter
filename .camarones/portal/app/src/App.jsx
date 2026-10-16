import { lazy, Suspense, useEffect, useState } from 'react'
import { MotionConfig } from 'motion/react'
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
  const [check, setCheck] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    getJSON('status?check=0').then(setStatus, (e) => setError(e.message))
    getJSON('check').then(setCheck, () => setCheck({ errors: [], warnings: [], failed: true }))   // slow on big projects
  }, [])
  if (error) return <p className="muted">The portal server is not answering ({error}). Start it with <code>camaron up</code>.</p>
  if (!status) return <p className="muted">Loading…</p>
  const changed = Object.values(status.changes || {}).filter((c) => c.status === 'changed').length
  const errors = check ? (check.failed ? '?' : check.errors.length) : '…'
  const tone = !check || check.failed ? '' : check.errors.length ? 'bad' : 'good'
  return (
    <section>
      <h1>Project brain</h1>
      <p className="lede">What the docs cover, what waits for a person, and what fell behind the code.</p>
      <div className="stats">
        <Stat label="plan units done" value={`${status.plan.done}/${status.plan.total}`} />
        <Stat label="pages to review" value={status.queue.length} tone={status.queue.length ? 'warn' : ''} />
        <Stat label={check ? 'check errors' : 'check errors (checking…)'} value={errors} tone={tone} />
        <Stat label="repos changed since documented" value={changed} tone={changed ? 'warn' : ''} />
      </div>
      <p><a className="go" href={href('pipeline')}>Open the pipeline →</a></p>
    </section>
  )
}

const Pipeline = lazy(() => import('./Pipeline.jsx'))          // React Flow loads only with this tab

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
      <MotionConfig reducedMotion="user">
        <main key={route.view} className="view">
          <Suspense fallback={<p className="muted">Loading…</p>}><View arg={route.arg} /></Suspense>
        </main>
      </MotionConfig>
    </div>
  )
}

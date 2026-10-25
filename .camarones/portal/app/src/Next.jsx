import { useEffect, useRef, useState } from 'react'
import { getJSON, postJSON } from './api.js'
import AgentLaunch from './AgentLaunch.jsx'
import { t } from './i18n.js'
import { isEmptyProject, pickNext } from './next.js'

const fill = (s, vars) => Object.entries(vars).reduce((acc, [k, v]) => acc.replaceAll(`{${k}}`, v), s)

// The project window's landing view (#/next): the plan's next unit with a session on it, another unit from the
// Plan, and how many drafts wait for review. Docs, Architecture and Quality are read in the browser portal.
export default function Next() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const load = () => Promise.all([getJSON('pipeline'), getJSON('status?check=0'), getJSON('tree')])     // no quality check: it takes seconds
    .then(([pipeline, status, tree]) => { setError(''); setData({ units: pipeline.units, status, empty: isEmptyProject(tree) }) }, (e) => setError(e.message))
  useEffect(() => { load() }, [])

  if (error) return (
    <section className="view nx"><p className="error" role="alert">{t('nxFailed')} {error}</p>
      <button type="button" className="small" onClick={load}>{t('obRetry')}</button></section>
  )
  if (!data) return <section className="view nx"><div className="skeleton" aria-busy="true" /></section>

  const { units, status, empty } = data
  const unit = pickNext(units)
  const waiting = status.queue.length
  const finished = !unit
  return (
    <section className="view nx">
      <h2>{t('nxTitle')}</h2>
      <p className="lede">{fill(t('nxPlan'), { total: String(status.plan.total), done: String(status.plan.done) })}</p>
      {empty ? <FirstLook onDone={load} /> : null}
      <div className={`nx-card${finished || empty ? '' : ' primary'}`}>
        {finished ? <>
          <h3>{t('nxAllDone')}</h3>
          <p className="muted">{t('nxAllDoneText')}</p>
        </> : <>
          <h3>{unit.title}</h3>
          <p className="muted small">{describe(unit)}</p>
          {unit.runner === 'agent' && unit.status !== 'blocked' ? <AgentLaunch unit={unit} title={false} />
            : <p className="muted small">{t(unit.status === 'blocked' ? 'nxRetryInPlan' : 'nxWizardUnit')}</p>}
        </>}
        <p className="nx-more"><a className="button ghost small" href="#/pipeline">{t('nxAnother')}</a></p>
      </div>
      <a className="nx-card nx-review" href="#/review">
        <b>{fill(t(waiting === 1 ? 'nxReviewOne' : 'nxReviewMany'), { n: String(waiting) })}</b>
        <span className="muted small">{t('nxReviewGo')}</span>
      </a>
      <p className="muted small nx-foot">{t('nxFoot')}</p>
    </section>
  )
}

// One line on the unit: the note the plan keeps on it, else where it sits (what the Pipeline shows: phase, type, repo).
function describe(unit) {
  const note = String(unit.notes || '').split('\n')[0].trim()
  const where = fill(t('nxWhere'), { phase: String(unit.phase ?? '?'), type: unit.type || unit.id })
  return [note.slice(0, 160) || where, unit.repo, unit.status === 'doing' ? t('nxDoing') : unit.status === 'blocked' ? t('nxBlocked') : '']
    .filter(Boolean).join(' · ')
}

// An empty project: the first look from the code, no AI (the build the docs home offers in the browser), as a job
// polled until it ends; then the view reloads.
function FirstLook({ onDone }) {
  const [state, setState] = useState({ running: false, error: '' })
  const alive = useRef(true)
  useEffect(() => () => { alive.current = false }, [])
  async function go() {
    setState({ running: true, error: '' })
    try {
      const job = await postJSON('build', { what: 'first-look' })
      for (;;) {
        const j = await getJSON(`jobs/${job.id}`)
        if (!alive.current) return
        if (j.status !== 'running') {
          if (j.status === 'done') return onDone()
          return setState({ running: false, error: `${t('nxFirstFailed')} ${j.log?.slice(-1)[0] || ''}`.trim() })
        }
        await new Promise((r) => setTimeout(r, 1000))
      }
    } catch (e) { if (alive.current) setState({ running: false, error: `${t('nxFirstFailed')} ${e.message}` }) }
  }
  return (
    <div className="nx-card nx-first primary">
      <h3>{t('nxFirstTitle')}</h3>
      <p className="muted">{t('nxFirstText')}</p>
      <p className="nx-more"><button type="button" disabled={state.running} onClick={go}>{state.running ? t('nxFirstRunning') : t('nxFirstGo')}</button></p>
      {state.error ? <p className="error" role="alert">{state.error}</p> : null}
    </div>
  )
}

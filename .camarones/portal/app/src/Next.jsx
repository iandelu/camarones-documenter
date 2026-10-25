import { useEffect, useState } from 'react'
import { getJSON } from './api.js'
import AgentLaunch from './AgentLaunch.jsx'
import { t } from './i18n.js'
import { pickNext } from './next.js'

const fill = (s, vars) => Object.entries(vars).reduce((acc, [k, v]) => acc.replaceAll(`{${k}}`, v), s)

// The project window's landing view (#/next): the plan's next unit with a session on it, another unit from the
// Plan, and how many drafts wait for review. Docs, Architecture and Quality are read in the browser portal.
export default function Next() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const load = () => Promise.all([getJSON('pipeline'), getJSON('status?check=0')])     // no quality check: it takes seconds
    .then(([pipeline, status]) => { setError(''); setData({ units: pipeline.units, status }) }, (e) => setError(e.message))
  useEffect(() => { load() }, [])

  if (error) return (
    <section className="view nx"><p className="error" role="alert">{t('nxFailed')} {error}</p>
      <button type="button" className="small" onClick={load}>{t('obRetry')}</button></section>
  )
  if (!data) return <section className="view nx"><div className="skeleton" aria-busy="true" /></section>

  const { units, status } = data
  const unit = pickNext(units)
  const waiting = status.queue.length
  const finished = !unit
  return (
    <section className="view nx">
      <h2>{t('nxTitle')}</h2>
      <p className="lede">{fill(t('nxPlan'), { total: String(status.plan.total), done: String(status.plan.done) })}</p>
      <div className={`nx-card${finished ? '' : ' primary'}`}>
        {finished ? <>
          <h3>{t('nxAllDone')}</h3>
          <p className="muted">{t('nxAllDoneText')}</p>
        </> : <>
          <h3>{unit.title}</h3>
          <p className="muted small"><code>{unit.id}</code>{unit.repo ? <> · {unit.repo}</> : null}{unit.status === 'doing' ? <> · {t('nxDoing')}</> : null}
            {unit.status === 'blocked' ? <> · {t('nxBlocked')}</> : null}</p>
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

import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card, Skeleton } from '@camaron/ui'
import { action, doctorNote } from '../summary.js'
import { useAgents, useStore } from '../hooks.js'
import { firstRunPending } from '../nav.js'
import { AgentPicker, Failed, Page } from '../parts.jsx'
import { lang, t } from '../i18n.js'

// The project's Summary: one next step (lib/plan.next_step, the wizard's own rule) with the one button that takes
// it, and where the plan, the review and the jobs stand. It looks again when a job ends: the plan may have moved.
// While the first run is unfinished (GET app/onboard/state), a notice leads back to the wizard; a failed read shows none.
export default function Summary({ srv, jobs }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [firstRun, setFirstRun] = useState(false)
  const [launch, setLaunch] = useState({ busy: false, note: '', error: '' })
  const a = useAgents(srv)
  const { running } = useStore(jobs)
  const load = () => srv.get('app/summary', { lang: lang() }).then((d) => { setData(d); setError('') }, (e) => setError(e.message))
  useEffect(() => {
    load()
    srv.get('app/onboard/state').then((s) => setFirstRun(firstRunPending(s)), () => setFirstRun(false))
  }, [])
  const was = useRef(running.length)
  useEffect(() => {
    if (running.length < was.current) load()
    was.current = running.length
  }, [running.length])

  const title = t('nav.summary')
  if (error) return <Page title={title}><Failed title={t('summary.failed')} detail={error} onRetry={() => { setError(''); load() }} /></Page>
  if (!data) return <Page title={title}><Skeleton lines={5} /></Page>
  const { step, plan, review } = data
  const next = action(step)
  const doc = doctorNote(data.doctor)
  const start = async () => {
    setLaunch({ busy: true, note: '', error: '' })
    try {
      await srv.post('app/agent', { unit: next.unit, agent: a.agent, lang: lang(), mode: next.mode })
      setLaunch({ busy: false, note: t('next.opened', { agent: a.label(a.agent) }), error: '' })
      load()
    } catch (e) {
      setLaunch({ busy: false, note: '', error: e.message })
    }
  }
  const heading = step.unit ? step.unit.title : step.kind === 'review'
    ? (step.count === 1 ? t('next.reviewTitle1') : t('next.reviewTitle', { n: step.count })) : t('next.doneTitle')
  return (
    <Page title={title}>
      {firstRun ? <FirstRunNotice /> : null}
      <Card className="dk-next">
        <span className="eyebrow">{t(step.kind === 'resume' ? 'next.eyebrowResume' : 'next.eyebrow')}</span>
        <h2 className="dk-next-title">{heading}</h2>
        {step.unit && <code className="muted small">{step.unit.id}</code>}
        {next.kind === 'agent' && a.agents && !a.agents.length
          ? <Aviso tone="warn" title={t('next.noAgent')}><Button href="#/machine">{t('next.machine')}</Button></Aviso>
          : (
            <div className="row">
              {next.kind === 'agent' && <AgentPicker a={a} />}
              {next.kind === 'agent'
                ? <Button variant="primary" disabled={!a.agent || launch.busy} onClick={start}>{t(next.label, { agent: a.label(a.agent) })}</Button>
                : <Button variant="primary" href={next.href}>{t(next.label)}</Button>}
              {next.href !== '#/plan' && <Button variant="ghost" href="#/plan">{t('next.plan')}</Button>}
            </div>
          )}
        {launch.note && <p className="muted small" role="status">{launch.note}</p>}
        {launch.error && <Aviso tone="error" title={t('next.failed')} detail={launch.error} />}
      </Card>
      {doc ? (
        <Aviso tone="warn" title={t('sum.doctor')}>
          <span className="row"><span className="small">{[doc.names.join(', '), doc.drift ? t('sum.drift', { n: doc.drift }) : ''].filter(Boolean).join(' · ')}</span>
            <Button size="sm" href="#/quality">{t('sum.doctorGo')}</Button></span>
        </Aviso>
      ) : null}
      <div className="dk-stats">
        <Card className="dk-stat">
          <span className="eyebrow">{t('stat.plan')}</span>
          <b className="t-impact dk-stat-n">{plan.done}/{plan.total}</b>
          <progress className="dk-progress" value={plan.done} max={plan.total || 1} aria-label={t('stat.plan')} />
        </Card>
        <Card className="dk-stat">
          <span className="eyebrow">{t('stat.review')}</span>
          {review ? <a className="t-impact dk-stat-n" href="../#/review">{review}</a> : <b className="t-impact dk-stat-n">0</b>}
        </Card>
        <Card className="dk-stat">
          <span className="eyebrow">{t('stat.jobs')}</span>
          <b className="t-impact dk-stat-n">{running.length}</b>
        </Card>
      </div>
    </Page>
  )
}

// The way back to the first-run wizard, for whoever left it for another section before finishing.
export function FirstRunNotice() {
  return <Aviso tone="info" title={t('sum.firstRun')} action={<Button size="sm" href="#/start">{t('sum.firstRunGo')}</Button>} />
}

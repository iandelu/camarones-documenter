import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card, Skeleton } from '@camaron/ui'
import { action } from './summary.js'
import { useStore } from './useStore.js'
import { lang, t } from './i18n.js'

// The project's Summary: one next step (lib/plan.next_step, the wizard's own rule) with the one button that takes
// it, and where the plan, the review and the jobs stand. It looks again when a job ends: the plan may have moved.
export default function Summary({ srv, jobs }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [agents, setAgents] = useState(null)       // [{id, label}] installed on this machine
  const [agent, setAgent] = useState('')
  const [launch, setLaunch] = useState({ busy: false, note: '', error: '' })
  const { running } = useStore(jobs)
  const load = () => srv.get('app/summary').then((d) => { setData(d); setError('') }, (e) => setError(e.message))
  useEffect(() => {
    load()
    srv.get('app/agents').then((a) => {
      setAgents(a.agents)
      setAgent(a.agents.some((x) => x.id === a.last) ? a.last : a.agents[0]?.id || '')
    }, () => setAgents([]))
  }, [])
  const was = useRef(running.length)
  useEffect(() => {
    if (running.length < was.current) load()
    was.current = running.length
  }, [running.length])

  if (error) return <Page><Aviso tone="error" title={t('summary.failed')} detail={error} /></Page>
  if (!data) return <Page><Skeleton lines={5} /></Page>
  const { step, plan, review } = data
  const next = action(step)
  const label = (id) => agents?.find((a) => a.id === id)?.label || id
  const start = async () => {
    setLaunch({ busy: true, note: '', error: '' })
    try {
      await srv.post('app/agent', { unit: next.unit, agent, lang: lang(), mode: next.mode })
      setLaunch({ busy: false, note: t('next.opened', { agent: label(agent) }), error: '' })
      load()
    } catch (e) {
      setLaunch({ busy: false, note: '', error: e.message })
    }
  }
  const title = step.unit ? step.unit.title : step.kind === 'review'
    ? (step.count === 1 ? t('next.reviewTitle1') : t('next.reviewTitle', { n: step.count })) : t('next.doneTitle')
  return (
    <Page>
      <Card className="dk-next">
        <span className="eyebrow">{t(step.kind === 'resume' ? 'next.eyebrowResume' : 'next.eyebrow')}</span>
        <h2 className="dk-next-title">{title}</h2>
        {step.unit && <code className="muted small">{step.unit.id}</code>}
        {next.kind === 'agent' && agents && !agents.length
          ? <Aviso tone="warn" title={t('next.noAgent')}><Button href="#/machine">{t('next.machine')}</Button></Aviso>
          : (
            <div className="row">
              {next.kind === 'agent' && agents?.length > 1 && (
                <select className="cu-input dk-select" aria-label={t('next.agent')} value={agent} onChange={(e) => setAgent(e.target.value)}>
                  {agents.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
                </select>
              )}
              {next.kind === 'agent'
                ? <Button variant="primary" disabled={!agent || launch.busy} onClick={start}>{t(next.label, { agent: label(agent) })}</Button>
                : <Button variant="primary" href={next.href}>{t(next.label)}</Button>}
              {next.href !== '#/plan' && <Button variant="ghost" href="#/plan">{t('next.plan')}</Button>}
            </div>
          )}
        {launch.note && <p className="muted small" role="status">{launch.note}</p>}
        {launch.error && <Aviso tone="error" title={t('next.failed')} detail={launch.error} />}
      </Card>
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

const Page = ({ children }) => (
  <div className="dk-page"><h1 className="t-impact">{t('nav.summary')}</h1>{children}</div>
)

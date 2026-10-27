import { useEffect, useState } from 'react'
import { Button, Card, Skeleton } from '@camaron/ui'
import { useAgents, useCmd } from '../hooks.js'
import { AgentPicker, Failed, JobOutput, ModeChoice, Page, UnitRow } from '../parts.jsx'
import Commands from './Commands.jsx'
import { lang, t } from '../i18n.js'

// The interviews by task: how they run (the team questionnaire or live with an agent, asked first while nobody chose
// it: the agent refuses an interview until then); with the questionnaire, its
// state and what moves it — answer in the portal, export the form to share, import what comes back, close the round;
// then each interview unit with the agent. Every action is a catalog command run by the server.
const UNITS = ['questionnaire', 'answers', 'interview-context', 'interview-language', 'interview-history']

export default function Interviews({ srv, jobs, app }) {
  const [d, setD] = useState(null)
  const [units, setUnits] = useState([])
  const [all, setAll] = useState([])
  const [error, setError] = useState('')
  const [root, setRoot] = useState('')
  const a = useAgents(srv)
  const c = useCmd(srv, jobs)
  const load = () => {
    srv.get('interview').then((x) => { setD(x); setError('') }, (e) => setError(e.message))
    srv.get('pipeline', { lang: lang() }).then((p) => { setAll(p.units); setUnits(p.units.filter((u) => UNITS.includes(u.id))) }, () => {})
  }
  useEffect(() => { load(); srv.get('app/info').then((i) => setRoot(i.root), () => {}) }, [])
  const step = async (cmd, args) => { const end = await c.run(cmd, args); load(); return end }
  async function exportIt() {
    const end = await step('interview', { action: 'export', lang: lang() })
    if (end?.status === 'done' && root) {
      const sep = root.includes('\\') ? '\\' : '/'
      app.reveal?.([root, 'docs', 'interview', 'questionnaire', 'questionnaire.html'].join(sep))
    }
  }
  async function importIt() {
    const files = await app.pickFiles?.('answers')
    if (files?.length) step('interview', { action: 'import', args: files })
  }
  if (error) return <Page title={t('nav.interviews')}><Failed title={t('iv.failed')} detail={error} onRetry={() => { setError(''); load() }} /></Page>
  if (!d) return <Page title={t('nav.interviews')}><Skeleton lines={5} /></Page>
  const team = d.mode === 'team'
  const s = d.status
  const answers = units.find((u) => u.id === 'answers')
  const agentUnits = units.filter((u) => u.runner === 'agent')
  if (!d.chosen) return (
    <Page title={t('nav.interviews')}>
      <Card className="dk-run" data-tour="iv-mode">
        <span className="eyebrow">{t('iv.mode')}</span>
        <b>{t('iv.chooseTitle')}</b>
        <p className="muted small">{t('iv.chooseLead')}</p>
        <ModeChoice srv={srv} jobs={jobs} onChosen={load} />
      </Card>
    </Page>
  )
  return (
    <Page title={t('nav.interviews')}>
      <Card className="dk-run" data-tour="iv-mode">
        <span className="eyebrow">{t('iv.mode')}</span>
        <div className="row"><b>{team ? t('iv.team') : t('iv.live')}</b><span className="dk-grow"></span>
          <Button size="sm" variant="ghost" disabled={c.running}
            onClick={() => step('interview', { action: 'mode', args: [team ? 'live' : 'team'] })}>{team ? t('iv.toLive') : t('iv.toTeam')}</Button></div>
      </Card>
      {team ? (
        <Card className="dk-run" data-tour="iv-questionnaire">
          <span className="eyebrow">{t('iv.team')}</span>
          {d.available ? (<>
            <div className="row">
              <span>{t('iv.state', { q: s.questions, p: s.respondents.length })}</span>
              {s.respondents.length ? <span className="muted small">{s.respondents.map((r) => r.name).join(', ')}</span> : null}
              {s.conflicts.length ? <span className="cu-chip cu-chip--warn">{t('iv.conflicts', { n: s.conflicts.length })}</span> : null}
            </div>
            <div className="row">
              <Button size="sm" variant="primary" href="../#/interview">{t('iv.answer')}</Button>
              <Button size="sm" disabled={c.running} onClick={exportIt}>{t('iv.export')}</Button>
              <Button size="sm" disabled={c.running} onClick={importIt}>{t('iv.import')}</Button>
              {answers && answers.status !== 'done' && s.respondents.length
                ? <Button size="sm" variant="ghost" disabled={c.running} onClick={() => step('plan', { action: 'done', unit: 'answers' })}>{t('iv.close')}</Button> : null}
            </div>
          </>) : <p className="muted small">{t('iv.noForm')}</p>}
        </Card>
      ) : null}
      <JobOutput c={c} />
      {agentUnits.length ? (
        <section className="dk-group-block" data-tour="iv-agents">
          <div className="row dk-units-head"><h2 className="eyebrow dk-group">{t('iv.units')}</h2><span className="dk-grow"></span><AgentPicker a={a} /></div>
          <ul className="dk-units">{agentUnits.map((u) => <UnitRow key={u.id} u={u} all={all} srv={srv} a={a} plan={{ interviews: d.mode }} onChanged={load} />)}</ul>
        </section>
      ) : null}
      <Commands srv={srv} jobs={jobs} section="interviews" />
    </Page>
  )
}

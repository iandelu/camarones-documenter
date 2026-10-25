import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card } from '@camaron/ui'
import { t as tr } from '../i18n.js'
import { useBuild } from '../useBuild.js'
import { homeKpis } from '../zones.js'
import { askHref, emptyProject, kpiHref, withoutH1 } from './home.js'
import { core } from '../core.js'
import { docsGet } from '../docsApi.js'
import { drawToc, mountDoc } from '../content/doc.js'


// Home (#/): the question first, the project home ("The system") when there is one, then the docs' state, each figure
// a way in. The zones are in the sidebar.
export default function Home() {
  const index = core.tree()
  const mode = core.mode()
  const t = core.t
  if (emptyProject(index)) return <FirstLook index={index} mode={mode} t={t} />
  const kpis = homeKpis(index)
  return (
    <div className="page wide start">
      <header className="start-hero aurora-bg">
        <p className="eyebrow">{t('home.eyebrow', { project: index.project, n: (index.repos || []).length })}</p>
        <h1 className="t-impact">{t('home.title')}<br /><span className="t-eco">{t('home.eco')}</span></h1>
        <AskForm mode={mode} t={t} />
      </header>
      {core.byPath('index.md') && <System t={t} />}
      {kpis.length > 0 && (
        <section className="home-kpis" aria-label={t('home.state')}>
          {kpis.map((k) => (
            <Card as="a" key={k.id} href={kpiHref(k.id)} className={`home-kpi ${k.tone || ''}`}>
              <span className="eyebrow">{t('kpi.' + k.id)}</span>
              <b>{k.value}</b>
              <small>{t('kpid.' + k.id)}</small>
            </Card>
          ))}
        </section>
      )}
    </div>
  )
}

// The project home, in the reader's language when it has one, else English; the Home still works without it.
function System({ t }) {
  const body = useRef(null)
  const [gone, setGone] = useState(false)
  useEffect(() => {
    let live = true
    ;(async () => {
      let d = await docsGet('doc', { path: 'index.md', lang: core.lang() })
      if (!d.exists) d = await docsGet('doc', { path: 'index.md' })
      if (!d.exists) throw new Error('no index.md')
      if (!live || !body.current) return
      body.current.replaceChildren()
      await mountDoc(body.current, withoutH1(d.raw), 'index.md', '', d.blocks)
      drawToc(null)                                          // the Home is bare: no outline of the embedded page
    })().catch(() => live && setGone(true))
    return () => { live = false }
  }, [])
  if (gone) return null
  return (
    <section className="start-sec start-home" aria-labelledby="home-system">
      <h2 className="t-impact" id="home-system">{t('home.system')}</h2>
      <div className="start-home-body" ref={body}></div>
    </section>
  )
}

function AskForm({ mode, t }) {
  const [q, setQ] = useState('')
  const label = t(mode === 'static' ? 'search' : 'homeAsk')
  const submit = (e) => {
    e.preventDefault()
    const href = askHref(q, mode)
    if (href) location.hash = href
  }
  return (
    <form className="start-ask" onSubmit={submit}>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('home.askPh')} aria-label={label} autoComplete="off" />
      <Button type="submit" variant="primary">{label} <span aria-hidden="true">→</span></Button>
    </form>
  )
}

// Nothing documented yet: one way forward — a first look from the code, no AI (desktop app), then the plan.
function FirstLook({ index, mode, t }) {
  const build = useBuild()
  const tutorial = (index.kitGuides || []).find((g) => g.endsWith('tutorial.md')) || (index.kitGuides || [])[0]
  const run = async () => { const end = await build.start('first-look'); if (end?.status === 'done') location.reload() }
  return (
    <div className="page hero empty aurora-bg">
      <img className="hero-logo" src="favicon.svg" alt="" width="72" height="72" />
      <h1>{index.project}</h1>
      <p className="lead">{t('homeEmpty')}</p>
      <p className="muted">{t('noDocsHelp')}</p>
      {mode !== 'static' && (
        <div className="row center">
          {mode === 'app' && <Button variant="primary" onClick={run} disabled={build.running}>{tr('home.firstLook')}</Button>}
          <Button href="#/pipeline">{t('nextUnit')} <span aria-hidden="true">→</span></Button>
        </div>
      )}
      {build.job && <pre className="joblog" aria-live="polite">{build.job.lines.join('\n')}</pre>}
      {build.error && <Aviso tone="error" title={tr('home.firstLookFailed')} detail={build.error} />}
      {tutorial && <p className="small"><a href={core.hrefFor(tutorial)}>{t('readTutorial')} <span aria-hidden="true">→</span></a></p>}
    </div>
  )
}

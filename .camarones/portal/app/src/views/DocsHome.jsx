import { useEffect, useRef, useState } from 'react'
import { Card, Chip } from '@camaron/ui'
import { docsGet } from '../docsApi.js'
import { emptyProject } from './home.js'
import { audience } from './DocsTree.jsx'
import { buildTree, flatten, forBusiness, sortedDirs } from './tree.js'

const L = () => window.CamaronLegacy

// #/docs: the project's docs at a glance — figures, one card per section (C4 and wikis too), the system context
// diagram and the project's own index page.
export default function DocsHome() {
  const legacy = L()
  const t = legacy.t
  const index = legacy.tree()
  const lang = legacy.lang()
  const business = audience() === 'business'
  const empty = emptyProject(index)
  const body = useRef(null)
  const [home, setHome] = useState(null)
  useEffect(() => { if (empty) location.replace('#/') }, [empty])
  useEffect(() => {
    if (empty || !body.current) return
    const pending = [legacy.drawC4(body.current.parentElement)]
    if (legacy.byPath('index.md')) {
      pending.push(docsGet('doc', { path: 'index.md', lang }).then(async (d) => {
        const raw = d.exists ? d.raw : (await docsGet('doc', { path: 'index.md' })).raw
        setHome(d)
        body.current.innerHTML = ''
        await legacy.mountDoc(body.current, raw, 'index.md')
      }))
    }
    Promise.all(pending).catch(() => {})
  }, [])
  if (empty) return null

  const sections = index.sections || []
  const docs = (index.docs || []).filter((d) => (d.space || 'docs') === 'docs' && (!business || forBusiness(d)))
  const tree = buildTree(docs)
  const wikiPages = business ? 0 : (index.docs || []).filter((d) => d.space === 'wiki').length
  const confirmed = docs.length ? Math.round(100 * docs.filter((d) => d.trust === 'confirmed').length / docs.length) : 0
  const views = index.views || []
  const flows = views.filter((v) => v.kind === 'dynamic').length || (tree.dirs.flows ? tree.dirs.flows.pages.length : 0)
  const stats = [t('statPages', { n: docs.length }), t('statConfirmed', { n: confirmed }),
    flows ? t('statFlows', { n: flows }) : '', views.length ? t('statViews', { n: views.length }) : ''].filter(Boolean)
  const described = (k) => (t(k) === k ? '' : t(k))
  const cards = sortedDirs(tree, sections).map((n) => ({ key: n.path, href: legacy.hrefFor(n.index?.path || flatten(n, sections, lang)[0]),
    label: legacy.sectionLabel(n.name), desc: described('secd.' + n.name), count: flatten(n, sections, lang).length }))
  if (views.length) cards.splice(1, 0, { key: 'c4', href: '#/c4', label: 'C4', desc: described('secd.c4'), count: views.length })
  if (wikiPages) cards.push({ key: 'wikis', href: '#/wikis', label: t('wikis'), desc: described('secd.wikis'), count: wikiPages })
  const row = legacy.byPath('index.md')
  return (
    <div className="docpage">
      <div className="page wide home">
        <header className="hero">
          <h1>{row?.title && row.title !== 'index' ? row.title : index.project}</h1>
          <p className="lead">{row?.description || t('homeLead')}</p>
          <div className="stats">{stats.map((s) => <Chip key={s}>{s}</Chip>)}</div>
          {business && <p className="muted small">{t('businessOn')}</p>}
        </header>
        <div className="cards">
          {cards.map((c) => (
            <Card as="a" key={c.key} href={c.href} className="card link">
              <b>{c.label} <span className="count">{c.count}</span></b>
              {c.desc && <p className="muted small">{c.desc}</p>}
            </Card>
          ))}
        </div>
        {views.some((v) => v.id === 'index') && <><h2 className="home-h">{t('systemContext')}</h2><div className="c4embed" data-view="index"></div></>}
        <div ref={body} aria-busy={legacy.byPath('index.md') && !home ? 'true' : undefined}></div>
      </div>
      <aside className="doc-aside"><div id="toc" className="toc empty"></div></aside>
    </div>
  )
}

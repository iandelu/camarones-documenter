import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Chip, EmptyState, Skeleton } from '@camaron/ui'
import { docsGet } from '../docsApi.js'
import { useBuild } from '../useBuild.js'
import { codeCrumbs, codeRoute, codeView, graphModel, inSub, mixHex, nextSeg, searchFiles, singleFolder, subHref } from './code.js'
import { core } from '../core.js'

const runs = () => core.mode() === 'app'
const VIS = 'vendor/vis-network@9.1.6/standalone/umd/vis-network.min.js'
let visReady = null
const loadVis = () => (visReady ||= new Promise((ok) => {
  if (window.vis?.Network) return ok(true)
  const s = document.createElement('script')
  s.src = VIS
  s.onload = () => ok(!!window.vis?.Network)
  s.onerror = () => ok(false)
  document.head.append(s)
}))

// One colour per module, from the theme's brand and state tokens; the soft one is mixed toward the canvas.
const HUES = ['--color-aurora-cyan', '--color-aurora-violet', '--color-aurora-coral', '--color-estado-bien',
  '--color-aurora-pink', '--color-aurora-amber', '--color-acento-texto', '--color-estado-aviso']
function themeLook(t) {
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim()
  const canvas = css('--color-canvas')
  const dark = document.documentElement.dataset.theme === 'dark'
    || (!document.documentElement.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches)
  const hues = HUES.map(css)
  return { t, ink: css('--color-ink'), muted: css('--color-ink-dim'), line: css('--color-rule'), raise: css('--color-canvas-elevated'),
    accent: css('--color-acento-texto'), colorOf: (g, soft) => (soft ? mixHex(hues[g % hues.length], canvas, dark ? 0.32 : 0.24) : hues[g % hues.length]) }
}
const swatch = (g) => ({ background: `var(${HUES[g % HUES.length]})` })

let mapCache = { repo: '', map: null }
const codeMap = async (repo) => {
  if (mapCache.repo !== repo) mapCache = { repo, map: await docsGet('codemap', { repo }) }
  return mapCache.map
}

// The sidebar on the code views: each repo with a map, and graphify's full graph.
export function CodeSide({ arg }) {
  const t = core.t
  const index = core.tree()
  const { repo } = codeRoute(arg, index)
  return (
    <nav className="code-side" aria-label={t('codeTab')}>
      <div className="side-title">{t('codeTab')}</div>
      <div className="group">
        {(index.codeMaps || []).map((r) => <a key={r} href={`#/code/${r}`} className={r === repo ? 'on' : ''}>{r}</a>)}
        {!(index.codeMaps || []).length && <p className="muted small">{t('noCodeMap')}</p>}
      </div>
      {(index.codeGraphs || []).length > 0 && (
        <div className="group"><div className="group-title">{t('explore')}</div>
          <a href={`#/code/${repo || 'all'}/graph`}>{t('fullGraph')}</a></div>
      )}
    </nav>
  )
}

// #/code/…: the module map, one module's files (folder by folder), or one file with what it uses and what uses it.
export default function CodeMap({ arg }) {
  const t = core.t
  const index = core.tree()
  const r = codeRoute(arg, index)
  const [m, setM] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { if (r.repo && !r.graph) codeMap(r.repo).then(setM, (e) => setError(e.message)) }, [r.repo])
  if (r.graph) return <GraphifyPage repo={r.repo} />
  if (!r.repo) return <NoMap t={t} />
  if (error) return <div className="page"><Aviso tone="error" title={t('error')} detail={error} /></div>
  if (!m) return <div className="page"><Skeleton lines={5} /></div>
  const view = codeView(m, r.mode, r.id)
  const open = view === 'group' && singleFolder(m, r.id, r.sub, r.repo)
  if (open) { location.replace(open); return null }
  return <MapView repo={r.repo} m={m} view={view} id={r.id} sub={r.sub} t={t} />
}

function MapView({ repo, m, view, id, sub, t }) {
  const canvas = useRef(null)
  const [noVis, setNoVis] = useState(false)
  useEffect(() => {
    let net = null
    loadVis().then((ok) => {
      if (!ok || !canvas.current) { setNoVis(!ok); return }
      const g = graphModel(m, view, id, sub, themeLook(t))
      net = new window.vis.Network(canvas.current, { nodes: g.nodes, edges: g.edges }, {
        layout: g.layered ? { hierarchical: { enabled: true, direction: g.direction, sortMethod: 'directed', shakeTowards: 'roots',
          levelSeparation: view === 'map' ? 130 : 300, nodeSpacing: view === 'map' ? 180 : 60, treeSpacing: 120 } } : { improvedLayout: true },
        physics: g.layered ? false : { solver: 'forceAtlas2Based', forceAtlas2Based: { gravitationalConstant: -120, springLength: 160, avoidOverlap: 0.8 },
          stabilization: { iterations: 300, fit: true } },
        edges: { scaling: { min: 1, max: 7 }, smooth: g.layered
          ? { type: 'cubicBezier', forceDirection: view === 'map' ? 'vertical' : 'horizontal', roundness: 0.5 } : { type: 'continuous' } },
        interaction: { hover: true, tooltipDelay: 150, zoomView: true, dragView: true, keyboard: false },
      })
      if (g.layered) net.once('afterDrawing', () => net.fit({ animation: false }))
      else net.once('stabilizationIterationsDone', () => { net.setOptions({ physics: false }); net.fit({ animation: { duration: 250 } }) })
      net.on('click', (p) => {
        const n = p.nodes[0]
        if (!n) return
        if (n[0] === 's') location.hash = subHref(repo, id, sub ? `${sub}/${n.slice(1)}` : n.slice(1))
        else location.hash = `#/code/${repo}/${n[0] === 'g' ? 'g' : 'f'}/${n.slice(1)}`
      })
    })
    return () => net?.destroy()
  }, [repo, view, id, sub])
  const title = view === 'file' ? m.files[id].label : view === 'group' ? m.groups[id].label + (sub ? '/' + sub : '') : repo
  const crumbs = codeCrumbs(repo, m, view, id, sub)
  return (
    <div className="codemap">
      <div className="code-head">
        <div>
          {crumbs.length > 1 && <nav className="crumbs" aria-label={t('codeTab')}>{crumbs.map((c, i) => (
            <span key={c.href}>{i > 0 && <span className="sep" aria-hidden="true">›</span>}<a href={c.href}>{c.label}</a></span>))}</nav>}
          <h1>{title}</h1>
          <div className="meta">
            {view === 'file' ? <code className="file">{m.files[id].path}</code> : <>
              <Chip>{t('statFiles', { n: view === 'group' ? inSub(m, id, sub).length : m.stats.files })}</Chip>
              {view === 'map' && <Chip>{t('statModules', { n: m.stats.groups })}</Chip>}</>}
            <span className="muted small">{t('codeHint')}</span>
          </div>
        </div>
        <FileSearch repo={repo} m={m} t={t} />
      </div>
      <div className="code-body">
        <div ref={canvas} className="cm-canvas" role="img" aria-label={title}>
          {noVis && <p className="muted pad">{t('noVis')}</p>}
        </div>
        <aside className="cm-info"><Info repo={repo} m={m} view={view} id={id} sub={sub} t={t} /></aside>
      </div>
    </div>
  )
}

function FileSearch({ repo, m, t }) {
  const [q, setQ] = useState('')
  const hits = searchFiles(m, q)
  const go = (i) => { location.hash = `#/code/${repo}/f/${i}` }
  return (
    <div className="code-search">
      <input type="search" value={q} placeholder={t('findClass')} aria-label={t('findClass')} autoComplete="off"
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && hits[0]) go(hits[0][0]); if (e.key === 'Escape') setQ('') }} />
      {hits.length > 0 && (
        <div className="cs-list">{hits.map(([i, f]) => (
          <a key={i} href={`#/code/${repo}/f/${i}`}><b>{f.label}</b><span className="muted small">{m.groups[f.group].label}</span></a>))}</div>
      )}
    </div>
  )
}

function FileLink({ repo, m, i, w }) {
  return (
    <a href={`#/code/${repo}/f/${i}`} title={m.files[i].path}>
      <span className="swatch" style={swatch(m.files[i].group)}></span>{m.files[i].label}{w ? <span className="count">{w}</span> : null}</a>
  )
}

function Info({ repo, m, view, id, sub, t }) {
  if (view === 'file') {
    const f = m.files[id]
    const list = (rows, title) => (
      <><h3>{title} <span className="count">{rows.length}</span></h3>
        {rows.length ? rows.map(([i, w]) => <FileLink key={i} repo={repo} m={m} i={i} w={w} />) : <p className="muted small">{t('none')}</p>}</>
    )
    return <>{list(f.out, t('uses'))}{list(f.in, t('usedBy'))}</>
  }
  if (view === 'group') {
    const files = inSub(m, id, sub)
    const segs = [...new Set(files.map(([, f]) => nextSeg(f, sub)).filter(Boolean))].sort()
    return (
      <>
        {segs.length > 0 && <><h3>{t('packages')} <span className="count">{segs.length}</span></h3>
          {segs.map((seg) => <a key={seg} href={subHref(repo, id, sub ? `${sub}/${seg}` : seg)}>{seg}/
            <span className="count">{files.filter(([, f]) => nextSeg(f, sub) === seg).length}</span></a>)}</>}
        <h3>{t('filesIn')} <span className="count">{files.length}</span></h3>
        {files.map(([i]) => <FileLink key={i} repo={repo} m={m} i={i} />)}
      </>
    )
  }
  return (
    <>
      <h3>{t('coreFiles')}</h3><p className="muted small">{t('coreHelp')}</p>
      {m.core.map((i) => <FileLink key={i} repo={repo} m={m} i={i} />)}
      <h3>{t('modules')}</h3>
      {m.groups.slice().sort((a, b) => b.files - a.files).map((g) => (
        <a key={g.id} href={`#/code/${repo}/g/${g.id}`}><span className="swatch" style={swatch(g.id)}></span>{g.label}
          <span className="count">{g.files}</span></a>))}
    </>
  )
}

function NoMap({ t }) {
  const [v, setV] = useState(null)
  const build = useBuild()
  useEffect(() => { docsGet('viewers').then(setV, () => setV({})) }, [])
  const can = runs() && v?.graphify
  return (
    <div className="page">
      <h1>{t('codeTab')}</h1>
      <EmptyState title={t('noCodeMap')} action={can
        ? <Button variant="primary" disabled={build.running} onClick={() => build.start('graph').then((s) => { if (s?.status === 'done') location.reload() })}>{t('build')}</Button>
        : <Button href="#/c4">{t('c4')}</Button>}>
        {core.mode() === 'live' ? t('appOnly') : runs() && v && !v.graphify ? t('noGraphify') : null}
      </EmptyState>
      {build.job && <pre className="joblog">{build.job.lines.join('\n')}</pre>}
    </div>
  )
}

// graphify's own page for a repo (or all of them), with when it was built and, in the app, a rebuild.
function GraphifyPage({ repo }) {
  const t = core.t
  const [v, setV] = useState(null)
  const build = useBuild()
  useEffect(() => { docsGet('viewers').then(setV, () => setV({ graphs: {} })) }, [])
  if (!v) return <div className="page"><Skeleton lines={3} /></div>
  const names = Object.keys(v.graphs || {})
  const name = names.includes(repo) ? repo : names[0] || ''
  const g = v.graphs?.[name]
  const src = name === 'all' ? 'code-graph/' : `code-graph/${encodeURIComponent(name)}/`
  return (
    <>
      <div className="vbar">
        <b>{t('code')}</b>
        {names.length > 0 && (
          <select aria-label={t('code')} value={name} onChange={(e) => { location.hash = `#/code/${e.target.value}/graph` }}>
            {names.map((n) => <option key={n} value={n}>{n === 'all' ? t('allRepos') : n}</option>)}</select>
        )}
        {g ? <span className="muted small">{t('builtAt', { when: core.ago(g.at) })}{g.stale && <> · <span className="warn">{t('stale')}</span></>}</span>
          : <span className="muted small">{t('noGraph')}</span>}
        {g && <a href={src} target="_blank" rel="noopener">{t('openTab')} <span aria-hidden="true">↗</span></a>}
        {runs() && v.graphify && <Button size="sm" disabled={build.running}
          onClick={() => build.start('graph').then((s) => { if (s?.status === 'done') location.reload() })}>{t(names.length ? 'rebuild' : 'build')}</Button>}
        {build.job && <pre className="joblog inline">{build.job.lines.slice(-3).join('\n')}</pre>}
      </div>
      {g && <iframe className="viewer" src={src} title={t('code')}></iframe>}
    </>
  )
}

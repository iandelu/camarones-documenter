import { useEffect, useMemo, useState } from 'react'
import { Button, Skeleton } from '@camaron/ui'
import { chapters, guideAt, guideHref, inline, linkTarget, parse, searchGuides } from '../guide.js'
import { inPanel, sectionFor } from '../catalog.js'
import { portalUrl } from '../docs.js'
import { useHash } from '../hooks.js'
import { Failed, Page } from '../parts.jsx'
import { catalog } from './Commands.jsx'
import { lang, t } from '../i18n.js'

// The kit's guides (lib/guide.py, from the installed kit): how to use Camarón, this app, the portal and how it works
// inside. Rendered from blocks (guide.js) as React elements; the markers become buttons that go where the text says.

const CACHE = {}                                    // per window and language: the guides do not change while it is open
export const loadGuides = (srv) => (CACHE[lang()] ||= srv.get('app/guide', { lang: lang() })
  .then((r) => r.guides.map((g) => ({ ...g, blocks: parse(g.markdown) })))
  .catch((e) => { delete CACHE[lang()]; throw e }))

const KEY = 'dk.guide.at'
const recall = () => { try { return localStorage.getItem(KEY) || '' } catch { return '' } }
const remember = (v) => { try { localStorage.setItem(KEY, v) } catch { /* a private window keeps nothing: fine */ } }

// Where a marker goes from this window; null when this window cannot go there (Kit dev outside a kit checkout, a
// command the catalog does not list or has not sent yet, a tour that does not exist).
export function markerAction({ kind, target }, { sections = [], commands = [], tours = [] }) {
  if (kind === 'go') return sections.includes(target) ? { label: t('gd.go', { s: t('nav.' + target) }), href: `#/${target}` } : null
  if (kind === 'cmd') {
    const c = commands.find((x) => x.name === target)
    const s = c && sectionFor(c, sections)
    return s ? { label: t('gd.cmd', { c: target }), href: inPanel(c) ? `#/${s}` : `#/${s}/${target}` } : null
  }
  if (kind === 'portal') return /^#\//.test(target) ? { label: t('gd.portal'), portal: target } : null
  if (kind === 'tour') return tours.includes(target) ? { label: t('gd.tour'), tour: target } : null
  return null
}

export default function Guide({ srv, app, sections = [], tours = [], onTour }) {
  const hash = useHash()
  const [guides, setGuides] = useState(null)
  const [error, setError] = useState('')
  const [commands, setCommands] = useState([])
  const load = () => loadGuides(srv).then((g) => { setGuides(g); setError('') }, (e) => setError(e.message))
  useEffect(() => { load(); catalog(srv).then((c) => setCommands(c.commands), () => {}) }, [])
  let at = guideAt(hash)
  if (!at.name) {
    const [name = '', ...rest] = recall().split('/')
    at = { name, anchor: rest.join('/') }
  }
  useEffect(() => {
    if (!guides) return
    remember(`${at.name}/${at.anchor}`)
    const el = at.anchor && document.getElementById('g-' + at.anchor)
    if (el) el.scrollIntoView({ block: 'start' })
    else document.getElementById('main')?.scrollTo?.(0, 0)
  }, [guides, at.name, at.anchor])
  if (error) return <Page title={t('gd.title')}><Failed title={t('gd.failed')} detail={error} onRetry={() => { setError(''); load() }} /></Page>
  if (!guides) return <Page title={t('gd.title')}><Skeleton lines={8} /></Page>
  if (!guides.length) return <Page title={t('gd.title')}><p className="muted">{t('gd.empty')}</p></Page>
  return (
    <GuideView guides={guides} at={at} sections={sections} commands={commands} tours={tours} onTour={onTour}
      onPortal={(h) => app.openExternal?.(portalUrl(location.origin, h))} onExternal={(href) => app.openExternal?.(href)} />
  )
}

export function GuideView({ guides, at, sections, commands, tours = [], onPortal, onTour, onExternal }) {
  const [q, setQ] = useState('')
  const g = guides.find((x) => x.name === at.name) || guides[0]
  const hits = useMemo(() => searchGuides(guides, q), [guides, q])
  const toc = chapters(g.blocks)
  const current = toc.find((c) => c.id === at.anchor || c.sections.some((s) => s.id === at.anchor))?.id
  const ctx = { sections, commands, tours, names: guides.map((x) => x.name), guide: g.name, onPortal, onTour, onExternal }
  const searching = q.trim().length >= 2
  return (
    <Page title={t('gd.title')} wide>
      <p className="muted">{t('gd.lead')}</p>
      <div className="dk-guide-tabs" role="tablist" aria-label={t('gd.title')}>
        {guides.map((x) => (
          <a key={x.name} role="tab" aria-selected={x.name === g.name ? 'true' : 'false'} href={guideHref(x.name)}
            className={'dk-guide-tab' + (x.name === g.name ? ' on' : '')}>{x.title}</a>))}
      </div>
      <div className="dk-guide-find">
        <label className="cu-field-label" htmlFor="gd-q">{t('gd.search')}</label>
        <input id="gd-q" type="search" className="cu-input" value={q} placeholder={t('gd.searchPh')}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && hits[0]) { location.hash = guideHref(hits[0].name, hits[0].id); setQ('') } }} />
        {searching ? (hits.length ? (
          <ul className="dk-guide-hits" aria-label={t('gd.results', { n: hits.length })}>
            {hits.map((h) => (
              <li key={`${h.name}/${h.id}`}><a href={guideHref(h.name, h.id)} onClick={() => setQ('')}>
                <b>{h.title}</b> <span className="muted small">{h.guideTitle}{h.chapter && h.chapter !== h.title ? ` › ${h.chapter}` : ''}</span>
                {h.snippet ? <span className="small dk-guide-snip">{h.snippet}</span> : null}</a></li>))}
          </ul>) : <p className="muted small">{t('gd.none')}</p>) : null}
      </div>
      <div className="dk-guide">
        <nav className="dk-guide-index" aria-label={t('gd.index')}>
          <span className="eyebrow">{t('gd.index')}</span>
          <ol>{toc.map((c) => (
            <li key={c.id}><a href={guideHref(g.name, c.id)} aria-current={c.id === current ? 'true' : undefined}><Inline text={c.text} ctx={ctx} plain /></a>
              {c.id === current && c.sections.length ? (
                <ol>{c.sections.map((s) => <li key={s.id}><a href={guideHref(g.name, s.id)}><Inline text={s.text} ctx={ctx} plain /></a></li>)}</ol>
              ) : null}</li>))}</ol>
        </nav>
        <article className="dk-guide-doc">
          {g.description ? <p className="dk-guide-lede">{g.description}</p> : null}
          <Blocks blocks={g.blocks} ctx={ctx} />
        </article>
      </div>
    </Page>
  )
}

const Blocks = ({ blocks, ctx }) => blocks.map((b, i) => <Block key={i} b={b} ctx={ctx} />)

function Block({ b, ctx }) {
  if (b.t === 'h') {
    const H = `h${b.level}`
    return <H id={'g-' + b.id} className="dk-guide-h"><Inline text={b.text} ctx={ctx} /></H>
  }
  if (b.t === 'p') return <p><Inline text={b.text} ctx={ctx} /></p>
  if (b.t === 'ul' || b.t === 'ol') {
    const L = b.t
    return <L>{b.items.map((it, i) => (
      <li key={i}><Inline text={it.text} ctx={ctx} />
        {it.items ? <ul>{it.items.map((x, j) => <li key={j}><Inline text={x.text} ctx={ctx} /></li>)}</ul> : null}</li>))}</L>
  }
  if (b.t === 'table') return (
    <div className="dk-guide-table"><table className="dk-table">
      <thead><tr>{b.head.map((c, i) => <th key={i} scope="col"><Inline text={c} ctx={ctx} /></th>)}</tr></thead>
      <tbody>{b.rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}><Inline text={c} ctx={ctx} /></td>)}</tr>)}</tbody>
    </table></div>
  )
  if (b.t === 'code') return <Code text={b.text} />
  if (b.t === 'quote') return (
    <blockquote className={'dk-callout' + (b.kind ? ' ' + b.kind : '')}>
      {b.kind ? <b className="dk-callout-title">{t('gd.' + b.kind)}</b> : null}<Blocks blocks={b.blocks} ctx={ctx} /></blockquote>
  )
  if (b.t === 'actions') {
    const acts = b.items.map((it) => markerAction(it, ctx)).filter(Boolean)
    return acts.length ? <div className="row dk-guide-acts">{acts.map((a, i) => <Act key={i} a={a} ctx={ctx} />)}</div> : null
  }
  return null
}

function Act({ a, ctx }) {
  if (a.href) return <Button size="sm" href={a.href}>{a.label}</Button>
  if (a.portal) return <Button size="sm" variant="ghost" onClick={() => ctx.onPortal?.(a.portal)}>{a.label} ↗</Button>
  return <Button size="sm" variant="primary" onClick={() => ctx.onTour?.(a.tour)}>{a.label}</Button>
}

function Code({ text }) {
  const [done, setDone] = useState(false)
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1500) } catch { /* no clipboard: the text is there to select */ }
  }
  return (
    <div className="dk-guide-code"><pre><code>{text}</code></pre>
      <Button size="sm" variant="ghost" onClick={copy}>{done ? t('gd.copied') : t('gd.copy')}</Button></div>
  )
}

// Inline Markdown as elements; HTML other than <kbd> is shown as the text it is. `plain` keeps links as text (the index).
function Inline({ text, ctx, plain = false }) {
  return inline(text).map((k, i) => {
    if (k.t === 'code') return <code key={i}>{k.text}</code>
    if (k.t === 'kbd') return <kbd key={i}>{k.text}</kbd>
    if (k.t === 'b') return <strong key={i}><Inline text={k.text} ctx={ctx} plain={plain} /></strong>
    if (k.t === 'i') return <em key={i}><Inline text={k.text} ctx={ctx} plain={plain} /></em>
    if (k.t !== 'a') return k.text
    const inner = <Inline text={k.text} ctx={ctx} plain />
    const to = !plain && linkTarget(k.href, ctx.names)
    if (!to) return <span key={i}>{inner}</span>
    if (to.kind === 'guide') return <a key={i} href={guideHref(to.name, to.anchor)}>{inner}</a>
    if (to.kind === 'anchor') return <a key={i} href={guideHref(ctx.guide, to.anchor)}>{inner}</a>
    return <a key={i} href={to.href} onClick={(e) => { e.preventDefault(); ctx.onExternal?.(to.href) }}>{inner} ↗</a>
  })
}

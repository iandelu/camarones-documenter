import { docsTrees, sortedDirs, byTitle } from './tree.js'
import { core } from '../core.js'


// The reader's audience: everything, or the Business view (`:::tech` blocks hidden, the tree keeps what the system
// does and why). Stored as before (cam-audience); <body data-audience> drives the blocks' CSS.
export function audience() {
  try { return localStorage.getItem('cam-audience') || 'all' } catch { return 'all' }
}
export function setAudience(a) {
  try { localStorage.setItem('cam-audience', a) } catch { /* private mode */ }
  document.body.dataset.audience = a
}

// The docs trees and reading orders for the current reader (language, audience) and page.
export function readerTrees(active = '') {
  const index = core.tree()
  return docsTrees(index.docs || [], { sections: index.sections || [], lang: core.lang(), business: audience() === 'business', active })
}

// The docs tree in the sidebar: the docs home, the root pages, one group per section, working notes folded last.
export default function DocsTree({ active = '', onChange }) {
  const t = core.t
  const index = core.tree()
  const sections = index.sections || []
  const lang = core.lang()
  const { docs, notes, notesOrder } = readerTrees(active)
  const leaf = (d, label) => (
    <a key={d.path} href={core.hrefFor(d.path)} className={d.path === active ? 'on' : ''} title={t('trust.' + d.trust)}
      aria-current={d.path === active ? 'page' : undefined}>
      <span className={'dot ' + (d.trust || '')} aria-hidden="true"></span>{label || d.title}</a>
  )
  const node = (n) => [
    ...n.pages.slice().sort(byTitle(lang)).map((d) => leaf(d)),
    ...sortedDirs(n, sections).map((c) => {
      if (!c.index && !Object.keys(c.dirs).length && c.pages.length === 1) return leaf(c.pages[0])
      const label = c.index
        ? <a href={core.hrefFor(c.index.path)} className={c.index.path === active ? 'on' : ''}>{c.name}</a> : <span>{c.name}</span>
      return (
        <details key={c.path} open={active.startsWith(c.path + '/')}>
          <summary>{label}</summary><div className="sub">{node(c)}</div>
        </details>
      )
    }),
  ]
  // (not up to content/doc.js's document-wide handler for the in-page switches)
  const pick = (a) => (e) => { e.stopPropagation(); if (a !== audience()) { setAudience(a); onChange?.() } }
  const aud = audience()
  return (
    <div className="docs-tree">
      <div className="audience seg side-audience" role="group" title={t('audienceHint')} aria-label={t('audienceHint')}>
        <button type="button" className={aud === 'all' ? 'on' : ''} aria-pressed={aud === 'all'} onClick={pick('all')}>{t('audienceAll')}</button>
        <button type="button" className={aud === 'business' ? 'on' : ''} aria-pressed={aud === 'business'} onClick={pick('business')}>{t('audienceBusiness')}</button>
      </div>
      {core.mode() !== 'static' && <a href="#/new" className="button ghost small newpage">{t('newPage').replace(/^\+\s*/, '')}</a>}
      <nav aria-label={t('docs')}>
        <div className="group"><a href="#/docs" className={!active ? 'on' : ''} aria-current={!active ? 'page' : undefined}>{t('docsHome')}</a></div>
        {docs.pages.length > 0 && (
          <div className="group"><div className="group-title">{t('general')}</div>{node({ ...docs, dirs: {} })}</div>
        )}
        {sortedDirs(docs, sections).map((n) => (
          <div className="group" key={n.path}>
            {n.index
              ? <a className={'group-title' + (n.index.path === active ? ' on' : '')} href={core.hrefFor(n.index.path)}>{core.sectionLabel(n.name)}</a>
              : <div className="group-title">{core.sectionLabel(n.name)}</div>}
            {node({ ...n, index: null })}
          </div>
        ))}
        {notesOrder.length > 0 && (
          <details className="notes" open={core.byPath(active)?.space === 'notes'}>
            <summary>{t('notes')} <span className="count">{notesOrder.length}</span></summary>
            <p className="muted small">{t('notesHelp')}</p>
            <div className="sub">{node(notes)}</div>
          </details>
        )}
      </nav>
    </div>
  )
}

import { useState } from 'react'
import { core } from '../core.js'
import { IDES, groupSources, lineLabel, openTarget, splitPath } from './sources.js'

const OPEN_KEY = 'cam-open-in'
const readOpen = () => { try { return localStorage.getItem(OPEN_KEY) || 'vscode' } catch { return 'vscode' } }
const saveOpen = (v) => { try { localStorage.setItem(OPEN_KEY, v) } catch { /* private mode */ } }

// One icon per freshness state (fresh | changed | missing | unchecked), drawn in currentColor; the CSS colours it and
// gives the out-of-date ones a soft pulse.
export function FreshIcon({ state }) {
  return (
    <span className="fresh-ico" data-state={state} aria-hidden="true">
      <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="8" cy="8" r="6.2" strokeDasharray={state === 'unchecked' ? '2.2 2.2' : undefined} />
        {state === 'fresh' && <path d="M5.3 8.3l1.8 1.8 3.6-3.8" />}
        {state === 'changed' && <><path d="M8 4.9v3.6" /><circle cx="8" cy="11" r=".5" fill="currentColor" /></>}
        {state === 'missing' && <path d="M6 6l4 4M10 6l-4 4" />}
      </svg>
    </span>
  )
}

// The page's sources, grouped by repo: a click opens the cited lines (the reader's editor on this machine, the forge
// from the deployed portal); hover or focus tells how fresh each one is and which commits, pull requests and tickets
// changed it since the page was written.
export default function Sources({ entries, refs }) {
  const t = core.t
  const [open, setOpen] = useState(readOpen)
  const list = entries?.length ? entries : refs.map((ref) => ({ ref, kind: 'code', repo: '', path: ref, state: 'unchecked' }))
  const local = list.some((e) => e.file)
  const forge = list.some((e) => e.url)
  const pick = (v) => { setOpen(v); saveOpen(v) }
  return (
    <div className="cu-card doc-sources">
      <div className="src-head">
        <span className="eyebrow">{t('sources')} · {list.length}</span>
        {local && (
          <label className="src-open">
            <span className="sr-only">{t('src.openIn')}</span>
            <select value={open} onChange={(e) => pick(e.target.value)} title={t('src.openIn')}>
              {IDES.map((i) => <option key={i.id} value={i.id}>{i.label}</option>)}
              {forge && <option value="repo">{t('src.repo')}</option>}
            </select>
          </label>
        )}
      </div>
      {groupSources(list).map((g) => (
        <section key={g.key} className="src-group">
          <span className="src-repo">{g.key === 'docs' ? t('src.pages') : g.key === 'c4' ? t('src.c4') : g.key}</span>
          <ul>{g.items.map((e, i) => <Source key={e.ref} e={e} open={open} id={`src-${g.key}-${i}`} t={t} />)}</ul>
        </section>
      ))}
    </div>
  )
}

function Source({ e, open, id, t }) {
  const target = e.kind === 'doc' ? { href: core.hrefFor(e.page), external: false, where: 'page' } : openTarget(e, open)
  const { dir, name } = e.kind === 'doc' ? splitPath(e.page) : e.kind === 'c4' ? { dir: '', name: e.name } : splitPath(e.path || e.ref)
  const lines = lineLabel(e)
  const ide = IDES.find((i) => i.id === open) || IDES[0]
  const body = (
    <>
      <FreshIcon state={e.state} />
      <span className="src-text">
        <span className="src-name"><span className="src-file">{name}</span>{lines && <span className="src-lines">{lines}</span>}</span>
        {dir && <span className="src-dir">{dir}</span>}
      </span>
    </>
  )
  const label = `${e.ref} — ${t('src.state.' + e.state)}`
  return (
    <li className="src-item" data-state={e.state}>
      {target
        ? <a className="src-link" href={target.href} aria-describedby={id} aria-label={label}
            {...(target.external ? { target: '_blank', rel: 'noopener' } : {})}>{body}</a>
        : <span className="src-link" tabIndex={0} aria-describedby={id} aria-label={label}>{body}</span>}
      <div className="src-pop" role="tooltip" id={id}>
        <div className="src-pop-in">
          <div className="src-pop-head"><FreshIcon state={e.state} /><b>{t('src.state.' + e.state)}</b></div>
          <code className="src-ref">{e.ref}</code>
          {e.since && <p className="small muted">{t('src.since', { date: String(e.since).slice(0, 10) })}</p>}
          {e.commits?.length > 0 && (
            <>
              <span className="eyebrow">{t('src.commits')}</span>
              <ul className="src-commits">{e.commits.map((c) => <Commit key={c.sha} c={c} />)}</ul>
            </>
          )}
          {e.dirty && <p className="small">{t('src.dirty')}</p>}
          {(e.state === 'changed' || e.state === 'missing') && !e.commits?.length && !e.dirty && e.kind !== 'doc' && e.kind !== 'c4' &&
            <p className="small muted">{t('src.noHistory')}</p>}
          {target?.where === 'ide' && e.url && <a className="small" href={e.url} target="_blank" rel="noopener">{t('src.openRepo')} ↗</a>}
          {target?.where === 'repo' && e.file && <a className="small" href={ide.href(e.file, e.line || 1)}>{t('src.openIde', { ide: ide.label })} →</a>}
        </div>
      </div>
    </li>
  )
}

function Commit({ c }) {
  const ext = { target: '_blank', rel: 'noopener' }
  return (
    <li>
      <div className="src-commit">
        {c.url ? <a className="src-sha" href={c.url} {...ext}>{c.short}</a> : <code className="src-sha">{c.short}</code>}
        <span className="src-subject" title={c.subject}>{c.title || c.subject}</span>
      </div>
      <div className="src-tags">
        {c.pr && (c.pr.url ? <a className="src-tag pr" href={c.pr.url} {...ext}>#{c.pr.n} ↗</a> : <span className="src-tag pr">#{c.pr.n}</span>)}
        {c.tasks.map((k) => <span key={k} className="src-tag">{k}</span>)}
        <span className="small muted">{c.author} · {String(c.at).slice(0, 10)}</span>
      </div>
    </li>
  )
}

import { Button, EmptyState, fmtAgo, uiText } from '@camaron/ui'
import { counts, FILTERS, filterRows } from '../../adr.js'
import { lang, t } from '../../i18n.js'
import { Page } from '../../parts.jsx'
import { StatusChip, chipOf, kindWord } from './Read.jsx'

// The list (spec §2.1): Candidatas · N and Nuevo ADR beside the title, the filters with their counts and a search,
// one row per ADR (the rows of GET app/adr), and the decisions the code took without one as a strip under them.
// `candidates` is null while it is read (or when it could not be: the candidates screen says why).

const NAMED = 3
const EDGE = ['review', 'running']        // the rows that still ask for something

function day(iso, l, now) {
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00`)
  if (Number.isNaN(+d)) return String(iso)
  const year = d.getFullYear() === new Date(now).getFullYear() ? {} : { year: 'numeric' }
  return new Intl.DateTimeFormat(l, { day: 'numeric', month: 'short', ...year }).format(d)
}

function when(r, l, now) {
  if (r.decided) return t('adr.decidedOn', { date: day(r.decided, l, now) })
  return r.updated && !Number.isNaN(Date.parse(r.updated)) ? fmtAgo(r.updated, now, (k) => uiText(k, l)) : ''
}

function Row({ r, now }) {
  const l = lang()
  const points = r.points?.total ? t('adr.points', { decided: r.points.decided || 0, total: r.points.total }) : ''
  const meta = [kindWord(r), (r.repos || []).join(', '), points, when(r, l, now)].filter(Boolean).join(' · ')
  const chip = chipOf(r)
  return (
    <li>
      <a className={'dk-adr-row' + (EDGE.includes(chip) ? ` is-${chip}` : '')} href={`#/decisions/${r.id}`}>
        <span className="dk-adr-id">{r.id}</span>
        <span className="dk-adr-main">
          <span className="dk-adr-title">{r.title || r.id}</span>
          {meta ? <span className="dk-adr-meta">{meta}</span> : null}
        </span>
        <StatusChip chip={chip} />
      </a>
    </li>
  )
}

function Strip({ list }) {
  const names = list.map((c) => c?.label).filter(Boolean)
  const named = names.slice(0, NAMED).join(', ') + (names.length > NAMED ? '…' : '')
  return (
    <div className="dk-adr-strip">
      <p><strong>{t(list.length === 1 ? 'adr.cand.one' : 'adr.cand.many', { n: list.length })}</strong>
        {named ? <span className="muted">{` — ${named}`}</span> : null}</p>
      <Button size="sm" href="#/decisions/candidates">{t('adr.cand.review')}</Button>
    </div>
  )
}

function NoMatch({ q, filter, onFilter }) {
  const name = t(`adr.filter.${filter}`)
  const query = String(q ?? '').trim()
  return (
    <div className="dk-adr-none" role="status">
      <p>{query ? t('adr.noMatch', { q: query, filter: name }) : t('adr.noneIn', { filter: name })}</p>
      {filter !== 'all' ? <Button size="sm" onClick={() => onFilter('all')}>{t('adr.showAll')}</Button> : null}
    </div>
  )
}

export function AdrListView({ rows, filter = 'all', q = '', onFilter, onQ, candidates = null, now = Date.now() }) {
  const all = rows || []
  const cands = Array.isArray(candidates) ? candidates : null
  const strip = cands?.length ? <Strip list={cands} /> : null
  const create = <Button variant="primary" href="#/decisions/new"><span aria-hidden="true">+</span> {t('adr.new')}</Button>
  if (!all.length) return (
    <Page title={t('nav.decisions')}>
      <EmptyState title={t('adr.empty.title')} action={create}>{t('adr.empty.body')}</EmptyState>
      {strip}
    </Page>
  )
  const n = counts(all)
  const shown = filterRows(all, filter, q)
  const actions = (<>
    <Button href="#/decisions/candidates">{cands ? t('adr.cand.button', { n: cands.length }) : t('adr.cand.title')}</Button>
    {create}
  </>)
  return (
    <Page title={t('nav.decisions')} actions={actions}>
      <div className="dk-adr-bar">
        <div className="dk-adr-filters" role="group" aria-label={t('adr.filters')}>
          {FILTERS.map((f) => (
            <button key={f} type="button" className="dk-adr-filter" aria-pressed={filter === f} onClick={() => onFilter(f)}>
              {`${t(`adr.filter.${f}`)} `}<span className="dk-adr-n">{n[f]}</span>
            </button>
          ))}
        </div>
        <div className="dk-adr-find">
          <span aria-hidden="true">⌕</span>
          <input type="search" className="cu-input" value={q} placeholder={t('adr.searchPh')} aria-label={t('adr.search')}
            onChange={(e) => onQ(e.target.value)} onKeyDown={(e) => { if (e.key === 'Escape' && q) { e.stopPropagation(); onQ('') } }} />
        </div>
      </div>
      {shown.length ? (
        <ul className="dk-adr-list" aria-label={t('adr.list')}>{shown.map((r) => <Row key={r.id} r={r} now={now} />)}</ul>
      ) : <NoMatch q={q} filter={filter} onFilter={onFilter} />}
      {strip}
    </Page>
  )
}

import { Button, EmptyState } from '@camaron/ui'
import { S, t } from '../../i18n.js'
import { Page } from '../../parts.jsx'

// Candidatas (spec §4.4): the decisions the code already took that no ADR names (GET app/adr/candidates), grouped by
// what they are. Each one opens the new-ADR form as a retroactive ADR, its title a question and Toca its manifests.

const ORDER = ['data', 'cache', 'messaging', 'security', 'framework', 'deploy', 'c4']     // lib/adr_pack.py
const rank = (c) => { const at = ORDER.indexOf(c); return at < 0 ? ORDER.length : at }
const catName = (c) => { const key = `adr.cat.${c}`; const word = t(key); return word === key ? c : word }

// The form's prefill for a candidate, in the language given (the title is the person's text from then on).
export function candidateFields(c, lang) {
  const why = (S[lang] || S.es)['adr.cand.why']
  return { kind: 'retro', title: why.replace('{label}', c?.label || c?.key || ''), touches: [...(c?.manifests || [])] }
}

function Candidate({ c, onPick }) {
  const files = c.manifests || []
  const meta = [(c.repos || []).join(', '), files[0], files.length > 1 ? t('adr.cand.more', { n: files.length - 1 }) : '']
  return (
    <li className="dk-adr-cand">
      <span className="dk-adr-main">
        <span className="dk-adr-title">{c.label || c.key}</span>
        <span className="dk-adr-meta">{meta.filter(Boolean).join(' · ')}</span>
      </span>
      <Button size="sm" onClick={() => onPick(c)}>{t('adr.cand.create')}</Button>
    </li>
  )
}

export function CandidatesView({ rows, onPick }) {
  const list = rows || []
  if (!list.length) return (
    <Page title={t('adr.cand.title')}>
      <EmptyState title={t('adr.cand.none')} action={
        <div className="row"><Button variant="primary" href="#/decisions/new">{t('adr.new')}</Button><Button href="#/libs">{t('adr.cand.libs')}</Button></div>}>
        {t('adr.cand.noneBody')}
      </EmptyState>
    </Page>
  )
  const groups = [...new Set(list.map((c) => c.category || ''))].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b))
  return (
    <Page title={t('adr.cand.title')}>
      <p className="dk-adr-lede">{t('adr.cand.lede')}</p>
      {groups.map((g) => {
        const mine = list.filter((c) => (c.category || '') === g)
        return (
          <section key={g} className="dk-adr-cands" aria-labelledby={`adr-cat-${g}`}>
            <h2 id={`adr-cat-${g}`} className="eyebrow">{catName(g)} <span className="dk-adr-n">{mine.length}</span></h2>
            <ul className="dk-adr-list">{mine.map((c) => <Candidate key={c.key || c.label} c={c} onPick={onPick} />)}</ul>
          </section>
        )
      })}
    </Page>
  )
}

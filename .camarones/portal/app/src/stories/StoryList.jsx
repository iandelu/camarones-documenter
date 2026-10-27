import { useState } from 'react'
import { core } from '../core.js'

// The left column of Historias: "Nueva historia", a search box and every story of the board (not archived) with its
// verdict, recomputed on every read, its subtasks done/total and whether it overlaps another open story.
const t = core.t

export function VerdictBadge({ verdict }) {
  const v = ['good', 'improve', 'poor'].includes(verdict) ? verdict : 'none'
  return <span className={`st-verdict v-${v}`}>{t(`stories.verdict.short.${v}`)}</span>
}

export default function StoryList({ stories, selected, onPick }) {
  const [q, setQ] = useState('')
  const needle = q.trim().toLowerCase()
  const shown = (stories || []).filter((s) => !needle || `${s.id} ${s.title}`.toLowerCase().includes(needle))
  return (
    <nav className="st-list" aria-label={t('stories.list')}>
      <button type="button" className={selected ? 'ghost' : ''} aria-current={selected ? undefined : 'true'}
              onClick={() => onPick(null)}>+ {t('stories.new')}</button>
      <input type="search" className="st-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('stories.search')}
             aria-label={t('stories.search')} />
      {!stories?.length ? <p className="muted small">{t('stories.none')}</p>
        : !shown.length ? <p className="muted small">{t('stories.noMatch', { q })}</p> : (
          <ul>
            {shown.map((s) => (
              <li key={s.id}>
                <button type="button" className={`st-row${selected === s.id ? ' on' : ''}`} aria-current={selected === s.id ? 'true' : undefined}
                        onClick={() => onPick(s.id)}>
                  <span className="st-row-top"><span className="card-id">{s.id}</span><VerdictBadge verdict={s.verdict} />
                    {s.progress?.total ? <span className="muted small">{t('stories.progress', s.progress)}</span> : null}
                    {s.conflicts?.length ? <span className="st-clash" title={t('stories.clash', { ids: s.conflicts.join(', ') })}>
                      {t('stories.clash', { ids: s.conflicts.join(', ') })}</span> : null}</span>
                  <span className="st-row-title">{s.title}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
    </nav>
  )
}

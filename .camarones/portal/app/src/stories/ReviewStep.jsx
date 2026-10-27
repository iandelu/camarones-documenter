import { useId, useRef } from 'react'
import { core } from '../core.js'
import { footprintOf } from '../stories.js'
import { VerdictBadge } from './StoryList.jsx'
import { Suggest } from './Suggest.jsx'

// Step 2, Revisión: the INVEST verdict by rules (one chip per letter, its reason on hover or opened), the criteria
// editor, the overlaps with other open stories, the footprint line and the repos without a code graph.
const t = core.t
const plural = (key, n) => t(`${key}.${n === 1 ? 'one' : 'many'}`, { n })

export function footprintLine(touches, groups) {
  const f = footprintOf(touches, groups)
  return [plural('stories.fp.groups', f.groups), plural('stories.fp.files', f.files), plural('stories.fp.repos', f.repos),
    plural('stories.fp.pages', f.pages)].join(' · ')
}

function Criteria({ draft, change }) {
  const id = useId()
  const list = useRef(null)
  const saved = draft.savedCriteria || 0
  const set = (i, v) => change((d) => ({ ...d, criteria: d.criteria.map((c, j) => (j === i ? v : c)) }))
  const drop = (i) => change((d) => ({ ...d, criteria: d.criteria.filter((_, j) => j !== i) }))
  const add = () => {
    change((d) => ({ ...d, criteria: [...d.criteria, ''] }))
    requestAnimationFrame(() => [...(list.current?.querySelectorAll('input') || [])].pop()?.focus())
  }
  return (
    <div className="st-criteria">
      <h3 id={`${id}-h`}>{t('stories.criteria')}</h3>
      <ul ref={list} aria-labelledby={`${id}-h`}>
        {draft.criteria.map((c, i) => (
          <li key={i}>
            <span className="st-box" aria-hidden="true">☐</span>
            <input value={c} aria-label={t('stories.criteria.n', { n: i + 1 })} placeholder={t('stories.criteria.ph')}
                   readOnly={i < saved} title={i < saved ? t('stories.criteria.saved') : undefined} onChange={(e) => set(i, e.target.value)}
                   onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }} />
            {i >= saved ? <button type="button" className="icon" aria-label={t('stories.criteria.remove', { n: i + 1 })} onClick={() => drop(i)}>✕</button> : null}
          </li>
        ))}
      </ul>
      <button type="button" className="ghost small" onClick={add}>+ {t('stories.criteria.add')}</button>
    </div>
  )
}

export default function ReviewStep({ draft, change, analysis, pending, ai, aiOn, onNext }) {
  const id = useId()
  const inv = analysis?.invest
  return (
    <section className="st-step" aria-labelledby={`${id}-h`} aria-busy={pending || undefined}>
      <h2 id={`${id}-h`}><span className="st-n">2</span> {t('stories.step.2')}</h2>
      {inv ? (
        <>
          <p className="st-verdict-line"><VerdictBadge verdict={inv.verdict} /> {t(`stories.verdict.${inv.verdict}`)}</p>
          <div className="st-letters" role="list" aria-label={t('stories.invest')}>
            {[...'INVEST'].map((l) => {
              const x = inv.letters[l]
              return (
                <details key={l} role="listitem" className={`st-letter ${x.ok ? 'ok' : 'fail'}`}>
                  <summary title={x.reason}><b>{l}</b> {t(`stories.invest.${l}`)} <span aria-hidden="true">{x.ok ? '✓' : '✕'}</span></summary>
                  <p>{x.reason}</p>
                </details>
              )
            })}
          </div>
        </>
      ) : <p className="muted" role="status">{t('stories.block.pending')}</p>}
      <Criteria draft={draft} change={change} />
      <Suggest ai={ai} what="criteria" on={aiOn} onAccept={(c) => change((d) => ({ ...d, criteria: [...d.criteria.filter((x) => x.trim()), c] }))} />
      <h3>{t('stories.footprint')}</h3>
      <p className="st-footprint">{footprintLine(draft.touches, draft.groups)}</p>
      {(analysis?.graphless || []).length ? (
        <p className="aviso st-graphless">{t('stories.graphless', { repos: analysis.graphless.join(', ') })}{' '}
          {t('stories.graphless.how', { cmd: '\u0000' }).split('\u0000').flatMap((part, i) => (i ? [<code key={i}>camaron graph</code>, part] : [part]))}</p>
      ) : null}
      <h3>{t('stories.conflicts')}</h3>
      {analysis?.conflicts?.length ? (
        <ul className="st-conflicts">
          {analysis.conflicts.map((c) => (
            <li key={`${c.id}:${c.kind}`}><b>{c.id}</b> <span className={`st-kind k-${c.kind}`}>
              {c.kind === 'conflict' ? t('stories.kind.conflict', { files: (c.files || []).join(', ') }) : t('stories.kind.near')}</span></li>
          ))}
        </ul>
      ) : analysis ? <p className="muted small">{t('stories.conflicts.none')}</p> : null}
      {onNext ? <button type="button" className="st-next" onClick={onNext}>{t('stories.next')}</button> : null}
    </section>
  )
}

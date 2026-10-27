import { useId } from 'react'
import { core } from '../core.js'
import { lint } from '../stories.js'
import TouchPicker from './TouchPicker.jsx'
import { Suggest } from './Suggest.jsx'

// Step 1, Escribe la historia: Como / quiero / para with the instant hints under each field (the JS port of the kit's
// lint, no server round trip), the title (it follows the want until the person edits it), the epic and Toca.
const t = core.t

function Hints({ id, hints }) {
  if (!hints.length) return null
  return <ul id={id} className="st-hints">{hints.map((h) => <li key={h.code}>{t(`stories.hint.${h.code}`)}</li>)}</ul>
}

export default function WriteStep({ draft, change, words, lang, epics, existing, touchError, ai, aiOn, onNext }) {
  const id = useId()
  const hints = lint(draft.as, draft.want, draft.so, lang, words, draft.touches)
  const on = (field) => hints.filter((h) => h.field === field || (field === 'so' && h.field === 'story'))
  // the hints wait until the person has written or picked something, so a new story does not open scolding
  const started = !!(draft.as || draft.want || draft.so || draft.touches.length)
  const shown = (field) => (started ? on(field) : [])
  const field = (name, label) => {
    const list = shown(name)
    return (
      <div className="st-field">
        <label htmlFor={`${id}-${name}`}>{label}</label>
        <input id={`${id}-${name}`} value={draft[name]} placeholder={t(`stories.${name}.ph`)} aria-invalid={list.length ? true : undefined}
               aria-describedby={list.length ? `${id}-${name}-h` : undefined} onChange={(e) => change({ [name]: e.target.value })} />
        <Hints id={`${id}-${name}-h`} hints={list} />
      </div>
    )
  }
  const epicKnown = !draft.epic || epics.some((e) => e.id === draft.epic)
  return (
    <section className="st-step" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}><span className="st-n">1</span> {t('stories.step.1')}</h2>
      {field('as', t('stories.as'))}
      {field('want', t('stories.want'))}
      {field('so', t('stories.so'))}
      <Suggest ai={ai} what="rewrite" on={aiOn}
               onAccept={(r) => change({ as: r.as_ || draft.as, want: r.want || draft.want, so: r.so || draft.so })} />
      <div className="st-row2">
        <div className="st-field">
          <label htmlFor={`${id}-title`}>{t('stories.title')}</label>
          <input id={`${id}-title`} value={draft.title} maxLength={80} onChange={(e) => change({ title: e.target.value, titleAuto: false })} />
        </div>
        <div className="st-field">
          <label htmlFor={`${id}-epic`}>{t('stories.epic')}</label>
          <select id={`${id}-epic`} value={draft.epic || ''} disabled={existing} aria-describedby={existing ? `${id}-epic-n` : undefined}
                  onChange={(e) => change({ epic: e.target.value })}>
            <option value="">{t('stories.epic.none')}</option>
            {!epicKnown ? <option value={draft.epic}>{draft.epic}</option> : null}
            {epics.map((e) => <option key={e.id} value={e.id}>{e.id} · {e.title}</option>)}
          </select>
          {existing ? <p id={`${id}-epic-n`} className="muted small">{t('stories.epic.fixed')}</p> : null}
        </div>
      </div>
      <TouchPicker touches={draft.touches} groups={draft.groups} label={t('stories.touches')} error={touchError}
                   describedBy={shown('touches').length ? `${id}-touches-h` : undefined}
                   fromDocs={(draft.fromDocs || []).filter((f) => draft.touches.includes(f))} onKeep={() => change({ fromDocs: [] })}
                   onChange={(touches, groups) => change((d) => ({ ...d, touches, groups: { ...d.groups, ...groups },
                     fromDocs: (d.fromDocs || []).filter((f) => touches.includes(f)) }))} />
      <Hints id={`${id}-touches-h`} hints={shown('touches')} />
      {onNext ? <button type="button" className="st-next" onClick={onNext}>{t('stories.next')}</button> : null}
    </section>
  )
}

import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Thinking } from '@camaron/ui'
import { postJSON } from '../api.js'
import { core } from '../core.js'
import { escapeAborts } from '../stories.js'

// "✨ Sugerir con IA" (spec §7): in each place AI helps, always; disabled with the reason when it cannot run (aiGate). A
// suggestion is shown apart, marked IA, and does nothing until the person accepts it; it never decides files,
// dependencies, waves or the verdict. Escape cancels a suggestion on its way. The answer's `missing` means nothing usable came back — broken or nothing new — and the
// page says so plainly, without calling it an error.
const t = core.t
const key = (s) => String(s || '').trim().toLowerCase()

export function useSuggest({ draft, lang, onReadOnly }) {
  const [state, setState] = useState(null)          // {what, running, result, note, error}
  const [gone, setGone] = useState({})              // texts dismissed per kind: never proposed again this session
  const ctrl = useRef(null)
  const stop = useCallback(() => { ctrl.current?.abort() }, [])
  useEffect(() => {
    if (!state?.running) return undefined
    // capture: the key is taken before the form or search box under the focus sees it
    const onKey = (e) => { escapeAborts(e, true, stop) }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [state?.running, stop])
  useEffect(() => () => ctrl.current?.abort(), [])

  async function run(what) {
    ctrl.current?.abort()
    const mine = new AbortController()
    ctrl.current = mine
    const have = what === 'criteria' ? draft.criteria : what === 'tasks' ? (draft.tasks || []).map((x) => x.title) : []
    const exclude = [...have, ...(gone[what] || [])].filter((x) => String(x || '').trim())
    setState({ what, running: true })
    try {
      const res = await postJSON('stories/suggest', { story: { id: draft.id, as: draft.as, want: draft.want, so: draft.so,
        criteria: draft.criteria.filter((c) => c.trim()), touches: draft.touches, epic: draft.epic || null }, what, exclude, lang },
      { signal: mine.signal })
      const empty = (res.missing || []).includes(what)
      setState({ what, result: empty ? null : res, note: empty ? t('stories.ai.nothing') : '' })
    } catch (e) {
      if (e.name === 'AbortError') return setState({ what, note: t('stories.ai.cancelled') })
      if (e.status === 403) onReadOnly()
      setState({ what, error: e.message })
    } finally { if (ctrl.current === mine) ctrl.current = null }
  }
  const dismiss = (what, text) => {
    setGone((g) => ({ ...g, [what]: [...(g[what] || []), text] }))
    setState((s) => {
      if (!s?.result) return s
      const list = what === 'rewrite' ? null : s.result[what].filter((x) => key(x.title ?? x) !== key(text))
      return list && list.length ? { ...s, result: { ...s.result, [what]: list } } : null
    })
  }
  return { state, run, stop, dismiss, clear: () => setState(null) }
}

// The button and, under it, what came back for this kind. While it thinks, the button that started it is the indicator
// (a pending button, as in React Aria): it keeps the focus, shimmers and cannot be pressed again.
export function Suggest({ ai, what, gate, onAccept }) {
  const id = useId()
  const s = ai.state?.what === what ? ai.state : null
  const busy = !!s?.running
  const items = !s?.result ? [] : what === 'rewrite' ? (s.result.rewrite ? [s.result.rewrite] : []) : s.result[what] || []
  const text = (x) => (what === 'rewrite' ? t('stories.ai.rewrite', { as: x.as_, want: x.want, so: x.so }) : x.title ?? x)
  return (
    <div className="st-ai">
      <button type="button" className="ghost small" disabled={!busy && (!gate.on || !!ai.state?.running)}
              aria-disabled={busy || undefined} aria-busy={busy || undefined}
              aria-describedby={gate.on ? undefined : `${id}-why`} onClick={busy ? undefined : () => ai.run(what)}>
        {busy ? <>✨ <Thinking timer>{t('stories.ai.thinking')}</Thinking></>
          : `✨ ${t('stories.ai.suggest')}${gate.runner && gate.on ? ` · ${gate.runner}` : ''}`}</button>
      {gate.on ? null : <span id={`${id}-why`} className="muted small"> {t(gate.why)}</span>}
      {busy ? <span className="muted small" role="status"> <span className="sr-only">{t('stories.ai.thinking')} </span>
        {t('stories.ai.escape')}</span> : null}
      {s?.note ? <span className="muted small" role="status"> {s.note}</span> : null}
      {s?.error ? <p className="error" role="alert">{s.error}</p> : null}
      {items.length ? (
        <ul className="st-ai-list">
          {items.map((x) => (
            <li key={text(x)}>
              <span className="st-ai-badge">{t('stories.ai.badge')}</span>
              <span className="st-ai-text">{text(x)}</span>
              <button type="button" className="small" onClick={() => { onAccept(x); ai.dismiss(what, text(x)) }}>{t('stories.ai.accept')}</button>
              <button type="button" className="ghost small" onClick={() => ai.dismiss(what, text(x))}>{t('stories.ai.dismiss')}</button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

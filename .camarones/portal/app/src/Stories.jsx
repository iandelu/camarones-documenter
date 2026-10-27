import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Skeleton } from '@camaron/ui'
import { getJSON, postJSON } from './api.js'
import { core } from './core.js'
import Failed from './Failed.jsx'
import { analyzeBody, draftKey, dropDraft, initialDraft, loadDraft, mergeDocSources, nextStep, planAnalyze, primaryLabel, saveBlock,
  saveBody, saveDraft, titleFrom, withChecks } from './stories.js'
import StoryList from './stories/StoryList.jsx'
import WriteStep from './stories/WriteStep.jsx'
import ReviewStep from './stories/ReviewStep.jsx'
import TasksStep from './stories/TasksStep.jsx'
import { useSuggest } from './stories/Suggest.jsx'

// Historias (#/stories, spec §2): the stories of the board on the left; on the right one story in three steps — write
// it (with instant hints), review it (INVEST, criteria, footprint, conflicts) and the subtasks it splits into, with
// their dependencies and waves. Everything but Save is local: `analyze` writes nothing and runs 200 ms after a change.
const t = core.t
const lang = () => (core.lang() === 'es' ? 'es' : 'en')
const ANALYZE_MS = 200
const blank = (d) => !d.as.trim() && !d.want.trim() && !d.so.trim() && !d.touches.length

// A draft as the screen keeps it: the helper's draft plus what the screen adds (removed keys, the group of each
// touch, how many criteria are already on the card, whether the title still follows the want).
const fresh = (item) => ({ ...initialDraft(item), removed: [], groups: {}, savedCriteria: item?.criteria?.length || 0,
  titleAuto: !item?.id, step: item?.id ? 3 : 1 })

export default function Stories() {
  const [meta, setMeta] = useState(null)            // GET /api/stories
  const [epics, setEpics] = useState([])
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)    // the story open on the right; null = a new one
  const [item, setItem] = useState(null)            // GET /api/stories/item of the open story
  const [opening, setOpening] = useState('')
  const [draft, setDraft] = useState(() => fresh(null))
  const [restored, setRestored] = useState(false)
  const [analysis, setAnalysis] = useState(null)
  const [sent, setSent] = useState(null)            // the {as, want, so} the analysis on screen was made from
  const [pending, setPending] = useState(false)
  const [analyzeError, setAnalyzeError] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)  // {where: 'touches' | 'save' | 'conflict', msg}
  const [toast, setToast] = useState(null)          // {id, n}
  const [openError, setOpenError] = useState('')
  const [nonce, setNonce] = useState(0)             // a new one on each open: the analysis runs again even on the same text
  const lastBody = useRef('')                       // the analyze key whose answer is on screen
  const nowBody = useRef('')                        // the analyze key of the draft as it is now
  const seq = useRef(0)                             // the latest open(): an answer for an earlier one is dropped

  const load = useCallback(() => getJSON('stories').then((m) => { setMeta(m); setError('') }, (e) => setError(e.message)), [])
  useEffect(() => {
    load()
    getJSON('kanban').then((b) => setEpics(b.epics || []), () => setEpics([]))
  }, [load])

  // Open a story (or a new one): its draft from this browser when it is about the same text, else as on the board.
  // The steps are hidden while it loads and when it fails, and the draft on screen is a blank one meanwhile: the story
  // shown before can never be saved under another one. The files its linked pages cite join Toca once (marked).
  const open = useCallback(async (id) => {
    const mine = ++seq.current
    setSelected(id); setAnalysis(null); setSent(null); setSaveError(null); setAnalyzeError(''); setOpenError('')
    setItem(null); setRestored(false); setDraft(fresh(null)); setNonce((n) => n + 1); lastBody.current = ''
    if (!id) {
      const kept = loadDraft(draftKey(null))
      setRestored(!!kept); setDraft(kept ? { ...fresh(null), ...kept } : fresh(null)); setOpening('')
      return
    }
    setOpening(id)
    try {
      const it = await getJSON(`stories/item?id=${encodeURIComponent(id)}`)
      if (mine !== seq.current) return
      const kept = loadDraft(draftKey(id))
      const same = kept && kept.sha === it.sha
      setItem(it); setRestored(!!same)
      setDraft(same ? { ...fresh(it), ...kept } : mergeDocSources(fresh(it), it.doc_sources))
      setOpening('')
    } catch (e) {
      if (mine !== seq.current) return
      setOpening(''); setOpenError(`${t('stories.loadFailed', { id })} ${e.message}`)
    }
  }, [])
  useEffect(() => { open(null) }, [open])

  const change = useCallback((patch) => setDraft((d) => {
    const next = { ...(typeof patch === 'function' ? patch(d) : { ...d, ...patch }), dirty: true }
    if (next.titleAuto && next.want !== d.want) next.title = titleFrom(next.want)
    return next
  }), [])

  // The draft is kept in this browser once the person has changed something; nothing of it reaches the project before Save.
  useEffect(() => { if (draft.dirty && !blank(draft)) saveDraft(draftKey(draft.id), draft) }, [draft])

  // analyze, 200 ms after the last change; an answer for a draft that has changed since is dropped (planAnalyze).
  const keyOf = useCallback((d) => `${nonce}|${JSON.stringify(analyzeBody(d, lang()))}`, [nonce])
  const key = useMemo(() => keyOf(draft), [draft, keyOf])
  useEffect(() => {
    nowBody.current = key
    const plan = planAnalyze(lastBody.current, key, draft.want)
    lastBody.current = plan.last
    if (plan.action === 'skip') return undefined
    if (plan.action === 'clear') { setAnalysis(null); setSent(null); setPending(false); return undefined }
    const body = key.slice(key.indexOf('|') + 1)
    setPending(true)
    const ctrl = new AbortController()
    const timer = setTimeout(async () => {
      const asked = { as: draft.as, want: draft.want, so: draft.so }
      try {
        const res = await postJSON('stories/analyze', JSON.parse(body), { signal: ctrl.signal })
        if (nowBody.current !== key) return
        const groups = Object.fromEntries(res.tasks.flatMap((x) => (x.group ? x.touches.map((f) => [f, x.group]) : [])))
        setDraft((d) => {
          const next = { ...d, tasks: withChecks(res.tasks, d.tasks), groups: { ...groups, ...d.groups } }
          lastBody.current = nowBody.current = keyOf(next)
          return next
        })
        setAnalysis(res); setSent(asked); setAnalyzeError(''); setPending(false)
      } catch (e) {
        if (e.name === 'AbortError') return
        lastBody.current = key
        setAnalyzeError(e.message); setPending(false)
      }
    }, ANALYZE_MS)
    return () => { clearTimeout(timer); ctrl.abort() }
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps

  const ai = useSuggest({ draft, lang: lang(), onReadOnly: () => setMeta((m) => ({ ...m, writable: false })) })

  async function save() {
    setSaving(true); setSaveError(null)
    try {
      const res = await postJSON('stories/save', { ...saveBody(draft), lang: lang() })
      dropDraft(draftKey(draft.id))
      setToast({ id: res.story.id, n: res.tasks.length })
      await load()
      await open(res.story.id)
    } catch (e) {
      if (e.status === 409) setSaveError({ where: 'conflict', msg: t('stories.conflict', { id: e.data?.id || draft.id }) })
      else if (e.status === 403) setMeta((m) => ({ ...m, writable: false }))
      else setSaveError({ where: /^the story: /.test(e.message) ? 'touches' : 'save', msg: e.message })
    } finally { setSaving(false) }
  }
  useEffect(() => { if (saveError?.where === 'touches') setSaveError(null) }, [draft.touches]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!toast) return undefined
    const h = setTimeout(() => setToast(null), 12000)
    return () => clearTimeout(h)
  }, [toast])

  if (error) return <section className="view stories"><h1>{t('view.stories')}</h1><Failed title={t('stories.failed')} detail={error} onRetry={load} /></section>
  if (!meta) return <section className="view stories"><h1>{t('view.stories')}</h1><Skeleton lines={4} /></section>
  if (!meta.enabled) {
    return (
      <section className="view stories">
        <h1>{t('view.stories')}</h1>
        <p className="lede">{t('stories.off')}</p>
        <a className="button" href="#/kanban">{t('stories.toBoard')}</a>
      </section>
    )
  }

  const words = meta.lint_words?.[lang()] || {}
  const step = Math.max(1, draft.step || 1)
  const block = saveBlock(draft, pending ? null : analysis, pending ? null : sent)
  const goOn = () => change({ step: nextStep({ ...draft, step }, analysis) })
  return (
    <>
    <section className="view stories">
      <h1>{t('view.stories')}</h1>
      <p className="lede">{t('viewd.stories')}</p>
      {!meta.writable ? <p className="aviso st-ro" role="status">{t('stories.readonly')}</p> : null}
      <div className="st-layout">
        <StoryList stories={meta.stories} selected={selected} onPick={open} />
        <div className="st-steps">
          {opening ? <p className="muted" role="status">{t('stories.loading', { id: opening })}</p> : null}
          {openError ? <p className="error" role="alert">{openError}</p> : null}
          {opening || openError ? null : <>
          {restored ? <p className="aviso st-restored" role="status">{t('stories.draft.restored')}{' '}
            <button type="button" className="ghost small" onClick={() => { dropDraft(draftKey(draft.id)); setRestored(false); setDraft(mergeDocSources(fresh(item), item?.doc_sources)) }}>
              {t('stories.draft.discard')}</button></p> : null}
          <WriteStep draft={draft} change={change} words={words} lang={lang()} epics={epics} existing={!!draft.id}
                     touchError={saveError?.where === 'touches' ? saveError.msg : ''} ai={ai} aiOn={meta.ai?.available && meta.writable}
                     onNext={step === 1 ? goOn : null} />
          {step >= 2 ? <ReviewStep draft={draft} change={change} analysis={analysis} pending={pending} ai={ai}
                                   aiOn={meta.ai?.available && meta.writable} onNext={step === 2 ? goOn : null} /> : null}
          {step >= 3 ? <TasksStep draft={draft} change={change} analysis={analysis} ai={ai} aiOn={meta.ai?.available && meta.writable} /> : null}
          {analyzeError ? <p className="error" role="alert">{t('stories.analyzeFailed')} {analyzeError}</p> : null}
          {step >= 3 ? (
            <div className="st-save">
              <button type="button" disabled={!meta.writable || !!block || saving} aria-describedby={block ? 'st-block' : undefined}
                      onClick={save}>{primaryLabel(draft, t)}</button>
              {block && meta.writable ? <p id="st-block" className="muted small" role="status">{t(block.key, block.vars)}</p> : null}
              {saveError?.where === 'save' ? <p className="error" role="alert">{t('stories.saveFailed')} {saveError.msg}</p> : null}
              {saveError?.where === 'conflict' ? <p className="error" role="alert">{saveError.msg}{' '}
                <button type="button" className="ghost small" onClick={() => { dropDraft(draftKey(draft.id)); open(draft.id) }}>{t('stories.reload')}</button></p> : null}
            </div>
          ) : null}
          </>}
        </div>
      </div>
    </section>
    {/* outside the animated .view: its transform would make the fixed toast scroll with it */}
    {toast ? <div className="st-toast" role="status">{t('stories.saved', toast)}{' '}
      <a href={`#/kanban?parent=${encodeURIComponent(toast.id)}`}>{t('stories.saved.link')}</a>
      <button type="button" className="ghost small" aria-label={t('stories.close')} onClick={() => setToast(null)}>✕</button></div> : null}
    </>
  )
}


import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { Skeleton } from '@camaron/ui'
import { route, screen, startScreen, viewOf } from '../adr.js'
import { useHash } from '../hooks.js'
import { Failed, Page } from '../parts.jsx'
import { lang, t } from '../i18n.js'
import { AdrListView } from './adr/AdrList.jsx'
import { CandidatesView, candidateFields } from './adr/Candidates.jsx'
import { EvidenceView } from './adr/Evidence.jsx'
import { EMPTY, NewFormView, check, toBody } from './adr/NewForm.jsx'
import { LegacyView, ReadView } from './adr/Read.jsx'

export { AdrListView, CandidatesView, EvidenceView, LegacyView, NewFormView }

// Decisiones: the project's ADRs (lib/adr.py through /api/app/adr…, the app's token). The hash picks the place
// (adr.js `route`): the list, the new-ADR form, the candidates or one ADR. A read that fails says so with Try again.
const go = (hash) => { location.hash = hash }

export default function Decisions({ srv }) {
  const r = route(useHash())
  const [list, setList] = useState(null)                // GET app/adr: {adrs, next}
  const [listError, setListError] = useState('')
  const [cands, setCands] = useState(null)
  const [candError, setCandError] = useState('')
  const [filter, setFilter] = useState('all')
  const [q, setQ] = useState('')
  const [form, setForm] = useState(EMPTY)               // the new ADR as typed: it waits while the person looks elsewhere
  const [prefilled, setPrefilled] = useState(false)
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [creating, setCreating] = useState(false)
  const [carry, setCarry] = useState(null)              // {id, notice}: what the next ADR screen says first (a renumbering)
  const fresh = useRef('')                              // the ADR just created: its evidence is gathered when it opens

  const loadList = useCallback(() => srv.get('app/adr').then((x) => { setList(x); setListError('') }, (e) => setListError(e.message)), [srv])
  const loadCands = useCallback(() => srv.get('app/adr/candidates')
    .then((x) => { setCands(x.candidates || []); setCandError('') }, (e) => setCandError(e.message)), [srv])
  const search = useCallback((query) => srv.get('stories/files', { q: query, limit: 20 }), [srv])
  useEffect(() => { if (r.view !== 'adr' && r.view !== 'candidates') loadList() }, [r.view, loadList])
  useEffect(() => { if (r.view === 'list' || r.view === 'candidates') loadCands() }, [r.view, loadCands])
  useEffect(() => { if (carry && carry.id !== r.id) setCarry(null) }, [r.view, r.id])

  async function create() {
    const found = check(form)
    setErrors(found)
    if (Object.keys(found).length) { document.getElementById('adr-f-title')?.focus(); return }
    setCreating(true); setFormError('')
    try {
      const a = await srv.post('app/adr/new', toBody(form))
      fresh.current = a.id
      setForm(EMPTY); setPrefilled(false)
      go(`#/decisions/${a.id}`)
    } catch (e) { setFormError(e.message) } finally { setCreating(false) }
  }
  const pick = (c) => { setForm({ ...EMPTY, ...candidateFields(c, lang()) }); setPrefilled(true); setErrors({}); setFormError(''); go('#/decisions/new') }
  const cancel = () => { setForm(EMPTY); setPrefilled(false); setErrors({}); setFormError(''); go('#/decisions') }
  const takeFresh = (id) => { const yes = fresh.current === id; if (yes) fresh.current = ''; return yes }
  const moved = (to, notice) => { setCarry({ id: to, notice }); go(`#/decisions/${to}`) }

  if (r.view === 'adr') {
    return <AdrScreen key={r.id} id={r.id} srv={srv} notice={carry?.id === r.id ? carry.notice : null} fresh={takeFresh} onMoved={moved} />
  }
  if (r.view === 'candidates') {
    if (candError) return <Page title={t('adr.cand.title')}><Failed title={t('adr.cand.failed')} detail={candError} onRetry={() => { setCandError(''); loadCands() }} /></Page>
    if (!cands) return <Page title={t('adr.cand.title')}><Skeleton lines={6} /></Page>
    return <CandidatesView rows={cands} onPick={pick} />
  }
  if (r.view === 'new') {
    return (
      <NewFormView fields={form} errors={errors} prefilled={prefilled} next={list?.next} busy={creating} error={formError} search={search}
        accepted={(list?.adrs || []).filter((a) => a.chip === 'accepted')} onChange={setForm} onSubmit={create} onCancel={cancel} />
    )
  }
  if (listError) return <Page title={t('nav.decisions')}><Failed title={t('adr.failed')} detail={listError} onRetry={() => { setListError(''); loadList() }} /></Page>
  if (!list) return <Page title={t('nav.decisions')}><Skeleton lines={6} /></Page>
  return <AdrListView rows={list.adrs} filter={filter} q={q} onFilter={setFilter} onQ={setQ} candidates={cands} />
}

// One ADR, opened at its phase (adr.js `viewOf`). Its state (adr.js `screen`) lives and dies with it: Decisions keys it
// by the ADR, so what one was doing never shows on another. A save the file outran (409) reads the ADR again and says
// so; `fresh(id)` says whether it was just created, so its evidence is gathered once; `onMoved` follows a renumbering.
function AdrScreen({ id, srv, notice, fresh, onMoved }) {
  const [s, dispatch] = useReducer(screen, notice, startScreen)
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  const read = () => srv.get(`app/adr/${id}`)

  async function failed(e, type) {
    if (e.status !== 409) return dispatch({ type, error: e.message })
    try { dispatch({ type: 'reloaded', adr: await read() }) } catch (again) { dispatch({ type: 'readFailed', error: again.message }) }
  }
  async function gather() {
    dispatch({ type: 'packing' })
    try {
      const pack = await srv.post('app/adr/pack', { id })
      dispatch({ type: 'packed', pack, adr: await read().catch(() => null) })     // a framed ADR moves on to evidence
    } catch (e) { await failed(e, 'packFailed') }
  }
  useEffect(() => {
    let live = true
    read().then((adr) => {
      if (!live) return
      dispatch({ type: 'read', adr })
      if (!adr?.state) return
      srv.get(`app/adr/${id}/pack`).then((pack) => { if (live) dispatch({ type: 'pack', pack }) }, (e) => {
        if (!live) return
        if (e.status !== 404) return dispatch({ type: 'packFailed', error: e.message })
        dispatch({ type: 'pack', pack: null })
        if (fresh(id)) gather()
      })
    }, (e) => { if (live) dispatch({ type: 'readFailed', error: e.message }) })
    return () => { live = false }
  }, [s.reads])

  async function act(post, then) {
    dispatch({ type: 'busy' })
    try { then(await post()) } catch (e) { await failed(e, 'actFailed') }
  }
  const write = () => act(() => srv.post('app/adr/write', { id }), (adr) => {
    dispatch({ type: 'done', adr })
    const to = adr.notice?.renumbered
    if (to && alive.current) onMoved(to.to, { key: 'adr.renumbered', vars: to })
  })
  const review = () => act(() => srv.post('app/adr/review', { id }), (adr) => dispatch({ type: 'done', adr }))

  if (s.error) return <Page title={`ADR ${id}`}><Failed title={t('adr.adrFailed', { id })} detail={s.error} onRetry={() => dispatch({ type: 'retry' })} /></Page>
  if (!s.adr) return <Page title={`ADR ${id}`}><Skeleton lines={6} /></Page>
  const say = s.notice ? t(s.notice.key, s.notice.vars) : ''
  const view = viewOf(s.adr)
  if (view === 'legacy') return <LegacyView adr={s.adr} busy={s.busy} error={s.actError} notice={say} onReview={review} />
  if (view === 'evidence') return (
    <EvidenceView adr={s.adr} pack={s.pack} packing={s.packing} packError={s.packError} busy={s.busy} error={s.actError} notice={say}
      onPack={gather} onWrite={write} />
  )
  return <ReadView adr={s.adr} notice={say} />            // review, accepted, rejected: the review screen takes it next
}

import { useCallback, useEffect, useRef, useState } from 'react'
import { Skeleton } from '@camaron/ui'
import { route } from '../adr.js'
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
// (adr.js `route`): the list, the new-ADR form, the candidates or one ADR, which opens at its phase: framed or with its
// evidence → the evidence step; in review or decided → the review screen; no working state (legacy) → read-only, with
// the way into a session. A read that fails says so with Try again; a save the file outran (409) reads the ADR again.
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
  const [adr, setAdr] = useState(null)
  const [adrError, setAdrError] = useState('')
  const [pack, setPack] = useState(undefined)           // undefined: not read yet; null: none gathered
  const [packError, setPackError] = useState('')
  const [packing, setPacking] = useState(false)
  const [busy, setBusy] = useState(false)
  const [actError, setActError] = useState('')
  const [notice, setNotice] = useState(null)            // {id, text}: said on that ADR's screen
  const [reads, setReads] = useState(0)                 // Try again on an ADR reads it, and its pack, afresh
  const gather = useRef('')                             // the ADR just created: its evidence is gathered when it opens
  const shown = useRef('')                              // the ADR on screen: a late answer about another one is dropped
  shown.current = r.view === 'adr' ? r.id : ''

  const loadList = useCallback(() => srv.get('app/adr').then((x) => { setList(x); setListError('') }, (e) => setListError(e.message)), [srv])
  const loadCands = useCallback(() => srv.get('app/adr/candidates')
    .then((x) => { setCands(x.candidates || []); setCandError('') }, (e) => setCandError(e.message)), [srv])
  const search = useCallback((query) => srv.get('stories/files', { q: query, limit: 20 }), [srv])
  useEffect(() => { if (r.view !== 'adr' && r.view !== 'candidates') loadList() }, [r.view, loadList])
  useEffect(() => { if (r.view === 'list' || r.view === 'candidates') loadCands() }, [r.view, loadCands])

  const loadAdr = useCallback((id) => srv.get(`app/adr/${id}`).then((a) => { if (shown.current === id) { setAdr(a); setAdrError('') } },
    (e) => { if (shown.current === id) setAdrError(e.message) }), [srv])
  const reloaded = async (id) => { await loadAdr(id); setNotice({ id, text: t('adr.reloaded') }) }
  const failed = (id, e, set) => (e.status === 409 ? reloaded(id) : set(e.message))

  async function runPack(id) {
    setPacking(true); setPackError('')
    try {
      const p = await srv.post('app/adr/pack', { id })
      if (shown.current === id) setPack(p)
      await loadAdr(id)                                 // a framed ADR moves on to evidence
    } catch (e) { await failed(id, e, setPackError) } finally { setPacking(false) }
  }

  useEffect(() => {
    if (r.view !== 'adr') return undefined
    let live = true
    const id = r.id
    setAdr(null); setAdrError(''); setPack(undefined); setPackError(''); setActError('')
    srv.get(`app/adr/${id}`).then((a) => {
      if (!live) return
      setAdr(a)
      if (!a?.state) return
      srv.get(`app/adr/${id}/pack`).then((p) => { if (live) setPack(p) }, (e) => {
        if (!live) return
        setPack(null)
        if (e.status !== 404) setPackError(e.message)
        else if (gather.current === id) { gather.current = ''; runPack(id) }
      })
    }, (e) => { if (live) setAdrError(e.message) })
    return () => { live = false }
  }, [r.view, r.id, reads])

  async function act(post, onDone) {
    const id = adr.id
    setBusy(true); setActError('')
    try { const a = await post(id); if (shown.current === id) onDone(a) } catch (e) { await failed(id, e, setActError) } finally { setBusy(false) }
  }
  const write = () => act((id) => srv.post('app/adr/write', { id }), (a) => {
    const moved = a.notice?.renumbered
    if (moved) { setNotice({ id: moved.to, text: t('adr.renumbered', moved) }); go(`#/decisions/${moved.to}`) }
    setAdr(a)
  })
  const review = () => act((id) => srv.post('app/adr/review', { id }), setAdr)

  async function create() {
    const found = check(form)
    setErrors(found)
    if (Object.keys(found).length) { document.getElementById('adr-f-title')?.focus(); return }
    setBusy(true); setFormError('')
    try {
      const a = await srv.post('app/adr/new', toBody(form))
      gather.current = a.id
      setForm(EMPTY); setPrefilled(false)
      go(`#/decisions/${a.id}`)
    } catch (e) { setFormError(e.message) } finally { setBusy(false) }
  }
  const pick = (c) => { setForm({ ...EMPTY, ...candidateFields(c, lang()) }); setPrefilled(true); setErrors({}); setFormError(''); go('#/decisions/new') }
  const cancel = () => { setForm(EMPTY); setPrefilled(false); setErrors({}); setFormError(''); go('#/decisions') }

  if (r.view === 'candidates') {
    if (candError) return <Page title={t('adr.cand.title')}><Failed title={t('adr.cand.failed')} detail={candError} onRetry={() => { setCandError(''); loadCands() }} /></Page>
    if (!cands) return <Page title={t('adr.cand.title')}><Skeleton lines={6} /></Page>
    return <CandidatesView rows={cands} onPick={pick} />
  }
  if (r.view === 'new') {
    return (
      <NewFormView fields={form} errors={errors} prefilled={prefilled} next={list?.next} busy={busy} error={formError} search={search}
        accepted={(list?.adrs || []).filter((a) => a.chip === 'accepted')} onChange={setForm} onSubmit={create} onCancel={cancel} />
    )
  }
  if (r.view === 'adr') {
    const title = `ADR ${r.id}`
    if (adrError) return <Page title={title}><Failed title={t('adr.adrFailed', { id: r.id })} detail={adrError} onRetry={() => setReads((n) => n + 1)} /></Page>
    if (!adr || adr.id !== r.id) return <Page title={title}><Skeleton lines={6} /></Page>
    const say = notice?.id === adr.id ? notice.text : ''
    const phase = adr.state?.phase
    if (!adr.state) return <LegacyView adr={adr} busy={busy} error={actError} notice={say} onReview={review} />
    if (phase === 'problem' || phase === 'evidence') return (
      <EvidenceView adr={adr} pack={pack} packing={packing} packError={packError} busy={busy} error={actError} notice={say}
        onPack={() => runPack(adr.id)} onWrite={write} />
    )
    return <ReadView adr={adr} notice={say} />            // review, accepted, rejected: the review screen takes it next
  }
  if (listError) return <Page title={t('nav.decisions')}><Failed title={t('adr.failed')} detail={listError} onRetry={() => { setListError(''); loadList() }} /></Page>
  if (!list) return <Page title={t('nav.decisions')}><Skeleton lines={6} /></Page>
  return <AdrListView rows={list.adrs} filter={filter} q={q} onFilter={setFilter} onQ={setQ} candidates={cands} />
}

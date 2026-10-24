import { useEffect, useMemo, useState } from 'react'
import { getJSON, postJSON } from './api.js'
import { lang, t } from './i18n.js'

// The team questionnaire answered in the portal (lib/questionnaire.py): the same response file the offline form and
// `interview import` produce, one per person, so the consolidating units read them as always. A person's previous
// answers come back to be edited.
const store = {
  get: () => { try { return localStorage.getItem('cam-interview-name') || '' } catch { return '' } },
  set: (v) => { try { localStorage.setItem('cam-interview-name', v) } catch { /* private mode */ } },
}

export default function Interview() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [who, setWho] = useState(store.get())
  const [role, setRole] = useState('')
  const [answers, setAnswers] = useState({})
  const [sent, setSent] = useState(null)
  const [busy, setBusy] = useState(false)
  const load = (name) => getJSON(`interview${name ? `?who=${encodeURIComponent(name)}` : ''}`).then((d) => {
    setData(d)
    if (d.mine) { setAnswers(d.mine.answers || {}); setRole(d.mine.role || '') }
    if (!name && d.user) { setWho(d.user); return load(d.user) }
    return null
  }, (e) => setError(e.message))
  useEffect(() => { load(who) }, [])
  const L = data?.labels?.[lang()] || data?.labels?.en
  const topics = useMemo(() => {
    const out = {}
    for (const q of data?.questions || []) (out[q.topic] ||= []).push(q)
    return out
  }, [data])

  if (error) return <section className="view"><h1>{t('ivTitle')}</h1><p className="error" role="alert">{t('ivFailed')} {error}</p></section>
  if (!data) return <section className="view"><h1>{t('ivTitle')}</h1><div className="co-esqueleto skeleton" aria-busy="true" /></section>
  if (!data.available) return (
    <section className="view interview"><h1>{t('ivTitle')}</h1>
      <p className="lede">{t('ivLead')}</p>
      <p className="aviso">{data.mode === 'team' ? t('ivNoForm') : t('ivLive')}</p>
      <p className="muted small">{data.reason}</p></section>
  )
  const set = (id, patch) => setAnswers((a) => ({ ...a, [id]: { ...(a[id] || {}), ...patch } }))
  async function send(e) {
    e.preventDefault()
    setBusy(true)
    setSent(null)
    try {
      const s = await postJSON('interview/answer', { respondent: who.trim(), role: role.trim(), answers })
      store.set(who.trim())
      setSent({ ok: true })
      setData((d) => ({ ...d, status: s }))
    } catch (err) { setSent({ error: err.message }) } finally { setBusy(false) }
  }
  const s = data.status
  return (
    <section className="view interview">
      <h1>{data.title || t('ivTitle')}</h1>
      <p className="lede">{data.intro || t('ivLead')}</p>
      <div className="iv-state">
        <span className="pill">{t('ivQuestions').replace('{n}', s.questions)}</span>
        <span className="pill">{t('ivPeople').replace('{n}', s.respondents.length)}</span>
        {s.unanswered.length ? <span className="pill warn">{t('ivUnanswered').replace('{n}', s.unanswered.length)}</span> : null}
        {s.conflicts.length ? <span className="pill bad">{t('ivConflicts').replace('{n}', s.conflicts.length)}</span> : null}
        {s.respondents.length ? <span className="muted small">{s.respondents.map((r) => `${r.name} (${r.answered})`).join(', ')}</span> : null}
      </div>
      <form className="iv-form" onSubmit={send}>
        <div className="iv-who">
          <label>{L.name}<input className="co-input" required value={who} onChange={(e) => setWho(e.target.value)}
                                onBlur={() => who.trim() && load(who.trim())} /></label>
          <label>{L.role}<input className="co-input" value={role} onChange={(e) => setRole(e.target.value)} /></label>
        </div>
        {Object.entries(topics).map(([topic, qs]) => (
          <fieldset key={topic} className="iv-topic">
            <legend>{L.topics[topic] || topic}</legend>
            {qs.map((q) => <Question key={q.id} q={q} L={L} a={answers[q.id] || {}} set={(p) => set(q.id, p)}
                                     conflict={s.conflicts.find((c) => c.id === q.id)} />)}
          </fieldset>
        ))}
        <div className="row iv-send">
          <button type="submit" className="small" disabled={busy || !who.trim()}>{t('ivSend')}</button>
          {sent?.ok ? <span className="ok" role="status">{t('ivThanks')}</span> : null}
          {sent?.error ? <span className="error" role="alert">{sent.error}</span> : null}
        </div>
      </form>
    </section>
  )
}

function Question({ q, L, a, set, conflict }) {
  const name = `q-${q.id}`
  const choice = a.choice
  const multi = Array.isArray(choice) ? choice : choice ? [choice] : []
  const toggle = (o) => set({ choice: multi.includes(o) ? multi.filter((x) => x !== o) : [...multi, o] })
  return (
    <div className="iv-q">
      <p className="iv-text"><b>{q.text}</b> <code className="muted small">{q.id}</code></p>
      {q.inferred ? <p className="aviso small">{L.inferred}: {q.inferred}{q.evidence ? <> ({L.evidence}: <code>{q.evidence}</code>)</> : null}</p> : null}
      {conflict ? <p className="small warn">{t('ivDisagree')} {Object.entries(conflict.answers).map(([v, ns]) => `${v} ← ${ns.join(', ')}`).join(' · ')}</p> : null}
      {q.kind === 'text' ? (
        <textarea className="co-input" rows={3} value={a.text || ''} onChange={(e) => set({ text: e.target.value })} aria-label={L.answer} />
      ) : (
        <div className="iv-opts">
          {(q.kind === 'confirm' ? ['yes', 'no', 'unsure'] : q.options).map((o) => (
            <label key={o} className="check">
              <input type={q.kind === 'multi' ? 'checkbox' : 'radio'} name={name} checked={q.kind === 'multi' ? multi.includes(o) : choice === o}
                     onChange={() => (q.kind === 'multi' ? toggle(o) : set({ choice: o }))} />
              {q.kind === 'confirm' ? L[o] : o}
            </label>
          ))}
          {q.kind !== 'confirm' ? <label>{L.other}<input className="co-input" value={a.other || ''} onChange={(e) => set({ other: e.target.value })} /></label> : null}
        </div>
      )}
      {q.kind !== 'text' ? <label className="iv-comment">{L.comment}<input className="co-input" value={a.comment || ''}
                                                                          onChange={(e) => set({ comment: e.target.value })} /></label> : null}
    </div>
  )
}

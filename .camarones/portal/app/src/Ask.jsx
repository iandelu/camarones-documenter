import { useEffect, useRef, useState } from 'react'
import { getJSON, postJSON } from './api.js'
import { t } from './i18n.js'
import AppOnly from './AppOnly.jsx'
import { core } from './core.js'
import { drawMermaid, render } from './content/doc.js'

// A section rendered by the docs renderer (content/doc.js `render`), so it looks exactly like the page it comes from.
function Section({ text, path }) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const doc = render(text, path)
    el.replaceChildren(doc)
    drawMermaid(doc)
  }, [text, path])
  return <div ref={ref} />
}

// Opt-in, one click per question: the runner for bounded work answers from the sections Ask found, citing them.
function AiAnswer({ question, runner, link }) {
  const [state, setState] = useState(null)
  const [waited, setWaited] = useState(0)
  useEffect(() => {
    if (!state?.busy) return undefined
    const started = Date.now()
    const id = setInterval(() => setWaited(Math.round((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(id)
  }, [state?.busy])
  async function go() {
    setWaited(0)
    setState({ busy: true })
    try { setState(await postJSON('ask/answer', { q: question })) } catch (e) { setState({ error: e.message }) }
  }
  if (!state) return <AppOnly><button type="button" className="ghost small ai-go" onClick={go}>✨ {t('aiAnswer')} · {runner}</button></AppOnly>
  if (state.busy) return <p className="muted ai-busy" role="status">{t('aiBusy')} {waited ? `${waited} s` : ''}</p>
  if (state.error) return <p className="error" role="alert">{state.error}</p>
  const cost = state.cost_usd ? ` · $${state.cost_usd.toFixed(3)}` : ''
  return (
    <div className="ai-answer">
      <p className="muted small">{t('aiBy')} {state.runner}{state.model ? ` (${state.model})` : ''} · {state.seconds} s{cost}. {t('aiCheck')}</p>
      <p>{state.answer || t('aiNone')}</p>
      {state.cited?.length ? <p className="small">{state.cited.map((c) => <a key={c} href={link(c)}>{c}</a>)}</p> : null}
    </div>
  )
}

export default function Ask({ arg }) {
  const [q, setQ] = useState('')
  const [turns, setTurns] = useState([])
  const [busy, setBusy] = useState(false)
  useEffect(() => { if (arg) run(arg) }, [arg])                // #/ask/<question>: the home page's question box
  async function ask(e) {
    e.preventDefault()
    await run(q)
  }
  async function run(text) {
    const question = text.trim()
    if (!question) return
    setBusy(true)
    try {
      const r = await getJSON(`ask?q=${encodeURIComponent(question)}`)
      setTurns((ts) => [{ question, sections: r.sections, ai: r.ai }, ...ts])
      setQ('')
    } catch (e) {
      setTurns((ts) => [{ question, sections: [], error: e.message }, ...ts])
    } finally { setBusy(false) }
  }
  const link = (cite) => {
    const [path, anchor] = cite.split('#')
    return core.hrefFor(path, anchor)
  }
  return (
    <section className="ask view">
      <h1>{t('askTitle')}</h1>
      <p className="lede">{t('askLead')}</p>
      {!(core.tree().docs || []).some((d) => !(core.tree().kitGuides || []).includes(d.path)
        && d.type !== 'interview')
        ? <p className="banner"><a href="#/">{t('askEmpty')}</a></p> : null}
      <form onSubmit={ask}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('askPh')} aria-label={t('askTitle')} autoFocus />
        <button type="submit" disabled={busy}>{busy ? t('asking') : t('ask')}</button>
      </form>
      {turns.map((turn, i) => (
        <div className="turn" key={turns.length - i}>
          <div className="q">{turn.question}</div>
          {turn.ai && turn.sections.length ? <AiAnswer question={turn.question} runner={turn.ai} link={link} /> : null}
          {turn.sections.length ? turn.sections.map((s) => (
            <article className="cited" key={s.cite}>
              <div className="cited-head">
                <a href={link(s.cite)}>{s.cite}</a>
                <span className={`pill trust ${s.trust}`}>{s.trust}</span>
                {s.withheld_for_agents ? <span className="withheld">{t('withheld')}</span> : null}
              </div>
              <Section text={(s.tldr ? s.tldr + '\n\n' : '') + s.text} path={s.cite.split('#')[0]} />
            </article>
          )) : turn.error ? <p className="error" role="alert">{t('askFailed')} {turn.error}</p>
            : <p className="muted">{t('nothing')}</p>}
        </div>
      ))}
    </section>
  )
}

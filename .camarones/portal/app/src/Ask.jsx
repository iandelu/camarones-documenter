import { useEffect, useRef, useState } from 'react'
import { getJSON } from './api.js'
import { t } from './i18n.js'

// A section rendered by the docs renderer (legacy/doc.js `render`), so it looks exactly like the page it comes from.
function Section({ text, path }) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el || !window.render) return
    el.replaceChildren(window.render(text, path))
  }, [text, path])
  return <div ref={ref} />
}

export default function Ask() {
  const [q, setQ] = useState('')
  const [turns, setTurns] = useState([])
  const [busy, setBusy] = useState(false)
  async function ask(e) {
    e.preventDefault()
    const question = q.trim()
    if (!question) return
    setBusy(true)
    try {
      const r = await getJSON(`ask?q=${encodeURIComponent(question)}`)
      setTurns((ts) => [{ question, sections: r.sections }, ...ts])
      setQ('')
    } finally { setBusy(false) }
  }
  const link = (cite) => {
    const [path, anchor] = cite.split('#')
    return window.hrefFor ? window.hrefFor(path, anchor) : `#/docs/${path}`
  }
  return (
    <section className="ask view">
      <h1>{t('askTitle')}</h1>
      <p className="lede">{t('askLead')}</p>
      <form onSubmit={ask}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('askPh')} aria-label={t('askTitle')} autoFocus />
        <button type="submit" disabled={busy}>{t('ask')}</button>
      </form>
      {turns.map((turn, i) => (
        <div className="turn" key={turns.length - i}>
          <div className="q">{turn.question}</div>
          {turn.sections.length ? turn.sections.map((s) => (
            <article className="cited" key={s.cite}>
              <div className="cited-head">
                <a href={link(s.cite)}>{s.cite}</a>
                <span className={`pill trust ${s.trust}`}>{s.trust}</span>
                {s.withheld_for_agents ? <span className="withheld">{t('withheld')}</span> : null}
              </div>
              <Section text={(s.tldr ? s.tldr + '\n\n' : '') + s.text} path={s.cite.split('#')[0]} />
            </article>
          )) : <p className="muted">{t('nothing')}</p>}
        </div>
      ))}
    </section>
  )
}

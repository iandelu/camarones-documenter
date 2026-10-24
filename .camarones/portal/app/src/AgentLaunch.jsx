import { useEffect, useState } from 'react'
import { getJSON, postJSON } from './api.js'
import { t } from './i18n.js'

// A unit an agent works on, opened as an interactive session in its own terminal window (lib/agents.py).
export default function AgentLaunch({ unit, title = true }) {
  const [agents, setAgents] = useState(null)
  const [agent, setAgent] = useState('')
  const [state, setState] = useState(null)
  useEffect(() => {
    getJSON('app/agents').then((a) => {
      setAgents(a.agents)
      setAgent(a.last && a.agents.some((x) => x.id === a.last) ? a.last : a.agents[0]?.id || '')
    }, (e) => setState({ error: e.message }))
  }, [])
  if (unit.runner !== 'agent' || !['todo', 'doing'].includes(unit.status)) return null
  if (agents && !agents.length) return <p className="aviso small">{t('pNoAgent')}</p>
  async function open(mode) {
    setState(null)
    const lang = document.documentElement.lang === 'es' ? 'es' : 'en'
    try { await postJSON('app/agent', { unit: unit.id, agent, mode, lang }); setState({ ok: true }) } catch (e) { setState({ error: e.message }) }
  }
  return (
    <div className="agent-launch">
      {title ? <h3>{t('pSession')}</h3> : null}
      <div className="row">
        <select className="co-input" value={agent} onChange={(e) => setAgent(e.target.value)} aria-label={t('pAgent')}>
          {(agents || []).map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
        </select>
        <button className="small" disabled={!agent} onClick={() => open('new')}>{t('pOpenTerminal')}</button>
      </div>
      {unit.status === 'doing' ? (
        <div className="row">
          <button className="ghost small" disabled={!agent} onClick={() => open('continue')}>{t('pContinue')}</button>
          <button className="ghost small" disabled={!agent} onClick={() => open('restart')}>{t('pRestart')}</button>
        </div>
      ) : null}
      {state?.ok ? <p className="muted small" role="status">{t('pOpened')}</p> : null}
      {state?.error ? <p className="error" role="alert">{state.error}</p> : null}
    </div>
  )
}

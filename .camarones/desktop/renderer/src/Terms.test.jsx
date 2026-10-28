import { ReactFlowProvider } from '@xyflow/react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { PtyNode } from './sections/Terms.jsx'
import { setLang } from './i18n.js'

afterEach(() => setLang('es'))
const html = (el) => renderToStaticMarkup(<ReactFlowProvider>{el}</ReactFlowProvider>)
const unit = { id: 'explain:api', title: 'Explicar la API', status: 'doing', runner: 'agent', phase: 2, deps: [] }
const live = { id: 't-explain_api-1', kind: 'unit', unit: 'explain:api', agent: 'claude', started: 0, ended: null, code: null }
const on = { attach: () => () => {}, onClose() {}, onMax() {}, onSession() {}, canStart: true }

test('a session with you shows its agent, its time and how to close it', () => {
  const out = html(<PtyNode data={{ unit, term: live, now: 120000, ...on }} />)
  for (const s of ['Explicar la API', 'claude', 'contigo', '2 min', 'Cerrar']) expect(out).toContain(s)
  expect(out).toMatch(/class="[^"]*dk-pty-slot[^"]*nowheel[^"]*nodrag[^"]*nokey/)
  expect(out).toContain('aria-label="Terminal de Explicar la API"')
  expect(out).not.toContain('Abrir una sesión nueva')
})

test('a session that failed keeps its screen and offers a new one', () => {
  const out = html(<PtyNode data={{ unit, term: { ...live, ended: 60, code: 1 }, now: 90000, ...on }} />)
  for (const s of ['terminó (1)', 'Quitar', 'Abrir una sesión nueva', 'tone-blocked']) expect(out).toContain(s)
})

test('the docs update is a loose session, in English too', () => {
  setLang('en')
  const term = { ...live, id: 't-update-1', kind: 'update', unit: null }
  const out = html(<PtyNode data={{ term, now: 0, ...on }} />)
  for (const s of ['Update docs', 'with you', 'Close']) expect(out).toContain(s)
})

import { ReactFlowProvider } from '@xyflow/react'
import { readFileSync } from 'node:fs'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { PtyNode, screenKey } from './sections/Terms.jsx'
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

// React Flow pans on a drag that starts anywhere but in a nopan element (nodrag only keeps the node still), and its pan
// swallows the mouse moves xterm needs to select text.
test('a drag inside a terminal selects its text: the canvas neither pans, drags, zooms nor takes its keys', () => {
  const out = html(<PtyNode data={{ unit, term: live, now: 0, ...on }} />)
  const slot = out.match(/class="([^"]*dk-pty-slot[^"]*)"/)[1].split(' ')
  const src = readFileSync(new URL('./sections/Terms.jsx', import.meta.url), 'utf-8')
  const host = src.match(/host\.className = '([^']*)'/)[1].split(' ')
  for (const c of ['nopan', 'nodrag', 'nowheel', 'nokey']) {
    expect(slot).toContain(c)
    expect(host).toContain(c)
  }
})

// WCAG 2.1.2: xterm keeps Escape, Tab and Enter for the program, so F6 is the way out (the canvas's canvasKey).
test('a terminal says how to leave it, in Spanish and English', () => {
  const slot = () => html(<PtyNode data={{ unit, term: live, now: 0, ...on }} />).match(/<div[^>]*dk-pty-slot[^>]*>/)[0]
  expect(slot()).toContain('aria-description="F6: salir de la terminal"')
  setLang('en')
  expect(slot()).toContain('aria-description="F6: leave the terminal"')
})

// Shift+Tab changes Claude Code's permission mode: sent to the agent, it must not also move the focus out.
test('F6 is left to the canvas, and Shift+Tab goes to the agent without moving the focus', () => {
  const key = (k, more = {}) => {
    const e = { type: 'keydown', key: k, shiftKey: false, prevented: false, preventDefault() { this.prevented = true }, ...more }
    return [screenKey(e), e.prevented]
  }
  expect(key('F6')).toEqual([false, false])
  expect(key('Tab', { shiftKey: true })).toEqual([true, true])
  expect(key('Tab', { shiftKey: true, type: 'keyup' })).toEqual([true, false])
  for (const k of ['Tab', 'Escape', 'Enter', 'a']) expect(key(k)).toEqual([true, false])
  const src = readFileSync(new URL('./sections/Terms.jsx', import.meta.url), 'utf-8')
  expect(src).toMatch(/attachCustomKeyEventHandler\(screenKey\)/)
})

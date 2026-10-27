import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { Failed, JobChip, Page } from './parts.jsx'
import { setLang } from './i18n.js'

// A read that failed says what, shows the server's own message and offers to try again: never a dead end.
test('a failed read is an alert with the server message and a retry', () => {
  setLang('es')
  const out = renderToStaticMarkup(<Failed title="No he podido leer el plan" detail="HTTP 500: boom" onRetry={() => {}} />)
  expect(out).toMatch(/^<div class="cu-aviso cu-aviso--error" role="alert">/)
  expect(out).toContain('<code class="cu-aviso-detail">HTTP 500: boom</code>')
  expect(out).toContain('>Reintentar</button>')
})

test('without a retry, no button', () => {
  expect(renderToStaticMarkup(<Failed title="x" detail="y" />)).not.toContain('<button')
})

test('a full page says so in its class; a plain one does not', () => {
  expect(renderToStaticMarkup(<Page title="Tablero" full />)).toMatch(/^<div class="dk-page full">/)
  expect(renderToStaticMarkup(<Page title="Plan" />)).toMatch(/^<div class="dk-page">/)
})

// A running job shimmers like the AI thinking (ui.css .cu-thinking): something is at work, not stuck. Once it ends
// its state is a plain word.
test('a running job says so with the thinking shimmer; a finished one is a plain word', () => {
  setLang('es')
  const html = (node) => renderToStaticMarkup(node)
  expect(html(<JobChip job={{ status: 'running' }} />)).toContain('<span class="cu-thinking">En curso</span>')
  const done = html(<JobChip job={{ status: 'done' }} />)
  expect(done).not.toContain('cu-thinking')
  expect(done).toContain('Hecho')
  expect(html(<JobChip job={{ status: 'failed', stopped: true }} />)).toContain('Parado')
})

// A page whose header carries its actions (Decisiones: Candidatas, Nuevo ADR) sets them beside the title.
test('a page with actions sets them beside its title; one without keeps the bare title', () => {
  const out = renderToStaticMarkup(<Page title="Decisiones" actions={<button type="button">Nuevo</button>} />)
  expect(out).toMatch(/^<div class="dk-page"><div class="dk-page-head"><h1 class="t-impact">Decisiones<\/h1><div class="row dk-page-acts"><button/)
  expect(renderToStaticMarkup(<Page title="Plan" />)).toBe('<div class="dk-page"><h1 class="t-impact">Plan</h1></div>')
})

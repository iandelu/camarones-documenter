import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { Failed } from './parts.jsx'
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

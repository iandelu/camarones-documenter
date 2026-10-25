import { readFileSync } from 'node:fs'
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement } from 'react'
import { expect, test } from 'vitest'
import Failed from './Failed.jsx'

const read = (f) => readFileSync(new URL(f, import.meta.url), 'utf-8')

// The same states in every view that reads the server: the kit's skeleton while it loads; when it fails, what failed,
// the server's own message and Try again. No bare "Loading…" and no dead end.
test.each(['./Ci.jsx', './Kpis.jsx', './Sync.jsx', './Interview.jsx', './Kanban.jsx', './Data.jsx', './Libs.jsx', './Pipeline.jsx'])(
  '%s loads with the skeleton and fails with a way out', (f) => {
    const src = read(f)
    expect(src).not.toMatch(/co-esqueleto|t\('loading'\)/)
    expect(src).toMatch(/<Skeleton lines=/)
    expect(src).toMatch(/<Failed [^>]*onRetry=|action=\{<Button[^>]*onClick=\{reload\}/)
  })

test('a failed view is an alert with the message and Try again', () => {
  const out = renderToStaticMarkup(createElement(Failed, { title: 'No he podido leer los KPIs', detail: 'HTTP 503', onRetry: () => {} }))
  expect(out).toMatch(/^<div class="cu-aviso cu-aviso--error" role="alert">/)
  expect(out).toContain('<code class="cu-aviso-detail">HTTP 503</code><span class="cu-aviso-action"><button')
})

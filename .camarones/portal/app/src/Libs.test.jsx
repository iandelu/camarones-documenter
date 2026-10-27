import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { Where } from './Libs.jsx'
import { matrix } from './libs.js'

test('a line of the table names its repos, the flagged ones first, so their columns need no scrolling', () => {
  const rows = ['wallet-adapter', 'backoffice-app', 'integration-service', 'lobby-service', 'content-service'].map((repo) => ({
    repo, ecosystem: 'Maven', name: 'org.springframework:spring-webmvc', version: '6.1.21', scope: 'runtime', category: 'framework',
    vulns: repo === 'integration-service' ? [{ id: 'GHSA-1', severity: 'high' }] : [] }))
  const out = renderToStaticMarkup(<Where item={matrix(rows).items[0]} />)
  expect(out).toMatch(/^<span class="libs-where[^"]*">in <b class="libs-where-bad">integration-service<\/b>/)
  expect(out).toContain('+2 more')
  expect(out).not.toContain('wallet-adapter')
})

import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { LibsView } from './Libs.jsx'

const row = (repo) => ({ repo, ecosystem: 'Maven', name: `org.acme.${repo}:lib`, version: '1.0.0', declared: '1.0.0', scope: 'runtime',
  category: 'other', language: 'Java', source: `${repo}:pom.xml`, managedBy: null, vulns: [] })

test('the portal draws the shared board, read-only, filtered by #/libs/<repo>', () => {
  const out = renderToStaticMarkup(<LibsView inv={{ libraries: [row('web'), row('api')], vulns: null, latest: null }} arg="api" />)
  expect(out).toContain('class="cu-libs"')
  expect(out).toContain('camaron inventory --cves --latest')
  expect(out).toContain('<option value="api" selected="">')
  expect(out).not.toContain('org.acme.web:lib')
})

test('a repo the inventory does not have leaves the filter empty', () => {
  const out = renderToStaticMarkup(<LibsView inv={{ libraries: [row('web')], vulns: null, latest: null }} arg="nope" />)
  expect(out).toContain('org.acme.web:lib')
})

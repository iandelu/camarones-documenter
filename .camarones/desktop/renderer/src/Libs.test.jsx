import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { matrix } from '@camaron/ui/libs.js'
import Libs, { LibTable, Library, ScanStatus } from './sections/Libs.jsx'
import { setLang } from './i18n.js'

const srv = { get: () => new Promise(() => {}), post: () => new Promise(() => {}) }
const vulns = [
  { id: 'GHSA-1', cve: 'CVE-2026-1', severity: 'high', score: 7.5, summary: 'launch-editor check bypassed', fixed: '8.3.3',
    aliases: ['CVE-2026-1'], details: 'The full text of the advisory.', published: '2026-10-01T00:00:00Z', modified: null,
    ranges: [{ introduced: '8.0.0', fixed: '8.3.3' }], references: [{ type: 'ADVISORY', url: 'https://example.org/a' }], cwes: ['CWE-22'] },
  { id: 'GHSA-2', cve: 'CVE-2026-2', severity: 'low', summary: 'old scan', fixed: '8.3.2' },      // a scan from before the full text
]
const rows = [{ repo: 'web', ecosystem: 'npm', name: 'vite', version: '8.3.1', declared: '^8.3.1', scope: 'dev', category: 'build',
  language: 'JavaScript', source: 'web:package.json', managedBy: null, vulns }]
const item = matrix(rows).items[0]
const render = (scanned = true) => renderToStaticMarkup(<Library item={item} rows={rows} scanned={scanned} srv={srv} jobs={null} onChanged={() => {}} />)

afterEach(() => setLang('es'))

test('Libraries is its own section of the app', () => {
  const out = renderToStaticMarkup(<Libs srv={srv} jobs={null} />)
  expect(out).toContain('Librerías')
  expect(out).toContain('Buscar vulnerabilidades')
})

test('a library opens on why it is there: the repo, its manifest, the range and the scope', () => {
  const out = render()
  expect(out).toContain('Por qué está aquí')
  expect(out).toContain('<code>package.json</code>')
  expect(out).toContain('<code>^8.3.1</code>')
  expect(out).toContain('desarrollo')
})

test('why it is flagged: each advisory once, the worst first, with its affected versions and its full text', () => {
  const out = render()
  expect(out).toContain('2 aviso(s) de seguridad')
  expect(out.indexOf('CVE-2026-1')).toBeLessThan(out.indexOf('CVE-2026-2'))
  expect(out).toContain('desde 8.0.0, corregida en 8.3.3')
  expect(out).toContain('The full text of the advisory.')
  expect(out).toContain('CWE-22')
  expect(out).toContain('href="https://example.org/a"')
  expect(out).toContain('busca vulnerabilidades otra vez para leerlo aquí')    // the old scan's advisory says how to get it
})

test('update offers the version that fixes every advisory', () => {
  const out = render()
  expect(out).toMatch(/value="8\.3\.3"/)
  expect(out).toContain('Actualizar')
})

test('before any scan it says so instead of claiming the library is clean', () => {
  const out = render(false)
  expect(out).toContain('Aún sin buscar vulnerabilidades')
  expect(out).not.toContain('Ningún aviso conocido')
})

const maven = [
  { repo: 'api', ecosystem: 'Maven', name: 'org.springframework:spring-webmvc', version: '6.1.21', declared: '', scope: 'runtime',
    category: 'framework', language: 'Java', source: 'api:core/pom.xml', managedBy: 'com.acme:services:2.0', vulns: [] },
  { repo: 'web', ecosystem: 'Maven', name: 'org.springframework:spring-webmvc', version: '6.1.9', declared: '6.1.9', scope: 'runtime',
    category: 'framework', language: 'Java', source: 'web:pom.xml', managedBy: null, vulns: [] },
  { repo: 'gw', ecosystem: 'Maven', name: 'io.quarkus:quarkus-rest', version: null, declared: '', scope: 'runtime', category: 'framework',
    language: 'Java', source: 'gw:pom.xml', managedBy: 'io.quarkus.platform:quarkus-bom:3.22.3, io.quarkus.platform:quarkus-camel-bom:3.22.3', vulns: [] },
]

test('each library says its versions next to its name, and a BOM it cannot read instead of a blank', () => {
  const out = renderToStaticMarkup(<LibTable m={matrix(maven)} rows={maven} inv={{ libraries: maven, vulns: null }} open={null} setOpen={() => {}} srv={srv} jobs={null} onChanged={() => {}} />)
  expect(out).toContain('<th>Versión</th>')
  expect(out).toContain('6.1.9 · 6.1.21')
  expect(out).toContain('quarkus-bom 3.22.3')
  expect(out).toContain('title="La fija io.quarkus.platform:quarkus-bom:3.22.3, io.quarkus.platform:quarkus-camel-bom:3.22.3"')
})

test('a scan in progress says which repo it is on, out of how many, and why the first one is slow', () => {
  const c = { running: true, job: { status: 'running', lines: ['[1/17] web: scanning for known vulnerabilities (offline database)…'] } }
  const out = renderToStaticMarkup(<ScanStatus c={c} cves />)
  expect(out).toContain('<progress')
  expect(out).toContain('Buscando vulnerabilidades en web (1 de 17)')
  expect(out).toContain('La primera vez descarga')
})

test('a finished scan says it ended well even when it found vulnerabilities', () => {
  const c = { running: false, job: { status: 'done', lines: ['[1/1] web: scanning…', '✔ 3 libraries with known vulnerabilities'] } }
  const out = renderToStaticMarkup(<ScanStatus c={c} cves />)
  expect(out).toContain('Hecho')
  expect(out).not.toContain('Falló')
  expect(out).not.toContain('<progress')
})

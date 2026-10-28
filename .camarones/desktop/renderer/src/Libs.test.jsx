import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { matrix } from '@camaron/ui/libs.js'
import Libs, { Library, ScanStatus, Where } from './sections/Libs.jsx'
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

test('a line of the table names its repos, the flagged ones first, so their columns need no scrolling', () => {
  const many = ['wallet-adapter', 'backoffice-app', 'integration-service', 'lobby-service', 'content-service']
    .map((repo) => ({ ...rows[0], repo, vulns: repo === 'integration-service' ? vulns : [] }))
  const out = renderToStaticMarkup(<Where item={matrix(many).items[0]} />)
  expect(out).toMatch(/^<span class="dk-where[^"]*">en <b class="dk-where-bad">integration-service<\/b>/)
  expect(out.indexOf('integration-service')).toBeLessThan(out.indexOf('backoffice-app'))
  expect(out).toContain('+2 más')
  expect(out).not.toContain('wallet-adapter')
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

// The scan as it goes, then a tick once it is done. `c` is useCmd's state: {job: {status, lines, result, stopped}, error}.
const scan = (job, cves = true) => renderToStaticMarkup(<ScanStatus c={{ job, error: '', running: job?.status === 'running', stop: () => {} }}
  cves={cves} onClose={() => {}} />)
const progress = ['[1/3] api: scanning for known vulnerabilities (offline database)…', '[2/3] web: scanning for known vulnerabilities…']
const found = { libraries: [...rows, { ...rows[0], repo: 'api' }, { ...rows[0], name: 'react', vulns: [] }],
  vulns: { scanned: 3, failed: [], online: false, vulnerable: 2, at: '2026-10-27T10:00:00+00:00' } }

test('nothing is drawn before a scan starts', () => {
  expect(scan(null)).toBe('')
})

test('a scan that has not counted a repo yet says it is getting ready, with a bar that moves and a way to stop', () => {
  const out = scan({ status: 'running', lines: [] })
  expect(out).toContain('role="status"')
  expect(out).toContain('Preparando el escáner')
  expect(out).toContain('dk-bar indeterminate')
  expect(out).toMatch(/<button[^>]*>Parar<\/button>/)
})

test('a running scan names the repo it reads, how far it is and ticks the repos done', () => {
  const out = scan({ status: 'running', lines: progress })
  expect(out).toContain('Buceando en web')
  expect(out).toContain('repo 2 de 3')
  expect(out).toMatch(/<li class="done">✓ api<\/li>/)
  expect(out).toMatch(/<li class="current"><i><\/i>web<\/li>/)
  expect(out).toContain('1 más')
  expect(out).not.toContain('dk-tick')
})

test('a reread says it reads the manifests', () => {
  expect(scan({ status: 'running', lines: [] }, false)).toContain('Leyendo los manifiestos')
})

test('a finished scan draws its tick and says what it found, by library', () => {
  const out = scan({ status: 'done', lines: progress, result: found })
  expect(out).toContain('class="dk-tick"')
  expect(out).toContain('Escaneo terminado')
  expect(out).toContain('3 repos revisados · 1 librerías con avisos conocidos')   // vite in two repos is one library
  expect(out).toContain('aria-label="Cerrar"')
})

test('a clean scan says no library has a known advisory, and names the repos it could not scan', () => {
  const clean = { libraries: [{ ...rows[0], vulns: [] }], vulns: { ...found.vulns, scanned: 2, failed: ['worker'], vulnerable: 0 } }
  const out = scan({ status: 'done', lines: [], result: clean })
  expect(out).toContain('2 repos revisados · ninguna librería con avisos conocidos')
  expect(out).toContain('No se pudo escanear: worker.')
})

test('without OSV-Scanner there is no tick: it warns, with the reason the scan gave', () => {
  const out = scan({ status: 'done', lines: ['⚠ osv-scanner: download failed (offline)'], result: { libraries: rows, vulns: null } })
  expect(out).not.toContain('dk-tick')
  expect(out).toContain('OSV-Scanner no está disponible en esta máquina')
  expect(out).toContain('osv-scanner: download failed (offline)')
})

test('a finished reread ticks and counts libraries and repos', () => {
  const out = scan({ status: 'done', lines: [], result: found }, false)
  expect(out).toContain('class="dk-tick"')
  expect(out).toContain('Librerías releídas')
  expect(out).toContain('2 librerías en 2 repos')
})

test('a failed or stopped scan shows the command output, not a tick', () => {
  expect(scan({ status: 'failed', lines: ['boom'], rc: 2 })).toContain('Falló')
  const stopped = scan({ status: 'failed', lines: progress, stopped: true })
  expect(stopped).toContain('Parado')
  expect(stopped).not.toContain('dk-tick')
})

test('the scan speaks English too', () => {
  setLang('en')
  expect(scan({ status: 'running', lines: progress })).toContain('Diving into web')
  expect(scan({ status: 'done', lines: [], result: found })).toContain('Scan finished')
})

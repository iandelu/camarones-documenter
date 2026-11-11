import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import Libs, { Actions, ScanStatus, Update } from './sections/Libs.jsx'
import { setLang, t } from './i18n.js'

const srv = { get: () => new Promise(() => {}), post: () => new Promise(() => {}) }
const vulns = [{ id: 'GHSA-1', cve: 'CVE-2026-1', severity: 'high', score: 7.5, summary: 'launch-editor check bypassed', fixed: '8.3.3' }]
const rows = [{ repo: 'web', ecosystem: 'npm', name: 'vite', version: '8.3.1', declared: '^8.3.1', scope: 'dev', category: 'build',
  language: 'JavaScript', source: 'web:package.json', managedBy: null, vulns }]
const idle = { job: null, error: '', running: false, stop: () => {} }

afterEach(() => setLang('es'))

test('Libraries is its own section of the app, with a title while it loads', () => {
  const out = renderToStaticMarkup(<Libs srv={srv} jobs={null} />)
  expect(out).toContain('Librerías')
})

test('its actions: scan, look for newer versions, reread, and the portal', () => {
  const out = renderToStaticMarkup(<Actions c={idle} run={() => {}} />)
  expect(out).toContain('Buscar vulnerabilidades')
  expect(out).toContain(t('lb.lookGo'))
  expect(out).toContain('Releer del código')
  expect(out).toContain('Abrir en el portal')
})

test('update proposes the latest version with both suggestions, the chosen one pressed', () => {
  const out = renderToStaticMarkup(<Update row={rows[0]} proposal={{ version: '9.0.0', fix: '8.3.3', latest: '9.0.0' }} srv={srv} jobs={null} onChanged={() => {}} />)
  expect(out).toMatch(/value="9\.0\.0"/)
  expect(out).toMatch(/aria-pressed="true"[^>]*>[^<]*9\.0\.0/)
  expect(out).toContain('Actualizar')
})

test('update with nothing to propose leaves the field empty for the person', () => {
  const out = renderToStaticMarkup(<Update row={rows[0]} proposal={{ version: '', fix: null, latest: null }} srv={srv} jobs={null} onChanged={() => {}} />)
  expect(out).toMatch(/value=""/)
  expect(out).not.toContain('aria-pressed')
})

// The scan as it goes, then a tick once it is done. `c` is useCmd's state: {job: {status, lines, result, stopped}, error}.
const scan = (job, mode = 'cves') => renderToStaticMarkup(<ScanStatus c={{ job, error: '', running: job?.status === 'running', stop: () => {} }}
  mode={mode} onClose={() => {}} />)
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
  expect(scan({ status: 'running', lines: [] }, 'read')).toContain('Leyendo los manifiestos')
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
  const out = scan({ status: 'done', lines: [], result: found }, 'read')
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

test('a lookup as it goes names the library and counts, without the repo chips of a scan', () => {
  const out = scan({ status: 'running', lines: ['[3/40] newer versions · org.postgresql:postgresql'] }, 'latest')
  expect(out).toContain(t('lb.looking', { name: 'org.postgresql:postgresql' }))
  expect(out).toContain(t('lb.lookCount', { n: 3, total: 40 }))
  expect(out).not.toContain('dk-scan-repos')
  expect(scan({ status: 'running', lines: [] }, 'latest')).toContain(t('lb.lookPrep'))
})

test('a finished lookup ticks, counts the newer ones and names the registries it could not reach', () => {
  const result = { libraries: [{ ...rows[0], vulns: [] }],
    latest: { at: '2026-11-11T10:00:00+00:00', checked: 40, found: 38, failed: ['npm'], versions: { 'npm|vite': '9.0.0' } } }
  const out = scan({ status: 'done', lines: [], result }, 'latest')
  expect(out).toContain('class="dk-tick"')
  expect(out).toContain(t('lb.looked'))
  expect(out).toContain(t('lb.lookedWhat', { checked: 40, n: 1 }))
  expect(out).toContain(t('lb.lookFailedShort', { registries: 'npm' }))
})

test('Quality reads the severity words and states from Libraries, in the app language', async () => {
  const { SEV, sevWord } = await import('./sections/Libs.jsx')
  expect(SEV.high).toBe('bad')
  expect(SEV.medium).toBe('warn')
  expect(sevWord('high')).toBe('altas')
  expect(sevWord('weird')).toBe('weird')
})

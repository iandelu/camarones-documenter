import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { t } from '../i18n/index.js'
import { fill, LibrariesBoard, LibraryDetail } from './libs.jsx'
import { matrix } from './libs.js'

const rows = [
  { repo: 'api', ecosystem: 'Maven', name: 'org.postgresql:postgresql', version: '42.6.0', declared: '42.6.0', scope: 'runtime',
    category: 'data', language: 'Java', source: 'api:pom.xml', managedBy: null,
    vulns: [{ id: 'GHSA-1', cve: 'CVE-2024-1597', severity: 'critical', score: 9.8, summary: 'SQL injection', fixed: '42.6.1' }] },
  { repo: 'web', ecosystem: 'npm', name: 'rxjs', version: '7.8.1', declared: '^7.8.1', scope: 'runtime', category: 'other',
    language: 'JavaScript', source: 'web:package.json', managedBy: null, vulns: [] },
  { repo: 'web', ecosystem: 'npm', name: '@angular/core', version: '16.2.1', declared: '^16.2.1', scope: 'runtime',
    category: 'framework', language: 'JavaScript', source: 'web:package.json', managedBy: null, vulns: [] }]
const latest = { at: '2026-11-11T10:00:00+00:00', checked: 3, found: 3, failed: [],
  versions: { 'Maven|org.postgresql:postgresql': '42.7.4', 'npm|rxjs': '7.8.1', 'npm|@angular/core': '19.0.5' } }
const inv = { libraries: rows, vulns: { scanned: 2, failed: [], online: false, vulnerable: 1, at: '2026-11-10T10:00:00+00:00' }, latest }
const en = (k) => t(k, 'en')
const itemOf = (key) => matrix(rows).items.find((x) => x.key === key)
const board = (props) => renderToStaticMarkup(<LibrariesBoard inv={inv} {...props} />)

test('one line per library with its version and the latest, no column per repo', () => {
  const out = board()
  expect(out).toContain('<col style="width:46%"/>')
  expect(out).not.toContain('<th>api</th>')
  expect(out).toContain('42.6.0')
  expect(out).toContain('42.7.4')
  expect(out).toContain(en('lb.major'))                         // 16 → 19
  expect(out).toContain(en('lb.upToDate'))                      // rxjs
  expect(out).not.toContain('overflow')
})

test('up to date and clean lines have no Update button; the others do', () => {
  expect(board().match(new RegExp(`>${en('lb.updateOpen')} ▾<`, 'g'))).toHaveLength(2)
})

test('read-only: no actions, the note says where it is done', () => {
  const out = board()
  expect(out).toContain('camaron inventory --cves --latest')
  expect(out).not.toContain('data-tour="libs-actions"')
  expect(out).toContain('data-tour="libs-filters"')
  expect(out).toContain('data-tour="libs-table"')
})

test('with actions: they are drawn with what each one sends out', () => {
  const out = board({ actions: <button>scan</button>, status: <p>running</p> })
  expect(out).toContain('data-tour="libs-actions"')
  expect(out).toContain(en('lb.sends'))
  expect(out).toContain('running')
  expect(out).not.toContain('camaron inventory --cves --latest')
})

test('an open library puts the update first: the bump command in the portal, the app control when given', () => {
  const key = 'Maven|org.postgresql:postgresql'
  const portal = renderToStaticMarkup(<LibraryDetail item={itemOf(key)} rows={[rows[0]]} latest={latest} scanned renderUpdate={null} />)
  expect(portal).toContain('camaron bump api org.postgresql:postgresql 42.7.4')
  expect(portal.indexOf('camaron bump')).toBeLessThan(portal.indexOf('CVE-2024-1597'))
  expect(portal).toContain(fill(en('lb.fixes'), { v: '42.6.1' }))
  expect(portal).toContain(fill(en('lb.latestIs'), { v: '42.7.4' }))
  const app = renderToStaticMarkup(<LibraryDetail item={itemOf(key)} rows={[rows[0]]} latest={latest} scanned
    renderUpdate={(row, p) => <i>update {row.repo} to {p.version}</i>} />)
  expect(app).toContain('update api to 42.7.4')
  expect(app).not.toContain('camaron bump')
})

test('an inventory from an older kit: latest shows a dash and the outdated filter is hidden', () => {
  const out = renderToStaticMarkup(<LibrariesBoard inv={{ libraries: rows, vulns: null }} />)
  expect(out).toContain('—')
  expect(out).not.toContain(en('lb.onlyOutdated'))
  expect(out).toContain(en('lb.neverLooked'))
  expect(out).toContain(en('lb.cvNever'))
})

test('a lookup that could not reach a registry says so with the date of the versions shown', () => {
  const out = renderToStaticMarkup(<LibrariesBoard inv={{ ...inv, latest: { ...latest, failed: ['npm'] } }} />)
  expect(out).toContain(fill(en('lb.lookFailed'), { registries: 'npm', day: '2026-11-11' }))
})

test('the summary counts the libraries with a newer version', () => {
  expect(board()).toContain(fill(en('lb.newer'), { n: 2 }))
})

test('opened from #/libs/<repo>, the repo filter starts on it', () => {
  const out = board({ repo: 'web' })
  expect(out).toContain('<option value="web" selected="">')
  expect(out).not.toContain('org.postgresql:postgresql')
})

// Moved from the desktop app's tests with the detail itself: the advisories as the last scan kept them.
const full = [
  { id: 'GHSA-1', cve: 'CVE-2026-1', severity: 'high', score: 7.5, summary: 'launch-editor check bypassed', fixed: '8.3.3',
    aliases: ['CVE-2026-1'], details: 'The full text of the advisory.', published: '2026-10-01T00:00:00Z', modified: null,
    ranges: [{ introduced: '8.0.0', fixed: '8.3.3' }], references: [{ type: 'ADVISORY', url: 'https://example.org/a' }], cwes: ['CWE-22'] },
  { id: 'GHSA-2', cve: 'CVE-2026-2', severity: 'low', summary: 'old scan', fixed: '8.3.2' }]
const vite = [{ repo: 'web', ecosystem: 'npm', name: 'vite', version: '8.3.1', declared: '^8.3.1', scope: 'dev', category: 'build',
  language: 'JavaScript', source: 'web:package.json', managedBy: null, vulns: full }]
const detail = (scanned = true) => renderToStaticMarkup(<LibraryDetail item={matrix(vite).items[0]} rows={vite} latest={null} scanned={scanned} />)

test('why it is flagged: each advisory once, the worst first, with its affected versions and its full text', () => {
  const out = detail()
  expect(out).toContain(fill(en('lb.flaggedLead'), { n: 2 }))
  expect(out.indexOf('CVE-2026-1')).toBeLessThan(out.indexOf('CVE-2026-2'))
  expect(out).toContain(fill(en('lb.range'), { from: '8.0.0', to: '8.3.3' }))
  expect(out).toContain('The full text of the advisory.')
  expect(out).toContain('CWE-22')
  expect(out).toContain('href="https://example.org/a"')
  expect(out).toContain(en('lb.rescan'))                        // the old scan's advisory says how to get it
})

test('why it is there: the repo, its manifest, the range and the scope; without a lookup the fix is proposed', () => {
  const out = detail()
  expect(out).toContain('<code>package.json</code>')
  expect(out).toContain('<code>^8.3.1</code>')
  expect(out).toContain(en('lb.scope.dev'))
  expect(out).toContain('camaron bump web vite 8.3.3')
})

test('before any scan it says so instead of claiming the library is clean', () => {
  const out = detail(false)
  expect(out).toContain(en('lb.notScanned'))
  expect(out).not.toContain(en('lb.clean'))
})

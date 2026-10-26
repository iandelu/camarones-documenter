import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import HealthRepo from './HealthRepo.jsx'
import { STRINGS } from './i18n.js'

const en = STRINGS.en
const item = (over = {}) => ({ source: 'quality/tech-debt.md', trust: 'draft', item: 'Old ORM', impact: 'high', effort: 'M', evidence: ['api:src/Dao.java', 'api:src/main/', 'web:pom.xml'], owner: 'ana', recommendation: 'Replace it', ...over })
const full = {
  inventory: { scanned: true },
  repo_state: { api: 'bad', web: null },
  repos: {
    api: {
      cloned: true, vulns: { high: 1 },
      vulnerable: [{ name: 'lodash', version: '4.17.20', severity: 'high', id: 'GHSA-1', cve: 'CVE-2021-1', fixed: '4.17.21' }],
      sonar: { used: true, project: 'org_api', organization: 'org', host: 'sonarcloud.io', link: 'https://sonarcloud.io/dashboard?id=org_api' },
      coverage: { percent: 71.5, at: '2026-10-20', source: 'report', path: 'target/jacoco.xml' },
      reports: [{ type: 'jacoco', path: 'target/jacoco.xml', percent: 71.5, at: '2026-10-20' }],
      debt: [item()],
    },
    web: { cloned: true, vulns: {}, vulnerable: [], sonar: { used: false }, coverage: null, reports: [], debt: [] },
    off: { cloned: false },
    broken: { error: 'cannot read' },
  },
  docs: { stale: [{ path: 'domain/x.md', repos: ['api'] }], suspect: [] },
}
const html = (snapshot, name) => renderToStaticMarkup(<HealthRepo snapshot={snapshot} name={name} />)

test('a repo with everything: header links, quality, vulnerabilities, debt and pages', () => {
  const out = html(full, 'api')
  expect(out).toContain('<h1>api</h1>')
  expect(out).toContain('At risk')                                           // the state is a word, not only a colour
  expect(out).toContain('href="https://sonarcloud.io/dashboard?id=org_api" target="_blank" rel="noopener noreferrer"')
  expect(out).toContain('href="#/docs/repos/api/index.md"')
  expect(out).toContain('href="#/libs/api"')
  expect(out).toContain('71.5%')
  expect(out).toContain('href="https://osv.dev/vulnerability/GHSA-1"')
  expect(out).toContain('4.17.21')
  expect(out).toContain('Old ORM')
  expect(out).toContain('href="#/docs/quality/tech-debt.md"')
  expect(out).toContain('href="#/code/api/f/src/Dao.java"')                   // a file path links
  expect(out).not.toContain('href="#/code/api/f/src/main/')                   // a folder does not
  expect(out).toContain('src/main/')
  expect(out).toContain('href="#/code/web/f/pom.xml"')
  expect(out).toContain('href="#/docs/domain/x.md"')
})

test('empty states say what to do, in the words of the spec', () => {
  const out = html(full, 'web')
  expect(out).toContain(en.hrNoSonar)
  expect(out).toContain('sonar-project.properties')
  expect(out).toContain(en.hrNoCoverage)
  expect(out).toContain(en.hrNoDebt)
  expect(out).toContain(en.hrNoVulns)
  expect(out).toContain(en.hrNoDocs)
  expect(STRINGS.es.hrNoSonar).toBe('Este repo no usa Sonar')
  expect(STRINGS.es.hrNoCoverage).toBe('No hay informe de cobertura: se lee el que deja la build (JaCoCo, lcov, Cobertura)')
  expect(STRINGS.es.hrNoDebt).toBe('Aún no hay deuda registrada: la recoge la unidad «ADR, SLA, deuda técnica»')
  expect(STRINGS.es.hrUnknown).toBe('No existe ese repo')
})

test('a repo with no state is neutral and says so; no Sonar link without Sonar', () => {
  const out = html(full, 'web')
  expect(out).toContain('No state')
  expect(out).toContain('cu-hb-dot--none')
  expect(out).not.toContain('cu-hb-dot--ok')
  expect(out).not.toContain('Sonar dashboard')
})

test('vulnerabilities not scanned yet are not "none"', () => {
  const out = html({ ...full, inventory: { scanned: false } }, 'web')
  expect(out).toContain(en.hrNotScanned)
  expect(out).not.toContain(en.hrNoVulns)
})

test('a Sonar link that is not http(s) is not a link', () => {
  const bad = { ...full, repos: { api: { ...full.repos.api, sonar: { used: true, project: 'k', link: 'javascript:alert(1)' } } } }
  const out = html(bad, 'api')
  expect(out).not.toContain('javascript:')
  expect(out).not.toContain('Sonar dashboard')
})

test('a block that failed shows its message in an Aviso, never a dash alone', () => {
  const broken = { ...full, repos: { api: { ...full.repos.api, sonar: { error: 'no token' }, coverage: { error: 'bad xml' }, vulnerable: { error: 'osv down' },
    debt: { error: 'page unreadable' } } }, docs: { error: 'docs unreadable' } }
  const out = html(broken, 'api')
  for (const msg of ['no token', 'bad xml', 'osv down', 'page unreadable', 'docs unreadable']) expect(out).toContain(msg)
  expect(out.match(/cu-aviso/g).length).toBeGreaterThanOrEqual(5)
})

test('a missing value is a dash, never 0', () => {
  const sparse = { ...full, repos: { api: { cloned: true, vulnerable: [{ severity: 'low' }], coverage: { percent: null }, reports: [{ type: 'lcov', path: 'lcov.info' }], sonar: { used: true } } } }
  const out = html(sparse, 'api')
  expect(out).toContain('—')
  expect(out).not.toMatch(/>0%</)
})

test('a repo that is not cloned or could not be read says so; an unknown one links back', () => {
  expect(html(full, 'off')).toContain('Not cloned')
  expect(html(full, 'broken')).toContain('cannot read')
  const out = html(full, 'nope')
  expect(out).toContain(en.hrUnknown)
  expect(out).toContain('href="#/health"')
})

// ---- step (c) ----

const server = (over = {}) => ({ at: '2026-10-26T08:00:00Z', host: 'https://secret-host.example', gate: 'ERROR', coverage: 81.5, bugs: 2, vulnerabilities: 0,
  security_hotspots: 1, code_smells: 40, debt_minutes: 1500, ratings: { maintainability: 'A', reliability: 'B', security: 'C' }, ...over })
const withSonar = (sonar, coverage) => ({ ...full, repos: { ...full.repos, api: { ...full.repos.api, sonar: { ...full.repos.api.sonar, ...sonar },
  ...(coverage && { coverage }) } } })

test('the Sonar figures, gate word and Sonar as the coverage source are on the page', () => {
  const out = html(withSonar({ server: server() }, { percent: 81.5, at: '2026-10-26T08:00:00Z', source: 'sonar', path: null }), 'api')
  expect(out).toContain(en.hrGate)
  expect(out).toContain('Failed')
  for (const label of [en.hrFigBugs, en.hrFigSmells, en.hrFigHotspots, en.hrFigDebt, en.hrFigMaintainability, en.hrFigReliability, en.hrFigSecurity]) expect(out).toContain(label)
  expect(out).toContain('3 d 1 h')
  expect(out).toContain('81.5%')
  expect(out).toContain('Sonar · 2026-10-26')
  expect(out).not.toContain('secret-host.example')                          // the host the figures came from is never drawn
})

test('the gate is a word with its dot, in Spanish too', () => {
  expect(STRINGS.es.hrGate).toBeTruthy()
  expect(html(withSonar({ server: server({ gate: 'OK' }) }), 'api')).toContain('cu-hb-dot--ok')
})

test('a Sonar error with kept values shows the values, how old they are and the reason', () => {
  const now = Date.parse('2026-10-29T08:00:00Z')
  const out = renderToStaticMarkup(<HealthRepo snapshot={withSonar({ server: server(), error: 'sin conexión' })} name="api" now={now} />)
  expect(out).toContain('sin conexión')
  expect(out).toContain('3 d 1 h')
  expect(out).toContain('Figures from 3 d ago')                           // via the kit's time helper
  expect(renderToStaticMarkup(<HealthRepo snapshot={withSonar({ server: server() })} name="api" now={now} />)).not.toContain('Figures from')
})

test('a Sonar error without values is the reason alone, no figures', () => {
  const out = html(withSonar({ error: 'proyecto no encontrado' }), 'api')
  expect(out).toContain('proyecto no encontrado')
  expect(out).not.toContain(en.hrFigBugs)
  expect(out).not.toContain(en.hrGate)
})

test('the app offers to connect; the portal only says a token is missing', () => {
  const out = html(withSonar({ connect: true }), 'api')
  expect(out).toContain(en.hrSonarNoToken)
  expect(out).not.toContain('kind=sonarqube')                               // no link: the portal runs nothing
  expect(html(withSonar({ connect: true, host: '' }), 'api')).toContain(en.hrSonarNoToken)
})

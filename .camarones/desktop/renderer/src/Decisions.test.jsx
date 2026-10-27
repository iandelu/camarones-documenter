import { readFileSync } from 'node:fs'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import Decisions, { AdrListView, CandidatesView, EvidenceView, LegacyView, NewFormView } from './sections/Decisions.jsx'
import { candidateFields } from './sections/adr/Candidates.jsx'
import { packLine } from './sections/adr/Evidence.jsx'
import { EMPTY, check, toBody } from './sections/adr/NewForm.jsx'
import { blocks } from './sections/adr/Prose.jsx'
import { ReadView, Stepper } from './sections/adr/Read.jsx'
import { TouchSearchView } from './sections/adr/TouchSearch.jsx'
import { setLang, t } from './i18n.js'

afterEach(() => setLang('es'))

const noop = () => {}
const html = (node, lang = 'es') => (setLang(lang), renderToStaticMarkup(node))
const list = (props, lang) => html(<AdrListView filter="all" q="" onFilter={noop} onQ={noop} {...props} />, lang)
const legacy = (props, lang) => html(<LegacyView onReview={noop} {...props} />, lang)
const evidence = (props, lang) => html(<EvidenceView onPack={noop} onWrite={noop} {...props} />, lang)
const form = (props, lang) => html(<NewFormView fields={EMPTY} errors={{}} onChange={noop} onSubmit={noop} search={async () => []}
  {...props} />, lang)

const row = (o) => ({ id: '0012', title: 'Sesiones en Redis', kind: 'new', chip: 'review', repos: ['api'],
  points: { total: 3, decided: 1 }, legacy: false, ...o })

test('the list shows rows, chips and the candidates strip in both languages', () => {
  const out = list({ rows: [row(), row({ id: '0011', title: 'JPA', kind: 'retro', chip: 'accepted' })],
                     candidates: [{ key: 'data:postgresql', label: 'postgresql', repos: ['api'] }] })
  for (const s of ['0012', 'Sesiones en Redis', 'En revisión', 'Aceptada', '1 decisión en el código sin ADR'])
    expect(out).toContain(s)
  expect(list({ rows: [row()], candidates: [{}, {}] })).toContain('2 decisiones en el código sin ADR')
  expect(list({ rows: [row()], candidates: [] }, 'en')).toContain('In review')
})

test('a legacy ADR opens read-only with a way into a session', () => {
  const out = legacy({ adr: { id: '0003', title: 'JPA', status: 'proposed', legacy: true, sections: { context: 'why' } } })
  expect(out).toContain('why')
  expect(out).toContain('Revisar en sesión')
  expect(out).not.toContain('<textarea')
})

test('an empty project invites the first decision', () => {
  expect(list({ rows: [], candidates: [] })).toContain('Nuevo ADR')
})

test('a candidate prefills a retroactive ADR', () => {
  const c = { key: 'data:postgresql', label: 'postgresql', manifests: ['api:pom.xml'] }
  expect(candidateFields(c, 'es')).toEqual({ kind: 'retro', title: '¿Por qué postgresql?', touches: ['api:pom.xml'] })
  expect(candidateFields(c, 'en').title).toBe('Why postgresql?')
})

test('the evidence step offers writing without AI and no research button in S1', () => {
  const out = evidence({ adr: { id: '0012', state: { phase: 'evidence', mode: 'manual' } },
                         pack: { summary: { files: 14, pages: 3, adrs: 1, commits: 31, c4: 2 }, markdown: '## Doc pages' } })
  expect(out).toContain('14 archivos')
  expect(out).toContain('Escribir sin IA')
  expect(out).not.toContain('Investigar')
})

// ---------- the list ----------
test('each row links to its ADR and says its kind, repos and points', () => {
  const out = list({ rows: [row()], candidates: [] })
  expect(out).toContain('href="#/decisions/0012"')
  expect(out).toContain('Nueva · api · puntos decididos: 1/3')
  expect(list({ rows: [row({ kind: 'retro', repos: ['api', 'vets'], points: { total: 0, decided: 0 } })], candidates: [] }))
    .toContain('Retro · api, vets')
})

test('an ADR the kit did not write lists as legacy, not as a kind it never had', () => {
  const out = list({ rows: [row({ legacy: true, kind: 'retro', chip: 'proposed' })], candidates: [] })
  expect(out).toContain('Heredada')
  expect(out).not.toContain('Retro ·')
  expect(out).toContain('Propuesta')
})

test('the filters count their rows; the filter and the search narrow the list', () => {
  const rows = [row(), row({ id: '0011', title: 'JPA', kind: 'retro', chip: 'accepted', repos: ['vets'] })]
  const out = list({ rows, candidates: [] })
  expect(out).toMatch(/aria-pressed="true">Todas <span class="dk-adr-n">2<\/span>/)
  expect(out).toContain('Aceptadas <span class="dk-adr-n">1</span>')
  expect(out).toContain('Sustituidas <span class="dk-adr-n">0</span>')
  const vets = list({ rows, q: 'vets', candidates: [] })
  expect(vets).toContain('JPA')
  expect(vets).not.toContain('Sesiones en Redis')
  const accepted = list({ rows, filter: 'accepted', candidates: [] })
  expect(accepted).toContain('JPA')
  expect(accepted).not.toContain('Sesiones en Redis')
})

test('a search that finds nothing says so and how to get out', () => {
  const out = list({ rows: [row()], q: 'zzz', candidates: [] })
  expect(out).toContain('Ninguna decisión coincide con «zzz»')
  expect(list({ rows: [row()], filter: 'superseded', candidates: [] })).toContain('Ver todas')
})

test('the header offers the candidates with their number and a new ADR', () => {
  const out = list({ rows: [row()], candidates: [{}, {}, {}] })
  expect(out).toContain('href="#/decisions/candidates"')
  expect(out).toContain('Candidatas · 3')
  expect(out).toMatch(/<a class="cu-btn cu-btn--primary" href="#\/decisions\/new">/)
  expect(list({ rows: [row()], candidates: null })).not.toContain('Candidatas ·')     // still being read
  expect(list({ rows: [row()], candidates: [] })).not.toContain('dk-adr-strip')
})

test('the strip names the first candidates, and the empty list keeps it', () => {
  const four = ['postgresql', 'kafka', 'redis', 'helm'].map((label) => ({ key: `x:${label}`, label }))
  expect(list({ rows: [row()], candidates: four })).toContain('postgresql, kafka, redis…')
  const empty = list({ rows: [], candidates: four })
  expect(empty).toMatch(/<a class="cu-btn cu-btn--primary" href="#\/decisions\/new">/)
  expect(empty).toContain('4 decisiones en el código sin ADR')
})

// ---------- the stepper ----------
test('the stepper marks where the ADR stands and leaves out what writing without AI skips', () => {
  const out = html(<Stepper phase="evidence" mode="manual" />)
  expect(out).toMatch(/aria-current="step"[^>]*>.*Evidencia/)
  expect(out).toContain('Problema')
  expect(out).not.toContain('Investigación')
  expect(html(<Stepper phase="evidence" mode="jury" />)).toContain('Investigación')
})

test('a rejected ADR ends on Rejected, never on Accepted', () => {
  const out = html(<Stepper phase="rejected" mode="manual" />)
  expect(out).toContain('Rechazado')
  expect(out).not.toContain('Aceptado')
  expect(html(<Stepper phase="rejected" mode="manual" />, 'en')).toContain('Rejected')
})

// ---------- evidence ----------
test('the pack reads in one line, singular and plural, the optional parts only when there are some', () => {
  setLang('es')
  expect(packLine({ files: 1, neighbours: 0, pages: 0, adrs: 1, commits: 0, c4: 0, libraries: 2, questions: 0 }, t))
    .toEqual(['1 archivo', '0 páginas de docs', '1 ADR relacionado', '0 commits', '0 elementos C4', '2 librerías'])
  setLang('en')
  expect(packLine({ files: 14, pages: 3 }, t)).toEqual(['14 files', '3 doc pages', '0 related ADRs', '0 commits', '0 C4 elements'])
  expect(packLine(undefined, t)[0]).toBe('0 files')
})

test('the pack opens as preformatted Markdown; with none, the way to gather it', () => {
  const adr = { id: '0012', title: 'Sesiones', state: { phase: 'evidence', mode: 'manual' } }
  const out = evidence({ adr, pack: { summary: { files: 1 }, markdown: '## Doc pages\n- `docs/a.md`' } })
  expect(out).toMatch(/<details[^>]*><summary>Ver paquete<\/summary><pre[^>]*>## Doc pages/)
  const none = evidence({ adr, pack: null })
  expect(none).toContain('Reunir la evidencia')
  expect(none).not.toContain('Ver paquete')
  expect(evidence({ adr, pack: undefined, packing: true })).toContain('Reuniendo la evidencia')
  expect(evidence({ adr, pack: null, packError: 'disk full' })).toContain('disk full')
})

test('the evidence step shows the problem as it was framed', () => {
  const adr = { id: '0012', title: 'Sesiones', kind: 'new', chip: 'running', repos: ['api'],
    state: { phase: 'evidence', mode: 'manual', problem: 'Hoy en memoria del pod.', drivers: ['latencia'], constraints: [],
             options_hint: ['Redis'], touches: ['api:src/Session.java'] } }
  const out = evidence({ adr, pack: null })
  for (const s of ['0012 · Sesiones', 'Hoy en memoria del pod.', 'latencia', 'Redis', 'src/Session.java', 'En curso']) expect(out).toContain(s)
  expect(evidence({ adr, pack: null }, 'en')).toContain('Write without AI')
})

// Spec §2.3: writing without AI brings the pack's evidence (lib/adr.py write_without_ai), and the step says so.
test('the evidence step says writing without AI brings the evidence of the pack', () => {
  const adr = { id: '0012', state: { phase: 'evidence', mode: 'manual' } }
  expect(evidence({ adr, pack: null })).toContain('la evidencia del paquete')
  expect(evidence({ adr, pack: null }, 'en')).toContain('evidence already in')
})

// One ADR's work never shows on another's screen: the screen is keyed by the ADR, so React drops its state with it.
test('each ADR gets a screen of its own', () => {
  const src = readFileSync(new URL('./sections/Decisions.jsx', import.meta.url), 'utf-8')
  expect(src).toMatch(/<AdrScreen key=\{r\.id\} id=\{r\.id\}/)
  expect(src).toMatch(/useReducer\(screen, notice, startScreen\)/)
})

test('every place of the section draws before its data comes', () => {
  const waiting = () => new Promise(() => {})
  const srv = { get: waiting, post: waiting }
  try {
    for (const [hash, shown] of [['#/decisions', 'cu-skel'], ['#/decisions/0012', 'ADR 0012'], ['#/decisions/candidates', 'Candidatas'],
      ['#/decisions/new', 'Crear y reunir la evidencia']]) {
      globalThis.location = { hash }
      expect(html(<Decisions srv={srv} />), hash).toContain(shown)
    }
  } finally { delete globalThis.location }
})

test('a write the server refused stays on the screen with its message', () => {
  const out = evidence({ adr: { id: '0012', state: { phase: 'evidence' } }, pack: null, error: 'write the ADR first' })
  expect(out).toMatch(/role="alert"/)
  expect(out).toContain('write the ADR first')
})

// ---------- reading an ADR ----------
test('a section reads as prose: code, bold and lists drawn, links kept as text, comments dropped', () => {
  const out = legacy({ adr: { id: '0003', title: 'JPA', status: 'accepted', sections: {
    context: 'Usa `JPA` y **Postgres** <!-- old -->', decision: '- a\n- b', evidence: '[ver](https://x.example)' } } })
  expect(out).toContain('<code>JPA</code>')
  expect(out).toContain('<strong>Postgres</strong>')
  expect(out).toContain('<li>a</li>')
  expect(out).not.toContain('old')
  expect(out).not.toContain('href="https')
  expect(out).toContain('Aceptada')
  expect(out.indexOf('Contexto')).toBeLessThan(out.indexOf('Decisión'))
})

test('the Markdown of a section splits into blocks', () => {
  expect(blocks('Hoy <!-- x --> en\nmemoria.\n\n### Sub\n\n- a\n- b\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```\nx = 1\n```\n> nota'))
    .toEqual([{ type: 'p', text: 'Hoy en memoria.' }, { type: 'h', level: 3, text: 'Sub' }, { type: 'ul', items: ['a', 'b'] },
      { type: 'table', head: ['A', 'B'], rows: [['1', '2']] }, { type: 'code', text: 'x = 1' }, { type: 'quote', text: 'nota' }])
  expect(blocks('')).toEqual([])
  expect(blocks(null)).toEqual([])
  expect(blocks('1. uno\n2. dos')).toEqual([{ type: 'ol', items: ['uno', 'dos'] }])
})

test('an ADR with nothing to read says so', () => {
  expect(legacy({ adr: { id: '0004', status: 'unknown', sections: {} } })).toContain('no tiene secciones')
})

test('an ADR in review reads with its stepper until the review screen takes it', () => {
  const out = html(<ReadView adr={{ id: '0012', title: 'S', chip: 'review', state: { phase: 'review', mode: 'manual' },
    sections: { context: 'Hoy' } }} />)
  expect(out).toMatch(/aria-current="step"[^>]*>.*Revisión/)
  expect(out).toContain('Hoy')
})

// ---------- the new-ADR form ----------
test('the form asks for the title, the kind, the problem, the lists, Toca and what it supersedes', () => {
  const out = form({ next: '0014', accepted: [row({ id: '0011', title: 'JPA', chip: 'accepted' })] })
  for (const s of ['Título', 'Nueva', 'Retroactiva', 'El problema', 'Drivers', 'Restricciones', 'Opciones', 'Toca', 'Sustituye a',
    '0014', '<option value="0011">0011 · JPA</option>', 'Crear y reunir la evidencia']) expect(out).toContain(s)
  expect(out).toMatch(/<input type="radio"(?=[^>]*value="new")(?=[^>]*checked="")/)
  expect(out.match(/<textarea/g)).toHaveLength(4)
  expect(out).not.toMatch(/Afinar|Investigar/)
})

test('a prefilled form says where it came from and keeps what came', () => {
  const fields = { ...EMPTY, ...candidateFields({ label: 'postgresql', manifests: ['api:pom.xml'] }, 'es') }
  const out = form({ fields, prefilled: true })
  expect(out).toContain('Viene de una candidata')
  expect(out).toContain('value="¿Por qué postgresql?"')
  expect(out).toMatch(/<input type="radio"(?=[^>]*value="retro")(?=[^>]*checked="")/)
  expect(out).toContain('pom.xml')
})

test('a form without a title says what is missing; a refusal shows the server message', () => {
  const out = form({ errors: check(EMPTY) })
  expect(out).toContain('Escribe un título.')
  expect(out).toMatch(/id="adr-f-title"[^>]*aria-invalid="true"|aria-invalid="true"[^>]*id="adr-f-title"/)
  expect(form({ error: 'kind must be one of new, retro' })).toContain('kind must be one of new, retro')
})

test('the form checks the title and turns its lines into the body the server takes', () => {
  expect(check(EMPTY)).toEqual({ title: true })
  expect(check({ ...EMPTY, title: '  x ' })).toEqual({})
  expect(toBody({ ...EMPTY, title: '  Sesiones  ', problem: ' p ', drivers: 'a\n\n b \n', options: 'Redis\r\nPostgres',
                  touches: ['api:x'] }))
    .toEqual({ title: 'Sesiones', kind: 'new', problem: 'p', drivers: ['a', 'b'], constraints: [], options_hint: ['Redis', 'Postgres'],
               touches: ['api:x'] })
  expect(toBody({ ...EMPTY, title: 'x', supersedes: '0011' }).supersedes).toBe('0011')
})

// ---------- Toca ----------
const hits = [{ touch: 'api:src/Session.java', group: 'api/session', kind: 'file' },
  { touch: 'api:session', kind: 'group', files: ['api:a', 'api:b'] }, { touch: 'cam-docs:docs/s.md', kind: 'page', title: 'Sesiones' }]
const touch = (props) => html(<TouchSearchView id="t" label="Toca" q="" hits={null} touches={[]} onQ={noop} onPick={noop} onRemove={noop} {...props} />)

test('Toca lists files, groups and pages, and the picked ones as chips you can remove', () => {
  const out = touch({ q: 'ses', hits, touches: ['api:pom.xml'] })
  for (const s of ['api:src/Session.java', 'archivo · api/session', 'grupo · 2 archivos', 'Sesiones', 'página de docs', 'pom.xml',
    'aria-label="Quitar api:pom.xml"']) expect(out).toContain(s)
})

test('Toca says when nothing matches or the search failed', () => {
  expect(touch({ q: 'zzz', hits: [] })).toContain('coincide con «zzz»')
  const failed = touch({ q: 'x', error: 'boom' })
  expect(failed).toContain('No he podido buscar')
  expect(failed).toContain('boom')
  expect(touch({})).toContain('Aún no toca nada.')
})

// ---------- candidates ----------
test('the candidates group by what they are, with their repos and a way to write each one', () => {
  const out = html(<CandidatesView onPick={noop} rows={[
    { key: 'data:postgresql', label: 'postgresql', category: 'data', repos: ['api', 'vets'], manifests: ['api:pom.xml'] },
    { key: 'deploy:helm', label: 'Helm', category: 'deploy', repos: ['api'], manifests: ['api:chart/Chart.yaml'] }]} />)
  for (const s of ['postgresql', 'Datos', 'api, vets', 'Helm', 'Despliegue', 'api:pom.xml']) expect(out).toContain(s)
  expect(out.match(/Crear ADR retro/g)).toHaveLength(2)
  expect(html(<CandidatesView onPick={noop} rows={[{ key: 'odd:x', label: 'x', category: 'odd', repos: [] }]} />)).toContain('odd')
})

test('no candidates says why and where to go', () => {
  const out = html(<CandidatesView rows={[]} onPick={noop} />)
  expect(out).toContain('Ninguna decisión del código está sin ADR')
  expect(out).toContain('href="#/libs"')
})

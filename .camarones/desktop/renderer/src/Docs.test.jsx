import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import Docs, { AnswerView, BuildCard, WikiBlock } from './sections/Docs.jsx'
import { wikiBlocks } from './docs.js'
import { setLang } from './i18n.js'

const srv = { get: () => new Promise(() => {}), post: () => new Promise(() => {}) }
// Every repo of the project is in `repos`; only api and ui have wiki pages yet.
const index = { repos: ['api', 'web', 'ui'], docs: [{ path: 'repos/api/index.md', space: 'wiki' }, { path: 'repos/ui/a.md', space: 'wiki' },
  { path: 'index.md', space: 'docs' }] }
const render = (idx = index) => renderToStaticMarkup(<Docs srv={srv} jobs={null} app={{ openExternal: () => {} }} index={idx} />)

afterEach(() => { delete globalThis.location; setLang('es') })

// Reading is the portal's, in the system browser: buttons that call app.openExternal, never a link the window follows.
test('Docs opens the portal through the browser and offers the C4 build', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  const out = render()
  expect(out).not.toMatch(/<a [^>]*href=/)
  for (const label of ['Leer la documentación', 'Revisar borradores', 'Buscar o preguntar']) expect(out).toContain(label)
  expect(out).toContain('Construir el explorador C4')
  expect(out).toMatch(/aria-label="Construir: Construir el explorador C4"/)
})

// One block per repo, with or without a wiki: Generate on each (it chooses the repo and writes the starter brief), the
// graph build only where there are pages to graph.
test('one wiki block per repo of the project, each with its own Generate button', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  const out = render()
  for (const repo of ['api', 'web', 'ui']) {
    expect(out).toContain(`Wiki · ${repo}`)
    expect(out).toMatch(new RegExp(`aria-label="Generar la wiki: Wiki · ${repo}">Generar la wiki</button>`))
  }
  expect(out.match(/>Generar la wiki</g)).toHaveLength(3)
  expect(out).toContain('Elige este repo para tener wiki y escribe un brief inicial sin IA si aún no tiene')
  expect(out).toContain('Grafo del wiki · api')               // the graph build is where the wiki has pages…
  expect(out).toContain('Grafo del wiki · ui')
  expect(out).not.toContain('Grafo del wiki · web')           // …and not before the first generation
  expect(out).toMatch(/aria-label="Ver: Wiki · api"/)
  expect(out).not.toMatch(/aria-label="Ver: Wiki · web"/)
  expect(out.match(/cu-btn--primary/g)).toHaveLength(1 + 3 + 1)   // Leer + a Generate per repo + Preguntar: one per card
})

test('with no repos there is no wiki block; the Ask card is still there', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  const out = render({ repos: [], docs: [] })
  expect(out).not.toContain('Generar la wiki')
  expect(out).toContain('Construir el explorador C4')
  expect(out).toContain('Preguntar con IA')
})

test('Ask has a question field and a Preguntar button', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  const out = render()
  expect(out).toContain('Preguntar con IA')
  expect(out).toMatch(/<input[^>]*aria-label="Pregunta"/)
  expect(out).toMatch(/>Preguntar<\/button>/)
})

test('the strings exist in English', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  setLang('en')
  const out = render()
  expect(out).toContain('Wiki · api')
  expect(out).toContain('Generate the wiki')
  expect(out).toContain('Picks this repo for a wiki and writes a starter brief without AI if it has none')
  expect(out).toContain('Ask with AI')
  expect(out).toMatch(/aria-label="Question"/)
  expect(out).toMatch(/>Ask<\/button>/)
})

// A failed build says so in the person's language, the button becomes Retry, and the repeated buttons are told apart.
test('a failed build offers Retry, localized, and every button names its card', () => {
  const failed = { job: null, error: 'Failed to fetch', running: false, run: () => {} }
  const out = renderToStaticMarkup(<BuildCard title="Grafo del wiki · api" hint="h" build={failed} onBuild={() => {}} onView={() => {}} />)
  expect(out).toContain('No llego al servidor del proyecto.')
  expect(out).not.toContain('Failed to fetch')
  expect(out).toMatch(/<button type="button" class="cu-btn cu-btn--secondary cu-btn--sm" aria-label="Reintentar: Grafo del wiki · api">Reintentar<\/button>/)
  expect(out).toMatch(/aria-label="Ver: Grafo del wiki · api">Ver<\/button>/)
  const fresh = renderToStaticMarkup(<BuildCard title="T" hint="h" build={{ job: null, error: '', running: false }} onBuild={() => {}} onView={() => {}} />)
  expect(fresh).toMatch(/aria-label="Construir: T">Construir<\/button>/)
})

// The answer is plain text with its sources as buttons (the window never follows a link to the portal).
test('an answer shows its text and its sources; "none" says so in the app\'s language', () => {
  const view = { kind: 'answer', text: 'It uses JWT.', by: 'claude (haiku)',
    sources: [{ cite: 'architecture/overview.md#Context', hash: '#/docs/architecture/overview.md::Context' }] }
  const out = renderToStaticMarkup(<AnswerView view={view} onOpen={() => {}} />)
  expect(out).toContain('It uses JWT.')
  expect(out).toContain('claude (haiku)')
  expect(out).toMatch(/aria-label="Ver: architecture\/overview.md#Context">architecture\/overview.md#Context<\/button>/)
  expect(out).not.toMatch(/<a [^>]*href=/)
  const bare = renderToStaticMarkup(<AnswerView view={{ ...view, sources: [] }} onOpen={() => {}} />)
  expect(bare).not.toContain('Fuentes')
  expect(renderToStaticMarkup(<AnswerView view={{ kind: 'none' }} onOpen={() => {}} />)).toContain('No he encontrado')
  setLang('en')
  expect(renderToStaticMarkup(<AnswerView view={{ kind: 'none' }} onOpen={() => {}} />)).toContain('I found nothing')
})

// A repo that cannot be generated says why, in the person's language, and its Generate button is closed: the portal
// offered it only for a cloned repo with a wiki engine (canGenerate).
const wikis = [{ repo: 'api', pages: 3, cloned: true, chosen: true, brief: 'ai', canGenerate: true },
  { repo: 'web', pages: 0, cloned: false, chosen: false, brief: null, canGenerate: false },
  { repo: 'ui', pages: 0, cloned: true, chosen: true, brief: null, canGenerate: false }]
const block = (i, props = {}) => renderToStaticMarkup(
  <WikiBlock srv={srv} jobs={null} block={wikiBlocks({ repos: ['api', 'web', 'ui'] }, wikis)[i]} onView={() => {}} onDone={() => {}} {...props} />)
const generate = (out) => out.match(/<button[^>]*aria-label="Generar la wiki[^"]*"[^>]*>/)[0]

test('Generate is enabled for a cloned repo with an engine, closed with its reason otherwise', () => {
  const ok = block(0)
  expect(generate(ok)).not.toContain('disabled')
  expect(ok).not.toContain('no está clonado')
  const uncloned = block(1)
  expect(generate(uncloned)).toContain('disabled')
  expect(uncloned).toContain('Este repo aún no está clonado')
  expect(uncloned).toContain('Máquina')
  const noEngine = block(2)
  expect(generate(noEngine)).toContain('disabled')
  expect(noEngine).toContain('No hay ningún motor de wiki instalado')
  expect(noEngine).not.toContain('aún no está clonado')
  setLang('en')
  expect(block(1)).toContain('This repo is not cloned yet')
  expect(block(2)).toContain('No wiki engine is installed')
})

test('before the wikis are read Generate is closed without a complaint; once reading failed it says so', () => {
  const unread = wikiBlocks({ repos: ['api'], docs: [] }, null)[0]
  const loading = renderToStaticMarkup(<WikiBlock srv={srv} jobs={null} block={unread} loading onView={() => {}} onDone={() => {}} />)
  expect(generate(loading)).toContain('disabled')
  expect(loading).not.toContain('No he podido leer')
  const failed = renderToStaticMarkup(<WikiBlock srv={srv} jobs={null} block={unread} onView={() => {}} onDone={() => {}} />)
  expect(generate(failed)).toContain('disabled')
  expect(failed).toContain('No he podido leer el estado de las wikis')
})

// While another repo's wiki runs, Generate is closed on this one and says why; a reason of its own goes first.
test("Generate is closed while another repo's wiki runs, and says whose", () => {
  const busy = block(0, { busyWith: 'web' })
  expect(generate(busy)).toContain('disabled')
  expect(busy).toContain('Se está generando la wiki de web: espera a que termine para generar otra.')
  expect(block(1, { busyWith: 'api' })).toContain('Este repo aún no está clonado')
  setLang('en')
  expect(block(0, { busyWith: 'web' })).toContain("The wiki of web is being generated: wait for it to finish to generate another.")
})

test('Docs reads the running wiki from the jobs store and closes Generate on the other repos', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  const jobs = { get: () => ({ running: [{ id: '1', kind: 'wiki', repo: 'api', status: 'running' }], recent: [], error: '' }),
    subscribe: () => () => {}, refresh: () => {} }
  const out = renderToStaticMarkup(<Docs srv={srv} jobs={jobs} app={{ openExternal: () => {} }} index={index} />)
  expect(out.match(/Se está generando la wiki de api/g)).toHaveLength(2)            // web and ui, not api itself
})

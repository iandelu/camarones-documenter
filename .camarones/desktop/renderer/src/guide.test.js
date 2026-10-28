import { expect, test } from 'vitest'
import { chapters, guideAt, guideEntries, guideHref, inline, linkTarget, parse, searchGuides, slug } from './guide.js'

const SAMPLE = [
  '# The app',
  '',
  '> **TL;DR:** one window per project.',
  '',
  '## The window',
  '',
  'Each project opens in its window.',
  'It has a rail.',
  '',
  '- one',
  '- two',
  '  - two and a half',
  '1. first',
  '2. second',
  '',
  '<!-- go:plan -->',
  '<!-- cmd:check -->',
  '<!-- a note for maintainers -->',
  '',
  '### Keys',
  '',
  '| Key | Does |',
  '|---|---|',
  '| `g p` | Plan |',
  '',
  '> [!TIP]',
  '> Press **Ctrl K**.',
  '',
  '```text',
  'camaron app',
  '```',
].join('\n')

test('parse turns the guide subset into blocks, H1 dropped, markers grouped, other comments dropped', () => {
  expect(parse(SAMPLE)).toEqual([
    { t: 'quote', kind: null, blocks: [{ t: 'p', text: '**TL;DR:** one window per project.' }] },
    { t: 'h', level: 2, text: 'The window', id: 'the-window' },
    { t: 'p', text: 'Each project opens in its window. It has a rail.' },
    { t: 'ul', items: [{ text: 'one' }, { text: 'two', items: [{ text: 'two and a half' }] }] },
    { t: 'ol', items: [{ text: 'first' }, { text: 'second' }] },
    { t: 'actions', items: [{ kind: 'go', target: 'plan' }, { kind: 'cmd', target: 'check' }] },
    { t: 'h', level: 3, text: 'Keys', id: 'keys' },
    { t: 'table', head: ['Key', 'Does'], rows: [['`g p`', 'Plan']] },
    { t: 'quote', kind: 'tip', blocks: [{ t: 'p', text: 'Press **Ctrl K**.' }] },
    { t: 'code', lang: 'text', text: 'camaron app' },
  ])
})

test('a pipe inside code does not split a table cell', () => {
  const [table] = parse('| a | b |\n|---|---|\n| `x | y` | z |')
  expect(table.rows).toEqual([['`x | y`', 'z']])
})

test('heading ids follow the portal: markup out, accents kept, a repeated one numbered', () => {
  const ids = parse('## Plan\n\n## Plan\n\n## The `camaron up` command\n\n## Datos y librerías\n\n## cam-docs/ and ~/.camarones')
    .map((b) => b.id)
  expect(ids).toEqual(['plan', 'plan-1', 'the-camaron-up-command', 'datos-y-librerías', 'cam-docs-and-camarones'])
  expect(slug('Health, libraries and vulnerabilities')).toBe('health-libraries-and-vulnerabilities')
})

test('inline tokens: code, bold, italic, links and kbd; any other HTML stays text', () => {
  expect(inline('Run `camaron up`, **then** *read* [the plan](app.md#plan) <kbd>Ctrl</kbd> <b>no</b>')).toEqual([
    { t: 'text', text: 'Run ' }, { t: 'code', text: 'camaron up' }, { t: 'text', text: ', ' }, { t: 'b', text: 'then' },
    { t: 'text', text: ' ' }, { t: 'i', text: 'read' }, { t: 'text', text: ' ' },
    { t: 'a', text: 'the plan', href: 'app.md#plan' }, { t: 'text', text: ' ' }, { t: 'kbd', text: 'Ctrl' },
    { t: 'text', text: ' <b>no</b>' },
  ])
})

test('chapters are the H2 with their H3', () => {
  expect(chapters(parse(SAMPLE))).toEqual([{ id: 'the-window', text: 'The window', sections: [{ id: 'keys', text: 'Keys' }] }])
})

test('linkTarget tells a guide, an anchor, the web and the rest apart', () => {
  const names = ['app', 'portal']
  expect(linkTarget('app.md#plan', names)).toEqual({ kind: 'guide', name: 'app', anchor: 'plan' })
  expect(linkTarget('./portal.md', names)).toEqual({ kind: 'guide', name: 'portal', anchor: '' })
  expect(linkTarget('#keys', names)).toEqual({ kind: 'anchor', anchor: 'keys' })
  expect(linkTarget('https://github.com/x', names)).toEqual({ kind: 'external', href: 'https://github.com/x' })
  expect(linkTarget('mailto:a@b.c', names)).toBeNull()
  expect(linkTarget('other.md', names)).toBeNull()
})

test('guide addresses round-trip, accents included', () => {
  expect(guideHref('app')).toBe('#/guide/app')
  expect(guideAt(guideHref('app', 'datos-y-librerías'))).toEqual({ name: 'app', anchor: 'datos-y-librerías' })
  expect(guideAt('#/guide')).toEqual({ name: '', anchor: '' })
})

const GUIDES = [{ name: 'app', title: 'The app', blocks: parse(SAMPLE) },
  { name: 'portal', title: 'The portal', blocks: parse('## Tokens\n\nThe portal token lets the browser write the board.') }]

test('search: every word, accents and case aside, with where it was found', () => {
  expect(searchGuides(GUIDES, 'TOKÉN board')).toEqual([{ name: 'portal', guideTitle: 'The portal', chapter: 'Tokens',
    id: 'tokens', title: 'Tokens', snippet: 'The portal token lets the browser write the board.' }])
  expect(searchGuides(GUIDES, 'ctrl k')[0]).toMatchObject({ name: 'app', id: 'keys', chapter: 'The window' })
})

test('search never throws on regex characters and ignores one-letter queries', () => {
  expect(searchGuides(GUIDES, 'c++ (')).toEqual([])
  expect(searchGuides(GUIDES, '*')).toEqual([])
  expect(searchGuides(GUIDES, 'a')).toEqual([])
})

test('search returns at most 20 places', () => {
  const md = Array.from({ length: 30 }, (_, i) => `## Step ${i}\n\nshrimp here`).join('\n\n')
  expect(searchGuides([{ name: 'x', title: 'X', blocks: parse(md) }], 'shrimp')).toHaveLength(20)
})

test('every chapter of every guide is a palette entry that opens it', () => {
  expect(guideEntries(GUIDES)).toEqual([
    { id: 'guide:app/the-window', label: 'The window', sub: 'The app', href: '#/guide/app/the-window' },
    { id: 'guide:portal/tokens', label: 'Tokens', sub: 'The portal', href: '#/guide/portal/tokens' },
  ])
})

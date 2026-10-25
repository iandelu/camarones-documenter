import { expect, test } from 'vitest'
import { buildTree, docsTrees, flatten, forBusiness, sortedDirs } from './tree.js'

const doc = (path, title, extra = {}) => ({ path, title, space: 'docs', ...extra })
const rows = [
  doc('index.md', 'Home'),
  doc('readme.md', 'Read me'),
  doc('domain/index.md', 'Domain'),
  doc('domain/visits.md', 'Visits', { type: 'domain' }),
  doc('domain/pets.md', 'Pets'),
  doc('architecture/c4.md', 'C4'),
  doc('guides/deep/x.md', 'Deep'),
  doc('interview/notes.md', 'Notes', { space: 'notes' }),
  doc('repos/api/wiki/intro.md', 'Intro', { space: 'wiki' }),
]
const sections = ['overview', 'architecture', 'domain', 'guides']

test('the tree: folders, their index page apart, the home page left out', () => {
  const root = buildTree(rows.filter((d) => d.space === 'docs'))
  expect(root.pages.map((d) => d.path)).toEqual(['readme.md'])
  expect(root.dirs.domain.index.path).toBe('domain/index.md')
  expect(root.dirs.domain.pages.map((d) => d.path)).toEqual(['domain/visits.md', 'domain/pets.md'])
  expect(root.dirs.guides.dirs.deep.pages[0].path).toBe('guides/deep/x.md')
})

test('top-level folders follow the canonical section order, deeper ones the alphabet', () => {
  const root = buildTree(rows.filter((d) => d.space === 'docs'))
  expect(sortedDirs(root, sections).map((n) => n.name)).toEqual(['architecture', 'domain', 'guides'])
})

test('reading order: a folder index first, its pages by title, then its folders', () => {
  const root = buildTree(rows.filter((d) => d.space === 'docs'))
  expect(flatten(root.dirs.domain, sections, 'en')).toEqual(['domain/index.md', 'domain/pets.md', 'domain/visits.md'])
})

test('docsTrees: the docs and notes trees with their reading orders; the home page leads the docs', () => {
  const t = docsTrees(rows, { sections, lang: 'en' })
  expect(t.order).toEqual(['index.md', 'readme.md', 'architecture/c4.md', 'domain/index.md', 'domain/pets.md', 'domain/visits.md', 'guides/deep/x.md'])
  expect(t.notesOrder).toEqual(['interview/notes.md'])
  expect(t.notes.path).toBe('')                     // a notes tree that is only interview/ opens on its pages
})

test('the Business view keeps what the system does and why, and the page being read', () => {
  expect(forBusiness(doc('domain/x.md', 'x'))).toBe(true)
  expect(forBusiness(doc('guides/x.md', 'x', { type: 'decision' }))).toBe(true)
  expect(forBusiness(doc('architecture/c4.md', 'x'))).toBe(false)
  const t = docsTrees(rows, { sections, lang: 'en', business: true, active: 'architecture/c4.md' })
  expect(t.order).toEqual(['index.md', 'architecture/c4.md', 'domain/index.md', 'domain/pets.md', 'domain/visits.md'])
})

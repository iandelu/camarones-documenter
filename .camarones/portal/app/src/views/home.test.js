import { expect, test } from 'vitest'
import { askHref, emptyProject, kpiHref, withoutH1 } from './home.js'

const page = (path, extra = {}) => ({ path, space: 'docs', ...extra })

test('a project with only the kit guides and interview notes is empty', () => {
  const index = { kitGuides: ['guides/tutorial.md'], views: [],
    docs: [page('guides/tutorial.md'), page('interview/notes.md', { type: 'interview' }), page('w.md', { space: 'wiki' })] }
  expect(emptyProject(index)).toBe(true)
  expect(emptyProject({ ...index, docs: [...index.docs, page('domain/visits.md')] })).toBe(false)
  expect(emptyProject({ ...index, views: [{ id: 'index' }] })).toBe(false)          // a C4 model counts
})

test('the home question asks on the server and searches in the export', () => {
  expect(askHref('how is a visit paid?', 'live')).toBe('#/ask/how%20is%20a%20visit%20paid%3F')
  expect(askHref('visits', 'static')).toBe('#/search/visits')
  expect(askHref('   ', 'live')).toBe('')
})

test('each state figure leads where it can be acted on', () => {
  expect(kpiHref('confirmed')).toBe('#/docs')
  for (const k of ['reconfirm', 'drafts', 'feedback']) expect(kpiHref(k)).toBe('#/review')
})

// The project home (docs/index.md) sits in the Home as "The system": without its H1 (the section has its heading),
// with its frontmatter and its TL;DR as they are.
test('the project home loses its H1 and keeps the rest', () => {
  const raw = '---\nx-owner: agent\n---\n# Bench clinic\n\n> **TL;DR** A clinic for pets.\n\n## Repos\n'
  expect(withoutH1(raw)).toBe('---\nx-owner: agent\n---\n\n> **TL;DR** A clinic for pets.\n\n## Repos\n')
  expect(withoutH1('# Only\nbody')).toBe('body')
  expect(withoutH1('no heading\n## Sub')).toBe('no heading\n## Sub')
})

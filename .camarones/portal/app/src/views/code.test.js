import { expect, test } from 'vitest'
import { codeCrumbs, codeRoute, codeView, fileIdByPath, graphModel, inSub, mixHex, searchFiles, singleFolder } from './code.js'

// A small map as lib/codemap.py writes it: groups (modules), files with their sub-folder, degrees and links.
const m = {
  stats: { files: 4, groups: 2 }, core: [0],
  groups: [{ id: 0, label: 'owner', files: 3 }, { id: 1, label: 'vet', files: 1 }],
  links: [{ s: 0, t: 1, w: 2 }],
  files: [
    { label: 'OwnerController', path: 'owner/web/OwnerController.java', group: 0, sub: 'web', deg: [2, 1], out: [[1, 1], [3, 2]], in: [[2, 1]] },
    { label: 'Owner', path: 'owner/model/Owner.java', group: 0, sub: 'model', deg: [0, 2], out: [], in: [[0, 1]] },
    { label: 'OwnerRepository', path: 'owner/model/OwnerRepository.java', group: 0, sub: 'model', deg: [1, 0], out: [[0, 1]], in: [] },
    { label: 'Vet', path: 'vet/Vet.java', group: 1, sub: '', deg: [0, 1], out: [], in: [[0, 2]] },
  ],
}
const index = { codeMaps: ['api'], codeGraphs: ['all', 'api', 'web'] }

test('the address: repo, kind of view, id and sub-folder; graphify’s page for a repo without a map', () => {
  expect(codeRoute('', index)).toEqual({ repo: 'api', mode: '', id: NaN, sub: '', graph: false })
  expect(codeRoute('api/g/0/model/x', index)).toMatchObject({ repo: 'api', mode: 'g', id: 0, sub: 'model/x', graph: false })
  expect(codeRoute('api/graph', index).graph).toBe(true)
  expect(codeRoute('web', index)).toMatchObject({ repo: 'web', graph: true })
  expect(codeRoute('', { codeMaps: [], codeGraphs: ['all'] })).toMatchObject({ repo: 'all', graph: true })
  expect(codeRoute('', { codeMaps: [], codeGraphs: [] }).repo).toBe('')
})

test('which view: a file, a module, or the map when the id does not exist', () => {
  expect(codeView(m, 'f', 1)).toBe('file')
  expect(codeView(m, 'g', 1)).toBe('group')
  expect(codeView(m, 'g', 9)).toBe('map')
  expect(codeView(m, '', NaN)).toBe('map')
})

test('a module’s files in a sub-folder, the busiest first; a level with one folder opens it', () => {
  expect(inSub(m, 0, '').map(([i]) => i)).toEqual([0, 1, 2])
  expect(inSub(m, 0, 'model').map(([i]) => i)).toEqual([1, 2])
  expect(singleFolder(m, 0, '', 'api')).toBeNull()                       // web and model: two folders
  expect(singleFolder(m, 0, 'model', 'api')).toBeNull()                  // files of its own
  expect(singleFolder({ ...m, files: m.files.slice(1, 3) }, 0, '', 'api')).toBe('#/code/api/g/0/model')
})

test('find a file by name or path, names that start with it first', () => {
  expect(searchFiles(m, 'owner').map(([i]) => i)).toEqual([0, 1, 2])                  // all start with it: busiest first
  expect(searchFiles(m, 'model').map(([i]) => i)).toEqual([1, 2])                     // by path
  expect(searchFiles(m, 'vet.java').map(([i]) => i)).toEqual([3])
  expect(searchFiles(m, 'o')).toEqual([])
})

test('the in-page path: repo, module, each folder', () => {
  expect(codeCrumbs('api', m, 'map', 0, '')).toEqual([{ label: 'api', href: '#/code/api' }])
  expect(codeCrumbs('api', m, 'file', 2, '')).toEqual([{ label: 'api', href: '#/code/api' },
    { label: 'owner', href: '#/code/api/g/0' }, { label: 'model', href: '#/code/api/g/0/model' }])
})

test('colours are mixed from the theme, never written by hand', () => {
  expect(mixHex('#ff0000', '#ffffff', 0.5)).toBe('#ff8080')
  expect(mixHex('#000000', '#ffffff', 1)).toBe('#000000')
})

const look = { colorOf: (g, soft) => (soft ? `s${g}` : `c${g}`), t: (k, v) => `${k}:${v?.n ?? ''}`, ink: 'i', muted: 'm', line: 'l', raise: 'r', accent: 'a' }

test('the module map: one box per module, links weighted, top-down', () => {
  const g = graphModel(m, 'map', 0, '', look)
  expect(g.nodes.map((n) => n.id)).toEqual(['g0', 'g1'])
  expect(g.edges).toMatchObject([{ from: 'g0', to: 'g1', value: 2 }])
  expect(g).toMatchObject({ layered: true, direction: 'UD' })
})

test('a file between what uses it and what it uses', () => {
  const g = graphModel(m, 'file', 0, '', look)
  expect(g.nodes.map((n) => n.id).sort()).toEqual(['f0', 'f1', 'f2', 'f3'])
  expect(g.edges.map((e) => `${e.from}>${e.to}`).sort()).toEqual(['f0>f1', 'f0>f3', 'f2>f0'])
  expect(g.direction).toBe('LR')
})

test('a module: its files as a cloud, links out of it to the other modules dashed', () => {
  const g = graphModel(m, 'group', 0, '', look)
  expect(g.layered).toBe(false)
  expect(g.nodes.map((n) => n.id)).toEqual(['f0', 'f1', 'f2', 'g1'])
  expect(g.edges.find((e) => e.to === 'g1')).toMatchObject({ from: 'f0', dashes: true })
  expect(JSON.stringify(g.nodes)).not.toMatch(/\p{Extended_Pictographic}/u)
})

test('a file address by path (#/code/<repo>/f/<path>) finds the file in the map', () => {
  expect(fileIdByPath(m, 'owner/model/Owner.java')).toBe(1)
  expect(fileIdByPath(m, 'src/main/java/vet/Vet.java')).toBe(3)             // the map's paths start below the source root
  expect(fileIdByPath(m, 'src/Other.java')).toBeNaN()
  expect(fileIdByPath(m, '')).toBeNaN()
})

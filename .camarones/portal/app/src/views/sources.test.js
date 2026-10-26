import { expect, test } from 'vitest'
import { IDES, groupSources, lineLabel, openTarget, pageFresh, splitPath } from './sources.js'

const code = (over = {}) => ({ ref: 'api:src/a/Api.java#L3-L5', kind: 'code', repo: 'api', path: 'src/a/Api.java',
  lines: [3, 5], line: 3, state: 'fresh', url: 'https://github.com/x/api/blob/main/src/a/Api.java#L3-L5', ...over })

test('each editor opens the file at its line, on Windows and on Unix paths', () => {
  const href = (id, file) => IDES.find((i) => i.id === id).href(file, 12)
  expect(href('vscode', 'C:/Users/ana/api/Api.java')).toBe('vscode://file/C:/Users/ana/api/Api.java:12:1')
  expect(href('vscode', '/home/ana/api/Api.java')).toBe('vscode://file/home/ana/api/Api.java:12:1')
  expect(href('cursor', '/home/ana/my api/A.java')).toBe('cursor://file/home/ana/my%20api/A.java:12:1')
  expect(href('idea', 'C:/Users/ana/A.java')).toBe('idea://open?file=C%3A%2FUsers%2Fana%2FA.java&line=12')
})

test('a source opens in the reader\'s editor when this machine has the file, else on the forge', () => {
  const local = code({ file: 'C:/w/api/src/a/Api.java' })
  expect(openTarget(local, 'vscode')).toEqual({ href: 'vscode://file/C:/w/api/src/a/Api.java:3:1', external: false, where: 'ide' })
  expect(openTarget(local, 'repo')).toEqual({ href: local.url, external: true, where: 'repo' })
  expect(openTarget(code(), 'vscode')).toEqual({ href: code().url, external: true, where: 'repo' })     // the deployed portal
  expect(openTarget(code({ url: '' }), 'repo')).toBe(null)
  expect(openTarget(code({ url: '', file: '/w/a.java' }), 'repo').where).toBe('ide')                  // no forge: the editor
  expect(openTarget({ kind: 'c4', ref: 'c4:x', name: 'x' }, 'vscode')).toBe(null)
})

test('a path shows its file name first and its folder dimmed; the lines or the symbol beside it', () => {
  expect(splitPath('src/lib/types.ts')).toEqual({ dir: 'src/lib', name: 'types.ts' })
  expect(splitPath('README.md')).toEqual({ dir: '', name: 'README.md' })
  expect(lineLabel(code())).toBe('L3–5')
  expect(lineLabel(code({ lines: [7, 7] }))).toBe('L7')
  expect(lineLabel(code({ lines: null }))).toBe('')
  expect(lineLabel(code({ kind: 'symbol', symbol: 'Api.call', lines: [5, 6] }))).toBe('#call')
})

test('sources are grouped by repo in the order they are cited; pages and C4 elements go last', () => {
  const s = [code({ ref: '1', repo: 'web' }), { ref: '2', kind: 'doc', page: 'a.md' }, code({ ref: '3', repo: 'api' }),
    code({ ref: '4', repo: 'web' }), { ref: '5', kind: 'c4', name: 'x' }]
  expect(groupSources(s).map((g) => [g.key, g.items.map((i) => i.ref)])).toEqual(
    [['web', ['1', '4']], ['api', ['3']], ['docs', ['2']], ['c4', ['5']]])
})

test('the page\'s freshness comes as a tone and an icon for each state', () => {
  expect(pageFresh('fresh')).toBe('fresh')
  expect(pageFresh('suspect')).toBe('changed')
  expect(pageFresh('stale')).toBe('missing')
  expect(pageFresh('unverified')).toBe('unchecked')
  expect(pageFresh(undefined)).toBe('unchecked')
})

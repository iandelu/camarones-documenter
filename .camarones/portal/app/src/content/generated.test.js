import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { mark, parseOpen } from './generated.js'

const T = { 'gen.fromCode': 'From the code', 'gen.confirmed': 'Confirmed by {by}', 'gen.stale': 'The code changed', 'gen.edited': 'Edited by hand' }
const t = (k, vars = {}) => (T[k] ?? k).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? '')
const BODY = '```mermaid\nstateDiagram-v2\n  [*] --> PENDING\n```'
const block = (attrs = '') => `<!-- generated:states repo=api id=OrderStatus${attrs} sha=abc123 -->\n${BODY}\n<!-- /generated:states -->`

describe('generated blocks', () => {
  it('marks a block from the code', () => {
    const out = mark(`# T\n\n${block()}\n\nafter`, [{ kind: 'states', repo: 'api', id: 'OrderStatus', state: 'current' }], t)
    expect(out).toContain('<div class="gen-block" data-state="from-code"><p class="gen-badge">From the code</p>')
    expect(out).toContain(`\n\n${BODY}\n\n</div>`)
    expect(out).not.toContain('<!--')
    expect(out).toContain('# T')
    expect(out).toContain('after')
  })

  it('badge comes from the marker when no state is given', () => {
    const out = mark(block(' confirmed=def456 by=ana'), [], t)
    expect(out).toContain('data-state="confirmed"')
    expect(out).toContain('Confirmed by ana')
    expect(mark(block(), [], t)).toContain('data-state="from-code"')
  })

  it('a confirmed-stale state wins over the marker', () => {
    const out = mark(block(' confirmed=def456 by=ana'), [{ kind: 'states', repo: 'api', id: 'OrderStatus', state: 'confirmed-stale' }], t)
    expect(out).toContain('data-state="stale"')
    expect(out).toContain('The code changed')
    expect(out).not.toContain('Confirmed by')
  })

  it('a stale code block says the code changed', () => {
    const out = mark(block(), [{ kind: 'states', repo: 'api', id: 'OrderStatus', state: 'stale' }], t)
    expect(out).toContain('data-state="stale"')
  })

  it('text without markers is unchanged', () => {
    const md = '# Title\n\nSome text\n\n```js\nx\n```\n'
    expect(mark(md, [], t)).toBe(md)
  })

  it('a marker inside a code fence is left alone', () => {
    const md = `\`\`\`md\n${block()}\n\`\`\``
    expect(mark(md, [], t)).toBe(md)
  })

  it('escapes the confirming name', () => {
    expect(mark(block(' confirmed=d by=<b'), [], t)).toContain('Confirmed by &lt;b')
  })

  it('a hand-edited block says so, never "from the code"', () => {
    const out = mark(block(), [{ kind: 'states', repo: 'api', id: 'OrderStatus', state: 'edited' }], t)
    expect(out).toContain('data-state="edited"')
    expect(out).toContain('Edited by hand')
    expect(out).not.toContain('From the code')
  })

  it('the edited label exists in English and Spanish', () => {
    const core = readFileSync(new URL('../../public/legacy/core.js', import.meta.url), 'utf-8')
    expect(core).toContain("'gen.edited': 'Edited by hand'")
    expect(core).toContain("'gen.edited': 'Editado a mano'")
  })

  it('a diagram whose source is gone says the code changed', () => {
    const out = mark(block(' confirmed=def456 by=ana'), [{ kind: 'states', repo: 'api', id: 'OrderStatus', state: 'gone' }], t)
    expect(out).toContain('data-state="stale"')
    expect(out).toContain('The code changed')
  })
})

// The same marker forms lib/genblocks.py reads (tests/test_genblocks.py): any order, a quoted or unquoted spaced name.
describe('parseOpen', () => {
  it('reads the attributes in any order', () => {
    expect(parseOpen('<!-- generated:states sha=abc by=ana confirmed=def id=OrderStatus repo=api -->'))
      .toEqual({ kind: 'states', repo: 'api', id: 'OrderStatus', confirmed: 'def', by: 'ana', sha: 'abc' })
  })

  it('reads a name with spaces, quoted or not', () => {
    for (const by of ['"Ana López"', 'Ana López']) {
      const got = parseOpen(`<!-- generated:states repo=api confirmed=3fa1c2d4e5f6 by=${by} sha=abc -->`)
      expect(got.by).toBe('Ana López')
      expect(got.sha).toBe('abc')
    }
  })

  it('accepts a pasted placeholder as a value', () => {
    expect(parseOpen('<!-- generated:states repo=api id=X confirmed=3fa1c2… by=ana sha=abc -->').confirmed).toBe('3fa1c2…')
  })

  it('refuses a marker it cannot read', () => {
    expect(parseOpen('<!-- generated:states sha=abc -->')).toBeNull()
    expect(parseOpen('<!-- generated:states repo=a/b -->')).toBeNull()
    expect(parseOpen('<!-- generated:states repo=api repo=web -->')).toBeNull()
    expect(parseOpen('<!-- generated:<kind> repo=<repo> -->')).toBeNull()
    expect(parseOpen(' <!-- generated:states repo=api -->')).toBeNull()
  })

  it('a block written in another order still gets its badge', () => {
    const md = `<!-- generated:states sha=abc confirmed=def by="Ana López" id=OrderStatus repo=api -->\n${BODY}\n<!-- /generated:states -->`
    expect(mark(md, [], t)).toContain('Confirmed by Ana López')
  })
})

import { describe, expect, it } from 'vitest'
import { mark } from './generated.js'

const T = { 'gen.fromCode': 'From the code', 'gen.confirmed': 'Confirmed by {by}', 'gen.stale': 'The code changed' }
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
})

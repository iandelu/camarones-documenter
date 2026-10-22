import { describe, expect, it } from 'vitest'
import { cards, render, rule, split, tabs } from './directives.js'

const md = (s) => `<md>${s.trim()}</md>`

describe('directives', () => {
  it('splits a page into Markdown and directive parts', () => {
    const parts = split('# T\n\n:::details More\nhidden\n:::\n\nend')
    expect(parts.map((p) => p.type)).toEqual(['md', 'directive', 'md'])
    expect(parts[1]).toMatchObject({ kind: 'details', arg: 'More', body: 'hidden' })
  })

  it('leaves directives inside code fences and unknown kinds alone', () => {
    expect(split('```\n:::tabs\n:::\n```').map((p) => p.type)).toEqual(['md'])
    expect(split(':::warning\nx\n:::').map((p) => p.type)).toEqual(['md'])
    expect(split(':::tabs\nno end').map((p) => p.type)).toEqual(['md'])
  })

  it('renders tabs with the first one open', () => {
    const html = render(':::tabs\n::tab Java\nmvn test\n::tab Kotlin\ngradle test\n:::', md)
    expect(tabs('::tab A\na\n::tab B\nb')).toEqual([{ label: 'A', body: 'a' }, { label: 'B', body: 'b' }])
    expect(html).toContain('data-tab="0">Java</button>')
    expect(html).toContain('<div class="dv-tab" role="tabpanel" data-tab="1" hidden><md>gradle test</md></div>')
  })

  it('renders cards, steps, details and audience blocks', () => {
    expect(cards('- [Orders](flows/orders.md): how orders flow\n- not a card')).toEqual(
      [{ title: 'Orders', href: 'flows/orders.md', text: 'how orders flow' }])
    const html = render(':::steps\n1. a\n:::\n:::details Why\nb\n:::\n:::tech\nc\n:::\n:::business\nd\n:::', md)
    expect(html).toContain('<div class="dv-steps"><md>1. a</md></div>')
    expect(html).toContain('<details class="dv-details"><summary>Why</summary><md>b</md></details>')
    expect(html).toContain('<div class="dv-tech" data-audience="tech"><md>c</md></div>')
    expect(html).toContain('data-audience="business"')
  })

  it('escapes labels', () => {
    expect(render(':::details <b>x</b>\ny\n:::', md)).toContain('&lt;b&gt;x&lt;/b&gt;')
  })

  it('renders a business rule with its anchors', () => {
    const body = 'enforced: api:src/A.java#A.place\ntest: api:src/ATest.java#ATest.empty\nAn order needs a line.'
    expect(rule(body)).toEqual({ enforced: ['api:src/A.java#A.place'], test: ['api:src/ATest.java#ATest.empty'],
      text: 'An order needs a line.' })
    const html = render(`:::rule ORD-1 Non-empty orders\n${body}\n:::`, md)
    expect(html).toContain('<div class="dv-rule" id="rule-ORD-1">')
    expect(html).toContain('<b>ORD-1</b>')
    expect(html).toContain('Non-empty orders')
    expect(html).toContain('<md>An order needs a line.</md>')
    expect(html).toContain('<code>api:src/A.java#A.place</code>')
  })
})

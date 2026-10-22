// Live tables (R29): any Markdown table can be sorted by a column, and long ones filtered. Pure helpers plus a small
// enhancer the page renderer calls on each <table>.
const num = (s) => {
  const t = String(s).replace(/[,\s%$€]/g, '')
  return t !== '' && !Number.isNaN(Number(t)) ? Number(t) : null
}

export function sortRows(rows, col, dir = 1) {
  const keyed = rows.map((r, i) => [r, i])
  const allNum = rows.every((r) => num(r[col]) !== null || String(r[col]).trim() === '')
  keyed.sort(([a, i], [b, j]) => {
    const x = allNum ? num(a[col]) ?? -Infinity : String(a[col]).toLowerCase()
    const y = allNum ? num(b[col]) ?? -Infinity : String(b[col]).toLowerCase()
    return (x < y ? -1 : x > y ? 1 : i - j) * dir
  })
  return keyed.map(([r]) => r)
}

export function filterRows(rows, q) {
  const words = q.toLowerCase().split(/\s+/).filter(Boolean)
  return words.length ? rows.filter((r) => words.every((w) => r.join(' ').toLowerCase().includes(w))) : rows
}

export const FILTER_FROM = 8      // rows: a filter box from this many on

export function enhance(table, labels = { filter: 'Filter…', sort: 'Sort' }) {
  const body = table.tBodies[0]
  const head = table.tHead?.rows[0]
  if (!body || !head || body.rows.length < 2) return
  const original = [...body.rows]
  const text = (tr) => [...tr.cells].map((c) => c.textContent.trim())
  let state = { col: -1, dir: 1, q: '' }
  const draw = () => {
    let rows = original.map((tr) => [tr, text(tr)])
    if (state.q) rows = rows.filter(([, t]) => filterRows([t], state.q).length)
    if (state.col >= 0) {
      const sorted = sortRows(rows.map(([, t]) => t), state.col, state.dir)
      rows = sorted.map((t) => rows.find(([, x]) => x === t))
    }
    body.replaceChildren(...rows.map(([tr]) => tr))
    ;[...head.cells].forEach((th, i) => { th.dataset.sort = i === state.col ? (state.dir > 0 ? 'asc' : 'desc') : '' })
  }
  ;[...head.cells].forEach((th, i) => {
    th.classList.add('sortable')
    th.title = labels.sort
    th.addEventListener('click', () => { state = { ...state, col: i, dir: state.col === i ? -state.dir : 1 }; draw() })
  })
  if (original.length >= FILTER_FROM) {
    const input = document.createElement('input')
    input.type = 'search'
    input.className = 'table-filter'
    input.placeholder = labels.filter
    input.addEventListener('input', () => { state = { ...state, q: input.value }; draw() })
    table.parentElement.before(input)
  }
}

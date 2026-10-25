// The catalog's forms (the desktop app's "All commands"), generated from the catalog (lib/catalog.py reads them from the CLI's own parser): one field per
// argument, and the values turned back into the args object the server checks again (lib/appapi.py). `--yes` and
// `--json` are never fields: the app asks before a command with `--yes`, and `--json` is for the views that read it.
const HIDDEN = new Set(['--yes', '--json'])

const widget = (a) => (a.kind === 'bool' ? 'check' : a.choices ? 'select' : a.many ? 'list'
  : a.kind === 'int' || a.kind === 'float' ? 'number' : 'text')

export function fields(entry) {
  const out = []
  for (const a of entry.args) {
    if (HIDDEN.has(a.flag)) continue
    if (a.kind === 'const') {
      const group = out.find((f) => f.dest === a.dest && f.widget === 'select' && f.consts)
      if (group) { group.options.push(a.const); group.label += ` | ${a.flag}`; continue }
      out.push({ dest: a.dest, widget: 'select', consts: true, options: ['', a.const], label: a.flag, required: false, initial: '' })
      continue
    }
    out.push({
      dest: a.dest, widget: widget(a), options: a.choices || null, label: a.positional ? a.dest : a.flag,
      required: a.required, many: a.many,
      initial: a.kind === 'bool' ? !!a.default : a.default == null ? '' : Array.isArray(a.default) ? a.default.join(' ') : String(a.default),
    })
  }
  return out
}

export function toArgs(entry, values) {
  const args = {}
  for (const f of fields(entry)) {
    const v = values[f.dest]
    if (f.widget === 'check') { if (v !== undefined) args[f.dest] = !!v; continue }
    if (v === undefined || v === null || String(v).trim() === '') continue
    if (f.widget === 'list' || (f.many && f.widget === 'text')) args[f.dest] = String(v).split(/[\s,]+/).filter(Boolean)
    else if (f.widget === 'number') args[f.dest] = Number(v)
    else if (f.many) args[f.dest] = [String(v)]
    else args[f.dest] = String(v)
  }
  return args
}

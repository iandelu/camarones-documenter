// Board names as lib/boards.py accepts them: lowercase letters, digits and dashes.
export const slug = (text) => String(text || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 58)

export function draftName(view, taken) {
  const base = `${slug(view.title) || slug(view.id)}-draft`
  const used = new Set(taken)
  if (!used.has(base)) return base
  let n = 2
  while (used.has(`${base}-${n}`)) n += 1
  return `${base}-${n}`
}

// The name field after a view is picked: a name the user typed stays; the one we filled follows the view.
export function nameAfterPick(name, autoName, view, taken) {
  if (name && name !== autoName) return name
  return view ? draftName(view, taken) : ''
}

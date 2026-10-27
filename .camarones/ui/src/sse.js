// Server-sent events read in pieces (lib/serve.py streams runs and jobs): complete messages out, the rest kept for
// the next piece, and the last id seen so a dropped stream can resume. Comments (keep-alives) are skipped.
export function parseSSE(buf) {
  const events = []
  let id = null
  let i
  while ((i = buf.indexOf('\n\n')) >= 0) {
    const lines = buf.slice(0, i).split('\n')
    buf = buf.slice(i + 2)
    for (const l of lines) if (l.startsWith('id: ')) id = l.slice(4)
    const data = lines.filter((l) => l.startsWith('data: ')).map((l) => l.slice(6)).join('\n')
    if (data) events.push(JSON.parse(data))
  }
  return { events, rest: buf, id }
}

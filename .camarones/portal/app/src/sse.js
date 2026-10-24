// Server-sent events read in pieces (lib/serve.py streams runs and jobs): complete messages out, the rest kept for the
// next piece. Comments (keep-alives) and ids are skipped.
export function parseSSE(buf) {
  const events = []
  let i
  while ((i = buf.indexOf('\n\n')) >= 0) {
    const data = buf.slice(0, i).split('\n').filter((l) => l.startsWith('data: ')).map((l) => l.slice(6)).join('\n')
    buf = buf.slice(i + 2)
    if (data) events.push(JSON.parse(data))
  }
  return { events, rest: buf }
}

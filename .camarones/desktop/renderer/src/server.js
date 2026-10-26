// The project's server, one folder up from /desktop/. Every call carries the app's token (lib/serve.py checks it);
// a write also carries X-Camarones, which a page on another site cannot send. A read's `query` goes in the address
// ({ lang } for the units' titles in the app's language). A refusal throws an Error with the server's message, its
// `status` and the response `data`.
export function server(token, fetcher = (...a) => fetch(...a)) {
  const call = async (name, init = {}) => {
    const r = await fetcher(`../api/${name}`, { ...init, headers: { 'X-Camaron-Token': token, ...init.headers } })
    const data = await r.json().catch(() => ({}))
    if (!r.ok) throw Object.assign(new Error(data.error || `${name}: ${r.status}`), { status: r.status, data })   // data: why (the board's 409 lists who blocks)
    return data
  }
  return {
    get: (name, query) => call(query ? `${name}?${new URLSearchParams(query)}` : name),
    post: (name, body) => call(name, { method: 'POST', body: JSON.stringify(body || {}),
      headers: { 'Content-Type': 'application/json', 'X-Camarones': '1' } }),
  }
}

"""Stdio MCP server: agents search and read the project docs and query the code graph while they implement.
Newline-delimited JSON-RPC 2.0 (the MCP stdio transport), stdlib only, no API keys. Nothing but protocol goes to stdout."""
from __future__ import annotations

import json, re, sys

from .common import ROOT, DOCS, WS_FILE, VERSIONS, run, which
from . import docs, env

PROTOCOL = "2025-06-18"

TOOLS = [
    {"name": "search_docs", "description": "Full-text search over the project documentation (all repos, architecture, domain, "
                                           "flows, decisions). Returns matching pages with trust level and snippets.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"},
                                                      "limit": {"type": "integer", "default": 8}}, "required": ["query"]}},
    {"name": "read_doc", "description": "Read one documentation page by the path returned by search_docs/list_docs "
                                        "(e.g. architecture/overview.md).",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "list_docs", "description": "Index of every documentation page: path, title, type, trust "
                                         "(confirmed = human-verified source of truth, draft = AI-written).",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "doc_status", "description": "Documentation health: trust counts, pages needing re-confirmation, orphaned "
                                          "sources, repos whose code changed since the docs were last updated.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "repo_graph", "description": "Ask the code knowledge graph (graphify) a question about one repo, or all repos when "
                                          "repo is omitted. Cheaper and more precise than grepping.",
     "inputSchema": {"type": "object", "properties": {"question": {"type": "string"}, "repo": {"type": "string"}},
                     "required": ["question"]}},
]


def _rows() -> dict[str, dict]:
    return {r["path"]: r for r in docs.collect()}


def _file(path: str):
    return dict(docs.iter_docs()).get(path.removeprefix("docs/"))


def search_docs(query: str, limit: int = 8) -> str:
    if not re.search(r"\w\w", query):
        return "Empty query."
    hits = docs.search(query, limit)
    if not hits:
        return f"No page mentions: {query}"
    return "\n\n".join(f"## {h['path']} [{h['trust']}] — {h['title']}\n" + "\n".join(f"> {l}" for l in h["lines"])
                       for h in hits)


def read_doc(path: str) -> str:
    f = _file(path)
    if not f:
        return f"No page at {path}. Use list_docs or search_docs."
    r = _rows().get(path.removeprefix("docs/"), {})
    return f"<!-- trust: {r.get('trust', '?')} · file: {r.get('file', '')} -->\n" + f.read_text(encoding="utf-8")


def list_docs() -> str:
    return "\n".join(f"- {r['path']} [{r['trust']}] {r['title']}" + (f" — {r['description']}" if r["description"] else "")
                     for r in docs.collect()) or "No docs yet."


def doc_status() -> str:
    rows = docs.collect()
    s = docs.summary(rows)
    lines = [f"{s['total']} pages: confirmed {s['confirmed']}, draft {s['draft']}, needs-reconfirm {s['needs-reconfirm']}, "
             f"orphans {s['orphans']}, untranslated {s['untranslated']}"]
    lines += [f"- re-confirm: {r['path']}" for r in rows if r["trust"] == "needs-reconfirm"]
    lines += [f"- orphan sources in {r['path']}: {r['orphan_sources']}" for r in rows if r["orphan_sources"]]
    for repo, c in docs.changes().items():
        if c["status"] != "up-to-date":
            lines.append(f"- repo {repo}: {c['status']}" + (f" ({len(c.get('files', []))} files)" if c.get("files") else ""))
    return "\n".join(lines)


def repo_graph(question: str, repo: str | None = None) -> str:
    if not which("graphify"):
        return "graphify is not installed (run camarones setup)."
    g = env.repo_graph(repo) if repo else env.CACHE / "graph" / "graph.json"
    if not g.exists():
        return f"No code graph for {repo or 'the workspace'} yet — run `camarones graph`."
    r = run(["graphify", "query", question, "--graph", str(g)], check=False, capture=True)
    return (r.stdout or r.stderr or "").strip()[-12000:] or "No result."


HANDLERS = {"search_docs": search_docs, "read_doc": read_doc, "list_docs": list_docs, "doc_status": doc_status,
            "repo_graph": repo_graph}


def handle(msg: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None                                    # notifications need no answer
    if method == "initialize":
        name = docs.workspace()["project"]["name"] if WS_FILE.exists() else "no project"
        result = {"protocolVersion": msg.get("params", {}).get("protocolVersion", PROTOCOL),
                  "capabilities": {"tools": {}},
                  "serverInfo": {"name": "camarones", "version": VERSIONS["kit"]},
                  "instructions": f"Living documentation of {name}. Search it before implementing; confirmed pages are "
                                  "the source of truth, drafts must be verified against the code."}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        p = msg.get("params", {})
        fn = HANDLERS.get(p.get("name"))
        if not fn:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool {p.get('name')}"}}
        try:
            text, err = (fn(**(p.get("arguments") or {})) if WS_FILE.exists() and DOCS.exists()
                         else f"No Camarones project found from {ROOT}."), False
        except Exception as e:  # noqa: BLE001 — a tool failure is reported to the agent, never kills the server
            text, err = f"{type(e).__name__}: {e}", True
        result = {"content": [{"type": "text", "text": text}], "isError": err}
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def serve_stdio() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            reply = handle(json.loads(line))
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        if reply:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()


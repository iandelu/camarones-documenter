"""MCP server: agents search and read the project docs and query the code graph while they implement. Stdio
(newline-delimited JSON-RPC 2.0) or Streamable HTTP on 127.0.0.1 with this machine's token (`camaron mcp --http`).
Stdlib only, no API keys. Writes are drafts only (R32): an AI draft can be edited, a page a person confirmed or owns
never is (the proposal waits for review), and nothing here confirms. Running units needs `mcp.pipeline_control`."""
from __future__ import annotations

import datetime as dt, hmac, json, re, secrets, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .common import HOME, ROOT, DOCS, WORK, WS_FILE, VERSIONS, run, which
from .harness import freshness
from . import docs, env, usage

PROTOCOL = "2025-06-18"

TOOLS = [
    {"name": "search_docs", "description": "Full-text search over the project documentation (all repos, architecture, domain, "
                                           "flows, decisions). Returns matching pages with the section that matched, trust "
                                           "level, freshness and snippets; read just that section next.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"},
                                                      "limit": {"type": "integer", "default": 8}}, "required": ["query"]}},
    {"name": "read_doc", "description": "Read one documentation page by the path returned by search_docs/list_docs "
                                        "(e.g. architecture/overview.md). Pass `section` (a slug from search_docs or the "
                                        "page outline, or the heading text) to get only the TL;DR and that section.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "section": {"type": "string"}},
                     "required": ["path"]}},
    {"name": "list_docs", "description": "Index of every documentation page: path, title, type, trust "
                                         "(confirmed = human-verified source of truth, draft = AI-written).",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "doc_status", "description": "Documentation health: trust counts, pages needing re-confirmation, orphaned "
                                          "sources, repos whose code changed since the docs were last updated.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "ask", "description": "The documentation's answer material for a question: the best matching sections "
                                   "(TL;DR + section) of pages agents may read, each under its citation "
                                   "[path#section]. Answer from them and cite; no model is called.",
     "inputSchema": {"type": "object", "properties": {"question": {"type": "string"},
                                                      "limit": {"type": "integer", "default": 3}},
                     "required": ["question"]}},
    {"name": "propose_edit", "description": "Propose new text for a page, or for one of its sections. An AI draft is "
                                            "changed in place and stays a draft; a page a person confirmed or owns is "
                                            "never changed: the proposal is saved for review. Never confirms anything.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "text": {"type": "string"},
                                                      "section": {"type": "string"}, "reason": {"type": "string"}},
                     "required": ["path", "text"]}},
    {"name": "add_feedback", "description": "Leave a review comment on a page for a person (and the review-fixes unit).",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "text": {"type": "string"},
                                                      "by": {"type": "string"}}, "required": ["path", "text"]}},
    {"name": "mark_suspect", "description": "Say a page no longer matches the code: agents stop getting it until it is "
                                            "refreshed or a person acknowledges it (`camaron fresh --ack`).",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "reason": {"type": "string"}},
                     "required": ["path", "reason"]}},
    {"name": "pipeline_status", "description": "The documentation plan: units, their status and the last run.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "run_node", "description": "Start one ready unit of the plan in the background (needs "
                                        "`mcp: {pipeline_control: true}` in workspace.yaml).",
     "inputSchema": {"type": "object", "properties": {"unit": {"type": "string"}}, "required": ["unit"]}},
    {"name": "run_events", "description": "Events of a documentation run after a byte offset (from pipeline_status).",
     "inputSchema": {"type": "object", "properties": {"run": {"type": "string"}, "after": {"type": "integer", "default": 0}},
                     "required": ["run"]}},
    {"name": "kpis", "description": "Is the documentation working: cost and speed of runs, coverage, trust, usage.",
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
    usage.record("mcp:search_docs", channel="agent", hit=bool(hits))
    if not hits:
        return f"No page mentions: {query}"
    rows, served, held = _rows(), [], []
    for h in hits:
        r = rows.get(h["path"], {})
        ok, notice = freshness.gate(h["path"], r.get("trust", "draft"), r.get("freshness"))
        (served if ok else held).append((h, notice))
    out = "\n\n".join(_hit(h, rows.get(h["path"], {}), n) for h, n in served)
    if held:
        out += (f"\n\n{len(held)} page{'s' if len(held) > 1 else ''} withheld (out of date or unreviewed):\n"
                + "\n".join(f"- {n}" for _, n in held))
    return out.strip()


def _hit(h: dict, r: dict, notice: str | None) -> str:
    where = h["path"] + (f"#{h['section']}" if h.get("section") else "")
    then = (f'→ read_doc("{h["path"]}", section="{h["section"]}")\n' if h.get("section") else "")
    return (f"## {where} [{h['trust']} · {r.get('fresh', '?')}] — {h['title']}\n" + (f"> ⚠ {notice}\n" if notice else "")
            + "\n".join(f"> {l}" for l in h["lines"]) + ("\n" + then.rstrip() if then else ""))


def read_doc(path: str, section: str | None = None) -> str:
    f = _file(path)
    usage.record("mcp:read_doc", channel="agent", page=path if f else None)
    if not f:
        return f"No page at {path}. Use list_docs or search_docs."
    r = _rows().get(path.removeprefix("docs/"), {})
    ok, notice = freshness.gate(path.removeprefix("docs/"), r.get("trust", "draft"), r.get("freshness"))
    if not ok:
        return notice
    text = f.read_text(encoding="utf-8")
    fm, body = docs.split_fm(text)
    outline = ", ".join(s["slug"] for s in docs.sections(body))
    head = (f"<!-- trust: {r.get('trust', '?')} · freshness: {r.get('fresh', '?')} · file: {r.get('file', '')}"
            + (f" · sections: {outline}" if outline else "") + " -->\n")
    warn = f"> ⚠ {notice}\n\n" if notice else ""
    if not section:
        return head + warn + text
    found = docs.section_text(body, section)
    if not found:
        return f"No section '{section}' in {path}. Sections: {outline or 'none'}."
    title = fm.get("title") or docs.first_heading(body) or path
    return head + warn + f"# {title}\n\n" + (docs.tldr(body) + "\n\n" if docs.tldr(body) else "") + found[1] + "\n"


def list_docs() -> str:
    usage.record("mcp:list_docs")
    rows = docs.collect()
    return "\n".join(f"- {r['path']} [{r['trust']}{'' if freshness.gate(r['path'], r['trust'], r.get('freshness'))[0] else ', withheld'}] "
                     f"{r['title']}" + (f" — {r['description']}" if r["description"] else "") for r in rows) or "No docs yet."


def doc_status() -> str:
    usage.record("mcp:doc_status")
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
    usage.record("mcp:repo_graph")
    if not which("graphify"):
        return "graphify is not installed (run camarones setup)."
    g = env.repo_graph(repo) if repo else env.CACHE / "graph" / "graph.json"
    if not g.exists():
        return f"No code graph for {repo or 'the workspace'} yet — run `camaron graph`."
    r = run(["graphify", "query", question, "--graph", str(g)], check=False, capture=True)
    return (r.stdout or r.stderr or "").strip()[-12000:] or "No result."


def ask(question: str, limit: int = 3) -> str:
    hits = docs.search(question, 20) if re.search(r"\w\w", question) else []
    usage.record("mcp:ask", channel="agent", hit=bool(hits))
    rows, parts = _rows(), []
    for h in hits:
        r = rows.get(h["path"], {})
        ok, notice = freshness.gate(h["path"], r.get("trust", "draft"), r.get("freshness"))
        f = _file(h["path"])
        if not ok or not f:
            continue
        body = docs.split_fm(f.read_text(encoding="utf-8"))[1]
        found = docs.section_text(body, h["section"]) if h.get("section") else None
        cite = h["path"] + (f"#{h['section']}" if found else "")
        tl = docs.tldr(body)
        text = found[1] if found else body.strip()
        parts.append(f"[{cite}] ({r.get('trust', '?')} · {r.get('fresh', '?')})\n" + (f"> ⚠ {notice}\n" if notice else "")
                     + (tl + "\n\n" if tl and found else "") + text)
        if len(parts) >= limit:
            break
    if not parts:
        return f"Nothing in the docs answers: {question}. Read the code (repo_graph) and say the docs lack it."
    return ("Answer from these sections only and cite each claim as [path#section]. `confirmed` is the source of "
            "truth; `draft` must be checked against the code.\n\n" + "\n\n---\n\n".join(parts))


# ---------- writes: drafts only ----------
PROPOSALS = WORK / "proposals"


def _replace_section(body: str, section: str, text: str) -> str | None:
    found = docs.section_text(body, section)
    if not found:
        return None
    lines = body.splitlines()
    s = found[0]
    head = lines[s["start"]]
    return "\n".join(lines[:s["start"]] + [head, "", text.strip(), ""] + lines[s["end"]:]).rstrip() + "\n"


def propose_edit(path: str, text: str, section: str | None = None, reason: str = "", by: str = "agent") -> str:
    logical = path.removeprefix("docs/")
    f = _file(logical)
    if not f:
        return f"No page at {path}."
    text = docs.split_fm(text)[1] if text.lstrip().startswith("---") else text   # frontmatter is never taken
    r = _rows().get(logical, {})
    raw = f.read_text(encoding="utf-8")
    fm, body = docs.split_fm(raw)
    if r.get("trust") == "draft" and r.get("owner") != "human" and r.get("space", "docs") == "docs":
        new = _replace_section(body, section, text) if section else text.strip() + "\n"
        if new is None:
            return f"No section '{section}' in {path}. Sections: {', '.join(s['slug'] for s in docs.sections(body))}."
        f.write_text(docs.join_fm(fm, new), encoding="utf-8", newline="\n")
        usage.record("mcp:propose_edit", channel="agent", page=logical)
        return f"applied to {path} ({'section ' + section if section else 'whole page'}); it stays an AI draft."
    PROPOSALS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = PROPOSALS / f"{stamp}-{re.sub(r'[^a-z0-9]+', '-', logical.lower()).strip('-')}.md"
    out.write_text(f"# Proposal for `{logical}`" + (f" § {section}" if section else "") + "\n\n"
                   + (f"Why: {reason}\n\n" if reason else "") + text.strip() + "\n", encoding="utf-8", newline="\n")
    docs.add_feedback(r.get("file", f"docs/{logical}"), f"proposed change ({out.relative_to(ROOT).as_posix()})"
                      + (f": {reason}" if reason else ""), by)
    usage.record("mcp:propose_edit", channel="agent", page=logical)
    return (f"{path} is {r.get('trust')}{' and owned by a person' if r.get('owner') == 'human' else ''}: not changed. "
            f"The proposal waits for review in {out.relative_to(ROOT).as_posix()}.")


def add_feedback(path: str, text: str, by: str = "agent") -> str:
    logical = path.removeprefix("docs/")
    r = _rows().get(logical)
    if not r:
        return f"No page at {path}."
    docs.add_feedback(r["file"], text, by)
    return f"recorded for {path}: a person sees it in Review, and the review-fixes unit applies it."


def mark_suspect(path: str, reason: str, by: str = "agent") -> str:
    logical = path.removeprefix("docs/")
    if logical not in _rows():
        return f"No page at {path}."
    freshness.flag(logical, reason, by)
    return f"marked {path} as out of date ({reason}); agents stop getting it until it is refreshed or acknowledged."


# ---------- pipeline control ----------
def pipeline_status() -> str:
    from . import plan
    from .harness import runs
    data = plan.load()
    d, total = plan.progress(data)
    lines = [f"{d}/{total} units done"] + [f"- {u['id']} [{u['status']}] {u['title']}" for u in data["units"]]
    last = (runs.rows() or [None])[0]
    if last:
        lines.append(f"last run: {last.get('run')} ({'finished' if last.get('finished') else 'running'})")
    return "\n".join(lines)


def _spawn_run(uid: str) -> str:
    import subprocess
    from .common import KIT, uv
    subprocess.Popen([uv(), "run", "--quiet", "--script", str(KIT / "camarones.py"), "run", "--only", uid,
                      "--parallel", "1"], cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, start_new_session=True)
    return f"started a run for {uid}"


def run_node(unit: str) -> str:
    from . import plan
    if not (docs.workspace().get("mcp") or {}).get("pipeline_control"):
        return ("Running units from the MCP is disabled: set `mcp: {pipeline_control: true}` in "
                ".camarones/workspace.yaml to allow it (runs start agents, which costs).")
    if not any(u["id"] == unit for u in plan.load()["units"]):
        return f"unknown unit {unit}"
    return _spawn_run(unit) + " — follow it with pipeline_status and run_events."


def run_events(run: str, after: int = 0) -> str:
    from .harness import runs
    if run not in runs.ids():
        return f"no run {run}"
    from .common import CTX
    from .harness.events import EventLog
    events, offset = EventLog(CTX.runs / run / "events.jsonl").read(int(after or 0))
    return json.dumps({"next": offset, "events": events}, ensure_ascii=False)


def kpis() -> str:
    from .harness import kpis as k
    return json.dumps(k.report(months=1, run_check=False), ensure_ascii=False, default=str)[:20000]


HANDLERS = {"search_docs": search_docs, "read_doc": read_doc, "list_docs": list_docs, "doc_status": doc_status,
            "ask": ask, "repo_graph": repo_graph, "propose_edit": propose_edit, "add_feedback": add_feedback,
            "mark_suspect": mark_suspect, "pipeline_status": pipeline_status, "run_node": run_node,
            "run_events": run_events, "kpis": kpis}

PROMPTS = {
    "implement-feature": {
        "description": "Look the feature up in the docs before writing code, then keep the docs current.",
        "arguments": [{"name": "feature", "description": "What you are about to build or change", "required": True}],
        "text": "I am about to work on: {feature}.\n1. Call `search_docs` with its key terms (or `ask` with the question) "
                "and read only the sections the hits name with `read_doc(path, section)`.\n2. Treat `confirmed` pages as "
                "the source of truth; verify `draft` pages against the code; withheld pages mean read the code.\n"
                "3. Use `repo_graph` for code structure instead of broad greps.\n4. Summarise what the docs say, with "
                "citations [path#section], and any contradiction with the code, before you change anything.\n"
                "5. After the change, update the affected pages (skill `cam-docs-update`) and run the kit's `check`."},
    "update-docs": {
        "description": "After changing code: find the pages that describe it and update them.",
        "arguments": [{"name": "files", "description": "The code files you changed (repo:path, comma-separated)",
                       "required": True}],
        "text": "I changed: {files}.\n1. `search_docs` for the classes, endpoints, topics and tables those files touch; pages "
                "whose `x-sources` cite them must be updated.\n2. Edit only `draft` pages directly; for `confirmed` "
                "pages, propose the change and tell the person they need re-confirming.\n3. Generated blocks "
                "(`<!-- generated:… -->`) are refreshed by the kit's `blocks` command, never by hand.\n4. Run the kit's "
                "`check` and fix what it reports on the pages you touched."},
}


def resources() -> list[dict]:
    out = [{"uri": "camdocs://llms.txt", "name": "llms.txt", "title": "Documentation index",
            "description": "Every page agents may read, with its trust level.", "mimeType": "text/plain"}]
    out += [{"uri": f"camdocs://{r['path']}", "name": r["path"], "title": r["title"],
             "description": r["description"] or r["title"], "mimeType": "text/markdown"} for r in docs.readable()]
    return out


def read_resource(uri: str) -> str:
    path = uri.removeprefix("camdocs://")
    if path == "llms.txt":
        docs.llms()
        return (DOCS / "llms.txt").read_text(encoding="utf-8")
    return read_doc(path)


def handle(msg: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None                                    # notifications need no answer
    if method == "initialize":
        name = docs.workspace()["project"]["name"] if WS_FILE.exists() else "no project"
        result = {"protocolVersion": msg.get("params", {}).get("protocolVersion", PROTOCOL),
                  "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                  "serverInfo": {"name": "camarones", "version": VERSIONS["kit"]},
                  "instructions": f"Living documentation of {name}. Search it before implementing; confirmed pages are "
                                  "the source of truth, drafts must be verified against the code."}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method in ("resources/list", "resources/read", "prompts/get") and not (WS_FILE.exists() and DOCS.exists()):
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32002, "message": f"No Camarones project found from {ROOT}."}}
    elif method == "resources/list":
        result = {"resources": resources()}
    elif method == "resources/read":
        uri = msg.get("params", {}).get("uri", "")
        result = {"contents": [{"uri": uri, "mimeType": "text/plain" if uri.endswith(".txt") else "text/markdown",
                                "text": read_resource(uri)}]}
    elif method == "prompts/list":
        result = {"prompts": [{"name": n, "description": p["description"], "arguments": p["arguments"]}
                              for n, p in PROMPTS.items()]}
    elif method == "prompts/get":
        params = msg.get("params", {})
        p = PROMPTS.get(params.get("name"))
        if not p:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown prompt {params.get('name')}"}}
        args = {a["name"]: (params.get("arguments") or {}).get(a["name"], "") for a in p["arguments"]}
        result = {"description": p["description"],
                  "messages": [{"role": "user", "content": {"type": "text", "text": p["text"].format(**args)}}]}
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


# ---------- Streamable HTTP on 127.0.0.1 ----------
TOKEN_FILE = HOME / ".camarones" / "mcp-token"
LOCAL_ORIGIN = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")


def token() -> str:
    """This machine's token for the HTTP transport (created once, readable only by you on macOS/Linux)."""
    if TOKEN_FILE.is_file() and len(TOKEN_FILE.read_text(encoding="utf-8").strip()) >= 32:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(value, encoding="utf-8")
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass
    return value


class HttpHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code: int, body: dict | None = None):
        data = json.dumps(body).encode("utf-8") if body is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path.split("?")[0] != "/mcp":
            return self._send(404, {"error": "not found"})
        origin = self.headers.get("Origin")
        if origin and not LOCAL_ORIGIN.match(origin):
            return self._send(403, {"error": "origin not allowed"})
        auth = self.headers.get("Authorization", "")
        if not hmac.compare_digest(auth.encode(), f"Bearer {token()}".encode()):
            return self._send(401, {"error": "missing or wrong token"})
        try:
            msg = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"null")
        except json.JSONDecodeError:
            return self._send(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
        reply = handle(msg) if isinstance(msg, dict) else None
        return self._send(200, reply) if reply else self._send(202)


def http_server(port: int = 8765) -> ThreadingHTTPServer:
    token()
    return ThreadingHTTPServer(("127.0.0.1", port), HttpHandler)

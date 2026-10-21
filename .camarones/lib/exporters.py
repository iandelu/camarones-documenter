"""Exporters (R35). Built in: the docs as one print-ready HTML (a PDF when a headless Chrome/Chromium is installed) and
a guided tour of a business flow (HTML slides from its Steps table). Confluence and Notion are kit plugins that send
the docs outside the machine: off until someone runs `camaron plugins enable <name>` here, and they need their own
URL and token. Only pages agents may read are exported (the freshness gate), so nothing withheld leaves."""
from __future__ import annotations

import base64, html as htmllib, json, os, re, shutil, urllib.request
from pathlib import Path

from .common import CACHE, IS_MAC, IS_WIN, ROOT, run, which
from . import docs

OUT = CACHE / "export"


class ExportError(RuntimeError):
    """The export cannot run; nothing was sent."""


# ---------- a small Markdown renderer (what kit pages use: headings, lists, tables, code, quotes, links) ----------
def _inline(text: str) -> str:
    t = htmllib.escape(text, quote=False)
    t = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?!\w)", r"<em>\1</em>", t)
    return re.sub(r"!?\[([^\]]*)\]\(([^)\s]+)\)", lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', t)


def blocks(md: str) -> list[dict]:
    """The page as blocks: heading · paragraph · list · table · code · quote."""
    lines, out, i = md.splitlines(), [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if m := re.match(r"^(```|~~~)\s*(\S*)", line):
            j = i + 1
            while j < len(lines) and not lines[j].startswith(m.group(1)):
                j += 1
            out.append({"type": "code", "lang": m.group(2), "text": "\n".join(lines[i + 1:j])})
            i = j + 1
            continue
        if m := re.match(r"^(#{1,6})\s+(.*)", line):
            out.append({"type": "heading", "level": len(m.group(1)), "text": m.group(2).strip()})
            i += 1
            continue
        if line.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            out.append({"type": "table", "rows": rows})
            continue
        if line.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i].lstrip("> ").rstrip())
                i += 1
            out.append({"type": "quote", "text": " ".join(quote)})
            continue
        if re.match(r"^\s*([-*+]|\d+\.)\s+", line):
            ordered, items = bool(re.match(r"^\s*\d+\.", line)), []
            while i < len(lines) and re.match(r"^\s*([-*+]|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*+]|\d+\.)\s+", "", lines[i]))
                i += 1
            out.append({"type": "list", "ordered": ordered, "items": items})
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,6}\s|```|~~~|>|\s*\||\s*([-*+]|\d+\.)\s)",
                                                                    lines[i]):
            para.append(lines[i].strip())
            i += 1
        out.append({"type": "paragraph", "text": " ".join(para)})
    return out


def to_html(md: str) -> str:
    parts = []
    for b in blocks(md):
        t = b["type"]
        if t == "heading":
            parts.append(f'<h{b["level"]} id="{docs.slug(b["text"])}">{_inline(b["text"])}</h{b["level"]}>')
        elif t == "paragraph":
            parts.append(f"<p>{_inline(b['text'])}</p>")
        elif t == "quote":
            parts.append(f"<blockquote><p>{_inline(b['text'])}</p></blockquote>")
        elif t == "list":
            tag = "ol" if b["ordered"] else "ul"
            parts.append(f"<{tag}>" + "".join(f"<li>{_inline(x)}</li>" for x in b["items"]) + f"</{tag}>")
        elif t == "table" and b["rows"]:
            head, *body = b["rows"]
            parts.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                         + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body)
                         + "</tbody></table>")
        elif t == "code":
            cls = f' class="language-{b["lang"]}"' if b["lang"] else ""
            parts.append(f"<pre><code{cls}>{htmllib.escape(b['text'], quote=False)}</code></pre>")
    return "\n".join(parts)


# ---------- what gets exported ----------
def pages() -> list[tuple[dict, str]]:
    """(row, body) for every page agents may read, in llms.txt order; working notes stay out."""
    out = []
    for r in docs.readable():
        if r["type"] == "interview" or r["path"].startswith("interview/") or r.get("space", "docs") != "docs":
            continue
        out.append((r, docs.split_fm((ROOT / r["file"]).read_text(encoding="utf-8"))[1]))
    return out


STYLE = """body{font:15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;color:#0b0b0b;max-width:46rem;margin:2rem auto;
padding:0 1rem}h1,h2,h3{letter-spacing:-.02em;line-height:1.2}h2{border-top:1px solid #e6e6e6;padding-top:1rem}
code{font:.9em ui-monospace,Menlo,monospace;background:#f6f6f6;padding:.1em .3em;border-radius:4px}
pre{background:#f6f6f6;padding:.8rem;border-radius:8px;overflow:auto}pre code{background:none;padding:0}
table{border-collapse:collapse;width:100%;font-size:.9em}th,td{border-bottom:1px solid #e6e6e6;padding:.4rem .6rem;
text-align:left;vertical-align:top}blockquote{margin:0;padding:.2rem 1rem;border-left:2px solid #0b0b0b}
.meta{color:#6b6b6b;font-size:.85em}article{break-after:page}
@media print{body{margin:0;max-width:none}a{color:inherit;text-decoration:none}}"""


def export_print() -> Path:
    ws = docs.workspace()
    arts = [f'<article id="{docs.slug(r["path"])}"><p class="meta">{htmllib.escape(r["path"])} · {r["trust"]}</p>'
            f"{to_html(body)}</article>" for r, body in pages()]
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "docs.html"
    out.write_text(f'<!doctype html><html lang="en"><meta charset="utf-8"><title>{htmllib.escape(ws["project"]["name"])}'
                   f"</title><style>{STYLE}</style><body>{''.join(arts)}</body></html>\n", encoding="utf-8")
    return out


def _chrome() -> str | None:
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome", "msedge"):
        if which(name):
            return which(name)
    candidates = (["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                   "/Applications/Chromium.app/Contents/MacOS/Chromium"] if IS_MAC else
                  [os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                   os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe")] if IS_WIN else [])
    return next((c for c in candidates if Path(c).is_file()), None)


def export_pdf() -> Path:
    """A PDF with a headless Chrome/Chromium/Edge; without one, the print-ready HTML (print it to PDF yourself)."""
    page = export_print()
    browser = _chrome()
    if not browser:
        return page
    pdf = OUT / "docs.pdf"
    r = run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", page.as_uri()],
            check=False, quiet=True)
    return pdf if r.returncode == 0 and pdf.is_file() else page


# ---------- guided tour of a business flow ----------
def tour(path: str) -> dict:
    logical = path.removeprefix("docs/")
    f = dict(docs.iter_docs()).get(logical)
    if not f:
        raise ExportError(f"no page at {path}")
    fm, body = docs.split_fm(f.read_text(encoding="utf-8"))
    found = docs.section_text(body, "steps")
    table = next((b for b in blocks(found[1]) if b["type"] == "table"), None) if found else None
    if not table or len(table["rows"]) < 2:
        raise ExportError(f"{path} has no Steps table to tour")
    head = [h.lower() for h in table["rows"][0]]
    col = lambda row, name: row[head.index(name)].strip("`") if name in head and head.index(name) < len(row) else ""  # noqa: E731
    steps = [{"title": col(r, "step") or r[0], "repo": col(r, "repo"), "entrypoint": col(r, "entrypoint"),
              "evidence": col(r, "evidence")} for r in table["rows"][1:]]
    return {"title": fm.get("title") or logical, "summary": docs.tldr(body).replace("> **TL;DR:**", "").strip(" >"),
            "steps": steps, "path": logical}


def export_tour(path: str) -> Path:
    t = tour(path)
    slides = [f'<section><p class="meta">{htmllib.escape(t["path"])}</p><h1>{htmllib.escape(t["title"])}</h1>'
              f"<p>{_inline(t['summary'])}</p><p class=meta>{len(t['steps'])} steps · → to start</p></section>"]
    for n, s in enumerate(t["steps"], 1):
        slides.append(f'<section><p class="meta">Step {n} of {len(t["steps"])}</p><h1>{htmllib.escape(s["title"])}</h1>'
                      f'<dl><dt>Repo</dt><dd><code>{htmllib.escape(s["repo"])}</code></dd><dt>Entry point</dt>'
                      f'<dd><code>{htmllib.escape(s["entrypoint"])}</code></dd><dt>Evidence</dt>'
                      f'<dd><code>{htmllib.escape(s["evidence"])}</code></dd></dl></section>')
    script = ("let i=0;const s=[...document.querySelectorAll('section')];const show=()=>s.forEach((x,j)=>x.hidden=j!==i);"
              "show();addEventListener('keydown',e=>{if(e.key==='ArrowRight'&&i<s.length-1)i++;"
              "if(e.key==='ArrowLeft'&&i>0)i--;show()});addEventListener('click',()=>{if(i<s.length-1){i++;show()}})")
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"tour-{Path(t['path']).stem}.html"
    out.write_text(f'<!doctype html><html lang="en"><meta charset="utf-8"><title>{htmllib.escape(t["title"])} — tour</title>'
                   f"<style>{STYLE} section{{min-height:80vh;display:flex;flex-direction:column;justify-content:center}}"
                   f"dt{{color:#6b6b6b;font-size:.8em;text-transform:uppercase;letter-spacing:.06em}}dd{{margin:0 0 1rem}}"
                   f"</style><body>{''.join(slides)}<script>{script}</script></body></html>\n", encoding="utf-8")
    return out


# ---------- third-party: Confluence, Notion (kit plugins that send data; enabled per machine) ----------
def _enabled(name: str) -> None:
    from .harness import plugins
    p = next((x for x in plugins.discover() if x.name == name), None)
    if not p or not p.active:
        raise ExportError(f"{name} sends the docs outside this machine: turn it on here with "
                          f"`camaron plugins enable {name}` first")


def _need(env: dict, *keys: str) -> None:
    missing = [k for k in keys if not env.get(k)]
    if missing:
        raise ExportError(f"set {', '.join(missing)} (environment) to export")


def _call(opener, url: str, method: str, payload: dict | None, headers: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload is not None else None, method=method,
                                 headers={**headers, "Content-Type": "application/json", "Accept": "application/json"})
    with opener(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def _confluence(env: dict, opener) -> int:
    _need(env, "CONFLUENCE_URL", "CONFLUENCE_USER", "CONFLUENCE_TOKEN", "CONFLUENCE_SPACE")
    base = env["CONFLUENCE_URL"].rstrip("/") + "/rest/api/content"
    auth = base64.b64encode(f"{env['CONFLUENCE_USER']}:{env['CONFLUENCE_TOKEN']}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}
    n = 0
    for r, body in pages():
        storage = to_html(body)
        found = _call(opener, f"{base}?spaceKey={env['CONFLUENCE_SPACE']}&title={urllib.request.quote(r['title'])}"
                              "&expand=version", "GET", None, headers).get("results") or []
        payload = {"type": "page", "title": r["title"], "space": {"key": env["CONFLUENCE_SPACE"]},
                   "body": {"storage": {"value": storage, "representation": "storage"}}}
        if found:
            payload["version"] = {"number": int((found[0].get("version") or {}).get("number", 1)) + 1}
            _call(opener, f"{base}/{found[0]['id']}", "PUT", payload, headers)
        else:
            _call(opener, base, "POST", payload, headers)
        n += 1
    return n


def _rich(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": re.sub(r"[*`]", "", text)[:1900]}}]


def _notion_blocks(md: str) -> list[dict]:
    out = []
    for b in blocks(md):
        t = b["type"]
        if t == "heading":
            kind = f"heading_{min(3, max(1, b['level']))}"
            out.append({"object": "block", "type": kind, kind: {"rich_text": _rich(b["text"])}})
        elif t in ("paragraph", "quote"):
            kind = "quote" if t == "quote" else "paragraph"
            out.append({"object": "block", "type": kind, kind: {"rich_text": _rich(b["text"])}})
        elif t == "list":
            kind = "numbered_list_item" if b["ordered"] else "bulleted_list_item"
            out += [{"object": "block", "type": kind, kind: {"rich_text": _rich(x)}} for x in b["items"]]
        elif t == "code":
            out.append({"object": "block", "type": "code", "code": {"rich_text": _rich(b["text"]),
                                                                   "language": b["lang"] or "plain text"}})
        elif t == "table":
            out += [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich(" · ".join(r))}}
                    for r in b["rows"]]
    return out[:100]                                     # the API's limit per request


def _notion(env: dict, opener) -> int:
    _need(env, "NOTION_TOKEN", "NOTION_PARENT_PAGE")
    headers = {"Authorization": f"Bearer {env['NOTION_TOKEN']}", "Notion-Version": "2022-06-28"}
    n = 0
    for r, body in pages():
        _call(opener, "https://api.notion.com/v1/pages", "POST",
              {"parent": {"page_id": env["NOTION_PARENT_PAGE"]},
               "properties": {"title": {"title": _rich(r["title"])}}, "children": _notion_blocks(body)}, headers)
        n += 1
    return n


TARGETS = {"confluence": _confluence, "notion": _notion}


def export_to(name: str, env: dict | None = None, opener=urllib.request.urlopen) -> int:
    if name not in TARGETS:
        raise ExportError(f"unknown exporter {name} (use pdf, tour, {', '.join(TARGETS)})")
    _enabled(name)
    return TARGETS[name](dict(os.environ) if env is None else env, opener)


def clean() -> None:
    shutil.rmtree(OUT, ignore_errors=True)

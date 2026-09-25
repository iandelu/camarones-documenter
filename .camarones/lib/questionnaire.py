"""Team questionnaire: the deferred form of the interviews. An agent writes `questionnaire.yaml` (inferred answers +
options); `export` turns it into a self-contained HTML form and a Markdown copy to share; each teammate sends back an
answers file (JSON from the form, or the filled Markdown); `import_files` stores one YAML per person under
`responses/`, and the interview units consolidate them. No AI, no server, nothing leaves the machine."""
from __future__ import annotations

import datetime as dt
import hashlib, json, re, unicodedata
from pathlib import Path

import yaml

from .common import DOCS

QDIR = DOCS / "interview" / "questionnaire"
SOURCE = QDIR / "questionnaire.yaml"
RESPONSES = QDIR / "responses"
HTML = QDIR / "questionnaire.html"
MD = QDIR / "questionnaire.md"
KINDS = ("single", "multi", "confirm", "text")
TOPICS = ("context", "language", "history")
CONFIRM = ("yes", "no", "unsure")
ANSWER_NAMES = re.compile(r"^(answers|respuestas|questionnaire|cuestionario)[-_ ].*\.(json|ya?ml|md)$", re.I)

LABELS = {
    "en": {
        "title": "Team questionnaire", "name": "Name", "role": "Role", "other": "Other", "comment": "Comment",
        "answer": "Answer", "inferred": "What we inferred", "evidence": "evidence",
        "yes": "Yes, correct", "no": "No", "unsure": "I don't know",
        "topics": {"context": "Context", "language": "Language", "history": "History"},
        "how_md": "How to answer: tick the options with `[x]`, write after the colons and send this file back "
                  "(or commit it in a pull request). Leave out what you do not know.",
        "how_html": "Answer what you know and leave the rest blank. Your answers stay in this browser until you press "
                    "“Download answers”; then send that file back to whoever shared this form.",
        "download": "Download answers", "need_name": "Write your name first.",
        "saved": "Downloaded {file}. Send it back to whoever shared this form.",
        "answered": "answered", "file": "answers",
        "desc": "Questionnaire for the team; answers are imported with `interview import`.",
    },
    "es": {
        "title": "Cuestionario para el equipo", "name": "Nombre", "role": "Rol", "other": "Otra", "comment": "Comentario",
        "answer": "Respuesta", "inferred": "Lo que hemos deducido", "evidence": "evidencia",
        "yes": "Sí, es correcto", "no": "No", "unsure": "No sé",
        "topics": {"context": "Contexto", "language": "Lenguaje", "history": "Historia"},
        "how_md": "Cómo responder: marca las opciones con `[x]`, escribe después de los dos puntos y devuelve este "
                  "fichero (o súbelo en un pull request). Deja en blanco lo que no sepas.",
        "how_html": "Responde lo que sepas y deja el resto en blanco. Las respuestas se quedan en este navegador hasta "
                    "que pulses «Descargar respuestas»; después envía ese fichero a quien te pasó el formulario.",
        "download": "Descargar respuestas", "need_name": "Escribe primero tu nombre.",
        "saved": "Descargado {file}. Envíaselo a quien te pasó el formulario.",
        "answered": "respondidas", "file": "respuestas",
        "desc": "Cuestionario para el equipo; las respuestas se importan con `interview import`.",
    },
}


# ---------- the questionnaire ----------
def load() -> dict:
    if not SOURCE.exists():
        raise ValueError(f"no questionnaire yet: the `questionnaire` unit writes {SOURCE.relative_to(DOCS.parent).as_posix()}")
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8")) or {}
    qs = data.get("questions") or []
    if not qs:
        raise ValueError("questionnaire.yaml has no questions")
    seen = set()
    for i, q in enumerate(qs, 1):
        where = f"questionnaire.yaml question {i} ({q.get('id', '?')})"
        if not q.get("id") or not q.get("text"):
            raise ValueError(f"{where}: needs `id` and `text`")
        if q["id"] in seen:
            raise ValueError(f"{where}: duplicate id")
        seen.add(q["id"])
        q["id"] = str(q["id"])
        q.setdefault("kind", "single" if q.get("options") else "text")
        if q["kind"] not in KINDS:
            raise ValueError(f"{where}: kind must be one of {', '.join(KINDS)}")
        if q["kind"] in ("single", "multi") and not q.get("options"):
            raise ValueError(f"{where}: a {q['kind']} question needs `options`")
        q["options"] = [str(o) for o in q.get("options") or []]
        if q.get("topic") not in TOPICS:
            q["topic"] = "context"
    data["questions"] = qs
    data["id"] = hashlib.sha1(json.dumps(qs, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:10]
    return data


def export(lang: str = "es") -> list[Path]:
    """Write questionnaire.html (offline form) and questionnaire.md (fill-in copy). Returns [html, md]."""
    data = load()
    L = LABELS["es" if lang == "es" else "en"]
    QDIR.mkdir(parents=True, exist_ok=True)
    HTML.write_text(_html(data, L, lang), encoding="utf-8", newline="\n")
    MD.write_text(_md(data, L), encoding="utf-8", newline="\n")
    return [HTML, MD]


def _md(data: dict, L: dict) -> str:
    title = data.get("title") or L["title"]
    fm = yaml.safe_dump({"type": "interview", "title": title, "description": L["desc"]},
                        sort_keys=False, allow_unicode=True, width=1000)
    out = [f"---\n{fm}---", f"# {title}", ""]
    if data.get("intro"):
        out += [data["intro"].strip(), ""]
    out += [L["how_md"], "", f"{L['name']}:", f"{L['role']}:", ""]
    for q in data["questions"]:
        out += [f"## {q['id']} · {L['topics'][q['topic']]}", "", f"**{q['text'].strip()}**", ""]
        if q.get("inferred"):
            ev = f" ({L['evidence']}: `{q['evidence']}`)" if q.get("evidence") else ""
            out += [f"> {L['inferred']}: {q['inferred'].strip()}{ev}", ""]
        if q["kind"] == "text":
            out += [f"{L['answer']}:", "", ""]
            continue
        opts = [L[v] for v in CONFIRM] if q["kind"] == "confirm" else q["options"] + [f"{L['other']}:"]
        out += [f"- [ ] {o}" for o in opts] + ["", f"{L['comment']}:", ""]
    return "\n".join(out).rstrip("\n") + "\n"


# ---------- answers ----------
def _clean(raw: dict, q: dict) -> dict:
    """One answer, normalised: only the non-empty keys among choice / other / text / comment."""
    if not isinstance(raw, dict):
        raw = {"text": raw} if q["kind"] == "text" else {"choice": raw}
    a, choice = {}, raw.get("choice")
    if q["kind"] == "multi":
        choice = [str(c) for c in (choice if isinstance(choice, list) else [choice] if choice else []) if str(c).strip()]
    elif isinstance(choice, list):
        choice = choice[0] if choice else None
    if q["kind"] == "confirm" and choice not in CONFIRM:
        choice = None
    if choice and q["kind"] != "text":
        a["choice"] = choice if q["kind"] == "multi" else str(choice)
    for k in ("other", "text", "comment"):
        v = str(raw.get(k) or "").strip()
        if v and not (k == "other" and q["kind"] in ("confirm", "text")) and not (k == "text" and q["kind"] != "text"):
            a[k] = v
    return a


def _parse_md(text: str, data: dict) -> dict:
    """A filled questionnaire.md (either language) → {respondent, role, answers}."""
    other = tuple(f"{LABELS[l]['other']}:" for l in LABELS)
    confirm = {LABELS[l][v].lower(): v for l in LABELS for v in CONFIRM}
    field = lambda line, key: next((line.split(":", 1)[1].strip() for l in LABELS                  # noqa: E731
                                    if line.lower().startswith(LABELS[l][key].lower() + ":")), None)
    kinds = {q["id"]: q for q in data["questions"]}
    head, *sections = re.split(r"^## ", text, flags=re.M)
    who = {"respondent": "", "role": ""}
    for line in head.splitlines():
        for key, dest in (("name", "respondent"), ("role", "role")):
            if (v := field(line, key)) is not None and not who[dest]:
                who[dest] = v
    answers = {}
    for sec in sections:
        qid, _, body = sec.partition("\n")
        q = kinds.get(qid.split(" ", 1)[0].strip())
        if not q:
            continue
        raw, ticked, block = {}, [], None
        for line in body.splitlines():
            if m := re.match(r"^\s*- \[([ xX])\] ?(.*)$", line):
                label = m.group(2).strip()
                if label.startswith(other):
                    if v := label.split(":", 1)[1].strip():
                        raw["other"] = v
                elif m.group(1) != " ":
                    ticked.append(confirm.get(label.lower()) if q["kind"] == "confirm" else label)
                block = None
            elif (v := field(line, "comment")) is not None:
                block, raw["comment"] = "comment", v
            elif (v := field(line, "answer")) is not None:
                block, raw["text"] = "text", v
            elif block:
                raw[block] = f"{raw[block]}\n{line}"
        raw["choice"] = ticked if q["kind"] == "multi" else (ticked[0] if ticked else None)
        if a := _clean(raw, q):
            answers[q["id"]] = a
    return {**who, "answers": answers}


def _slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "anon"


def _read(f: Path, data: dict) -> dict:
    text = f.read_text(encoding="utf-8-sig")
    if f.suffix.lower() == ".md":
        return _parse_md(text, data)
    raw = json.loads(text) if f.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValueError("not an answers file")
    kinds = {q["id"]: q for q in data["questions"]}
    answers = {k: a for k, v in (raw.get("answers") or {}).items() if k in kinds and (a := _clean(v, kinds[k]))}
    return {"respondent": str(raw.get("respondent") or "").strip(), "role": str(raw.get("role") or "").strip(),
            "date": str(raw.get("date") or ""), "answers": answers}


def import_files(paths: list) -> list[tuple[Path, str | None, str | None]]:
    """Import answers files (a folder → its answers-*/respuestas-* files). Returns (file, respondent, error) per file;
    the same file imported twice writes the same bytes, and a person's newer file replaces their older one."""
    data = load()
    files = []
    for p in map(Path, paths):
        files += sorted(f for f in p.iterdir() if f.is_file() and ANSWER_NAMES.match(f.name)) if p.is_dir() else [p]
    results = []
    for f in files:
        try:
            r = _read(f, data)
        except (OSError, ValueError, yaml.YAMLError) as e:
            results.append((f, None, f"cannot read it: {e}"))
            continue
        if not r["respondent"]:
            results.append((f, None, "no name in the file"))
            continue
        if not r["answers"]:
            results.append((f, None, "no answers to this questionnaire's questions"))
            continue
        RESPONSES.mkdir(parents=True, exist_ok=True)
        rec = {"respondent": r["respondent"], "role": r["role"], "date": r.get("date") or dt.date.today().isoformat(),
               "questionnaire": data["id"], "answers": r["answers"]}
        (RESPONSES / f"{_slug(r['respondent'])}.yaml").write_text(
            yaml.safe_dump(rec, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8", newline="\n")
        results.append((f, r["respondent"], None))
    return results


def responses() -> dict[str, dict]:
    if not RESPONSES.is_dir():
        return {}
    out = {}
    for f in sorted(RESPONSES.glob("*.yaml")):
        r = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        out[str(r.get("respondent") or f.stem)] = r
    return out


def status() -> dict:
    """Who answered, what nobody answered, and where people disagree (single-choice and confirm questions)."""
    data, rs = load(), responses()
    conflicts, unanswered = [], []
    for q in data["questions"]:
        given = {n: r.get("answers", {}).get(q["id"]) for n, r in rs.items()}
        given = {n: a for n, a in given.items() if a}
        if not given:
            unanswered.append(q["id"])
        if q["kind"] in ("single", "confirm"):
            by = {}
            for n, a in given.items():
                if a.get("choice"):
                    by.setdefault(a["choice"], []).append(n)
            if len(by) > 1:
                conflicts.append({"id": q["id"], "text": q["text"], "answers": by})
    return {"questions": len(data["questions"]), "unanswered": unanswered, "conflicts": conflicts,
            "respondents": [{"name": n, "role": r.get("role", ""), "date": r.get("date", ""),
                             "answered": len(r.get("answers") or {})} for n, r in rs.items()]}


# ---------- the offline form ----------
def _html(data: dict, L: dict, lang: str) -> str:
    payload = {"q": {k: data.get(k) for k in ("id", "title", "intro", "questions")}, "L": L, "lang": lang}
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    title = (data.get("title") or L["title"]).replace("&", "&amp;").replace("<", "&lt;")
    return FORM.replace("__TITLE__", title).replace("__LANG__", lang).replace("__DATA__", blob)


FORM = """<!doctype html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root { --bg: #fbf8f5; --card: #ffffff; --ink: #1f1b18; --muted: #6b625b; --line: #e6ddd5; --accent: #e8632b;
        --soft: #fff1e8; --focus: #b8461a; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #171412; --card: #221e1b; --ink: #f2ebe5; --muted: #a79d95; --line: #3a332e; --accent: #ff8a4c;
          --soft: #33241b; --focus: #ffb088; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 760px; margin: 0 auto; padding: 32px 16px 120px; }
h1 { font-size: 1.6rem; margin: 0 0 8px; }
.lead, .how { color: var(--muted); margin: 0 0 12px; }
.who { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 20px 0 28px; }
@media (max-width: 560px) { .who { grid-template-columns: 1fr; } }
label.f { display: block; font-size: .85rem; color: var(--muted); }
input[type=text], textarea { width: 100%; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px;
  background: var(--card); color: var(--ink); font: inherit; }
textarea { min-height: 64px; resize: vertical; }
input:focus-visible, textarea:focus-visible, button:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.q { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 18px; margin: 0 0 16px; }
.q h2 { font-size: 1.05rem; margin: 6px 0 10px; }
.chip { display: inline-block; font-size: .75rem; color: var(--accent); background: var(--soft); border-radius: 99px;
  padding: 1px 10px; }
.inf { background: var(--soft); border-radius: 8px; padding: 8px 12px; margin: 0 0 12px; font-size: .92rem; }
.inf code { font-size: .82rem; color: var(--muted); word-break: break-all; }
.opt { display: flex; gap: 8px; align-items: baseline; padding: 3px 0; }
.opt input[type=text] { flex: 1; }
.cm { margin-top: 10px; }
.bar { position: fixed; left: 0; right: 0; bottom: 0; background: var(--card); border-top: 1px solid var(--line);
  padding: 12px 16px; }
.bar div { max-width: 760px; margin: 0 auto; display: flex; gap: 12px; align-items: center; justify-content: space-between; }
#count { color: var(--muted); font-size: .9rem; }
#msg { font-size: .9rem; }
button { background: var(--accent); color: #fff; border: 0; border-radius: 8px; padding: 10px 18px; font: inherit;
  font-weight: 600; cursor: pointer; }
</style>
</head>
<body>
<main id="app"></main>
<div class="bar"><div><span id="count"></span><span id="msg" role="status"></span><button id="dl"></button></div></div>
<script type="application/json" id="data">__DATA__</script>
<script>
(function () {
  var D = JSON.parse(document.getElementById('data').textContent), L = D.L, Q = D.q;
  var KEY = 'camaron-questionnaire-' + Q.id, app = document.getElementById('app');
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === 'text') e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { if (c) e.appendChild(c); });
    return e;
  }
  function field(id, label, area) {
    var input = el(area ? 'textarea' : 'input', area ? { id: id } : { id: id, type: 'text' });
    return el('label', { 'class': 'f' }, [document.createTextNode(label), input]);
  }
  app.appendChild(el('h1', { text: Q.title || L.title }));
  if (Q.intro) app.appendChild(el('p', { 'class': 'lead', text: Q.intro }));
  app.appendChild(el('p', { 'class': 'how', text: L.how_html }));
  app.appendChild(el('div', { 'class': 'who' }, [field('who-name', L.name), field('who-role', L.role)]));
  Q.questions.forEach(function (q, i) {
    var box = el('section', { 'class': 'q', id: 'q-' + i });
    box.appendChild(el('span', { 'class': 'chip', text: L.topics[q.topic] || q.topic }));
    box.appendChild(el('h2', { text: q.text }));
    if (q.inferred) {
      var inf = el('p', { 'class': 'inf' }, [el('strong', { text: L.inferred + ': ' }), document.createTextNode(q.inferred)]);
      if (q.evidence) { inf.appendChild(document.createTextNode(' ')); inf.appendChild(el('code', { text: '(' + L.evidence + ': ' + q.evidence + ')' })); }
      box.appendChild(inf);
    }
    var name = 'q' + i;
    if (q.kind === 'text') {
      box.appendChild(field(name + '-text', L.answer, true));
    } else {
      var type = q.kind === 'multi' ? 'checkbox' : 'radio';
      var opts = q.kind === 'confirm' ? ['yes', 'no', 'unsure'] : q.options;
      opts.forEach(function (o, j) {
        var id = name + '-' + j;
        box.appendChild(el('div', { 'class': 'opt' }, [el('input', { type: type, name: name, id: id, value: o }),
          el('label', { 'for': id, text: q.kind === 'confirm' ? L[o] : o })]));
      });
      if (q.kind !== 'confirm') {
        box.appendChild(el('div', { 'class': 'opt' }, [el('label', { 'for': name + '-other', text: L.other + ':' }),
          el('input', { type: 'text', id: name + '-other' })]));
      }
      var cm = field(name + '-comment', L.comment, true); cm.className = 'f cm'; box.appendChild(cm);
    }
    app.appendChild(box);
  });
  function val(id) { var e = document.getElementById(id); return e ? e.value.trim() : ''; }
  function collect() {
    var answers = {};
    Q.questions.forEach(function (q, i) {
      var name = 'q' + i, a = {};
      if (q.kind === 'text') { if (val(name + '-text')) a.text = val(name + '-text'); }
      else {
        var picked = [].slice.call(document.querySelectorAll('input[name="' + name + '"]:checked')).map(function (e) { return e.value; });
        if (picked.length) a.choice = q.kind === 'multi' ? picked : picked[0];
        if (val(name + '-other')) a.other = val(name + '-other');
        if (val(name + '-comment')) a.comment = val(name + '-comment');
      }
      if (Object.keys(a).length) answers[q.id] = a;
    });
    return { respondent: val('who-name'), role: val('who-role'), date: new Date().toISOString().slice(0, 10),
             questionnaire: Q.id, answers: answers };
  }
  function count() {
    var n = Object.keys(collect().answers).length;
    document.getElementById('count').textContent = n + ' / ' + Q.questions.length + ' ' + L.answered;
  }
  function save() {
    var state = {};
    [].forEach.call(app.querySelectorAll('input, textarea'), function (e) {
      state[e.id] = (e.type === 'radio' || e.type === 'checkbox') ? e.checked : e.value;
    });
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (err) { /* private mode: nothing kept */ }
  }
  try {
    var saved = JSON.parse(localStorage.getItem(KEY) || '{}');
    Object.keys(saved).forEach(function (id) {
      var e = document.getElementById(id);
      if (!e) return;
      if (e.type === 'radio' || e.type === 'checkbox') e.checked = !!saved[id]; else e.value = saved[id];
    });
  } catch (err) { /* nothing saved */ }
  app.addEventListener('input', function () { save(); count(); });
  app.addEventListener('change', function () { save(); count(); });
  var dl = document.getElementById('dl'), msg = document.getElementById('msg');
  dl.textContent = L.download;
  dl.addEventListener('click', function () {
    var r = collect();
    if (!r.respondent) { msg.textContent = L.need_name; document.getElementById('who-name').focus(); return; }
    var slug = r.respondent.normalize('NFKD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'anon';
    var file = L.file + '-' + slug + '.json';
    var a = el('a', { href: URL.createObjectURL(new Blob([JSON.stringify(r, null, 2)], { type: 'application/json' })), download: file });
    document.body.appendChild(a); a.click(); a.remove();
    msg.textContent = L.saved.replace('{file}', file);
  });
  count();
})();
</script>
</body>
</html>
"""

"""Data schemas from code (S10), no AI. SQL tables from migrations (Flyway in version order, Liquibase XML/YAML), plain
schema files and entity classes (JPA, SQLAlchemy, Django, TypeORM, Prisma); NoSQL collections from Mongo `@Document`
classes, Mongoose schemas and Firestore (the paths of firestore.rules, `collection(…)` calls and the keys written to
them). Each field: name, type, primary key, reference (`table.column` or the entity it points to), nullability.

Each repo gets docs/data/<repo>.md, an AI draft for the `data` unit to complete, whose ER diagram and table list are a
generated block (`<!-- generated:schema repo=<repo> -->`, refreshed by genblocks like the reference pages)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from .common import DOCS, repo_dir
from . import docs, quickarch, radar

EXTS = {".sql", ".xml", ".yaml", ".yml", ".prisma", ".rules", ".java", ".kt", ".ts", ".js", ".mjs", ".py", ".dart"}
TEST_DIRS = {"test", "tests", "__tests__", "e2e", "spec", "testFixtures", "androidTest"}
MAX_BYTES = 2_000_000
SQL_FIRST = ("flyway", "liquibase", "sql")             # a table found by a migration wins over the same one in a class


def _files(repo: Path) -> list[tuple[str, Path]]:
    out = []
    for rel in radar.entries(repo):
        p = repo / rel
        parts = rel.split("/")
        if p.suffix.lower() in EXTS and not TEST_DIRS & set(parts[:-1]) and p.is_file():
            try:
                if p.stat().st_size <= MAX_BYTES:
                    out.append((rel, p))
            except OSError:
                continue
    return out


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _line(text: str, at: int) -> int:
    return text.count("\n", 0, at) + 1


def _f(name: str, type_: str = "", pk: bool = False, ref: str | None = None, null: bool | None = None) -> dict:
    return {"name": name, "type": type_, "pk": pk, "ref": ref, "null": null}


def _entity(name: str, kind: str, via: str, source: str, fields: list[dict], **extra) -> dict:
    return {"name": name, "kind": kind, "via": via, "source": source, "fields": fields, **extra}


# ---------- SQL ----------
IDENT = r"[`\"\[]?([\w.]+)[`\"\]]?"


def _unq(s: str) -> str:
    return s.strip().strip('`"[]').split(".")[-1]


def _split_top(body: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    return [p.strip() for p in [*parts, cur] if p.strip()]


def _closing(text: str, start: int) -> int:
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return len(text)


def sql(text: str, rel: str, repo: str, tables: dict, via: str = "sql") -> None:
    """Apply one SQL file to `tables` (name → entity): CREATE TABLE, ALTER TABLE ADD COLUMN / FOREIGN KEY, DROP TABLE."""
    text = re.sub(r"--[^\n]*|/\*.*?\*/", lambda m: " " * len(m.group()), text, flags=re.S)
    for m in re.finditer(rf"create\s+table\s+(?:if\s+not\s+exists\s+)?{IDENT}\s*\(", text, re.I):
        name = _unq(m.group(1)).lower()
        body = text[m.end():_closing(text, m.end() - 1)]
        fields, pks = [], set()
        for part in _split_top(body):
            low = part.lower()
            if fk := re.match(rf"(?:constraint\s+\w+\s+)?foreign\s+key\s*\(([^)]*)\)\s*references\s+{IDENT}\s*\(([^)]*)\)", part, re.I):
                for col in fk.group(1).split(","):
                    for f in fields:
                        if f["name"] == _unq(col).lower():
                            f["ref"] = f"{_unq(fk.group(2)).lower()}.{_unq(fk.group(3)).lower()}"
            elif pk := re.match(r"(?:constraint\s+\w+\s+)?primary\s+key\s*\(([^)]*)\)", part, re.I):
                pks |= {_unq(c).lower() for c in pk.group(1).split(",")}
            elif low.startswith(("constraint", "unique", "index", "key ", "check")):
                continue
            elif col := re.match(rf"{IDENT}\s+([\w ]+?(?:\([^)]*\))?)(?=\s|$)", part):
                ref = re.search(rf"references\s+{IDENT}\s*\(([^)]*)\)", part, re.I)
                fields.append(_f(_unq(col.group(1)).lower(), col.group(2).strip().upper(), "primary key" in low,
                                 f"{_unq(ref.group(1)).lower()}.{_unq(ref.group(2)).lower()}" if ref else None,
                                 False if "not null" in low or "primary key" in low else True))
        for f in fields:
            f["pk"] = f["pk"] or f["name"] in pks
            if f["pk"]:
                f["null"] = False
        tables[name] = _entity(name, "table", via, f"{repo}:{rel}#L{_line(text, m.start())}", fields)
    for m in re.finditer(rf"alter\s+table\s+(?:only\s+)?{IDENT}\s+(.*?);", text, re.I | re.S):
        t = tables.get(_unq(m.group(1)).lower())
        if not t:
            continue
        rest = m.group(2)
        if fk := re.search(rf"foreign\s+key\s*\(([^)]*)\)\s*references\s+{IDENT}\s*\(([^)]*)\)", rest, re.I):
            for f in t["fields"]:
                if f["name"] == _unq(fk.group(1)).lower():
                    f["ref"] = f"{_unq(fk.group(2)).lower()}.{_unq(fk.group(3)).lower()}"
        elif add := re.match(rf"\s*add\s+(?:column\s+)?(?:if\s+not\s+exists\s+)?{IDENT}\s+([\w ]+?(?:\([^)]*\))?)(?=\s|,|$)", rest, re.I):
            if add.group(1).lower() not in ("constraint", "primary", "foreign", "unique"):
                t["fields"].append(_f(_unq(add.group(1)).lower(), add.group(2).strip().upper(), null="not null" not in rest.lower()))
    for m in re.finditer(rf"drop\s+table\s+(?:if\s+exists\s+)?{IDENT}", text, re.I):
        tables.pop(_unq(m.group(1)).lower(), None)


def _flyway_key(rel: str) -> tuple:
    m = re.match(r"V([\d._]+)__", Path(rel).name)
    return tuple(int(x) for x in re.split(r"[._]", m.group(1)) if x.isdigit()) if m else (0,)


# ---------- Liquibase ----------
def _lb_column(name: str, type_: str, cons: dict) -> dict:
    ref = cons.get("references") or ""
    m = re.match(r"(\w+)\s*\((\w+)\)", ref)
    return _f(name.lower(), (type_ or "").upper(), str(cons.get("primaryKey", "")).lower() == "true",
              f"{m.group(1).lower()}.{m.group(2).lower()}" if m else None,
              None if "nullable" not in cons else str(cons["nullable"]).lower() == "true")


def liquibase_xml(text: str, rel: str, repo: str, tables: dict) -> None:
    root = ET.fromstring(text)
    strip = lambda el: el.tag.split("}")[-1]  # noqa: E731
    for el in root.iter():
        if strip(el) == "createTable":
            fields = []
            for col in el:
                if strip(col) != "column":
                    continue
                cons = next((dict(c.attrib) for c in col if strip(c) == "constraints"), {})
                fields.append(_lb_column(col.get("name", ""), col.get("type", ""), cons))
            name = el.get("tableName", "").lower()
            tables[name] = _entity(name, "table", "liquibase", f"{repo}:{rel}", fields)
        elif strip(el) == "addForeignKeyConstraint":
            t = tables.get(el.get("baseTableName", "").lower())
            for f in t["fields"] if t else []:
                if f["name"] == el.get("baseColumnNames", "").lower():
                    f["ref"] = f"{el.get('referencedTableName', '').lower()}.{el.get('referencedColumnNames', '').lower()}"


def liquibase_yaml(text: str, rel: str, repo: str, tables: dict) -> None:
    data = yaml.safe_load(text) or {}
    for item in data.get("databaseChangeLog") or []:
        for change in ((item or {}).get("changeSet") or {}).get("changes") or []:
            if ct := (change or {}).get("createTable"):
                fields = [_lb_column(c["column"].get("name", ""), c["column"].get("type", ""), c["column"].get("constraints") or {})
                          for c in ct.get("columns") or [] if isinstance(c, dict) and "column" in c]
                name = str(ct.get("tableName", "")).lower()
                tables[name] = _entity(name, "table", "liquibase", f"{repo}:{rel}", fields)


# ---------- entity classes ----------
CLASS = re.compile(r"\bclass\s+(\w+)")
JAVA_FIELD = re.compile(r"^\s*(?:private|protected|public)?\s*(?:final\s+)?([\w.<>,? \[\]]+?)\s+(\w+)\s*(?:=[^;]*)?;", re.M)
KOTLIN_FIELD = re.compile(r"^\s*(?:val|var)\s+(\w+)\s*:\s*([\w.<>?, ]+)", re.M)


def _annotations_before(text: str, at: int) -> str:
    """The annotation lines right above a declaration."""
    lines = text[:at].rstrip("\n").split("\n")
    out = []
    for line in reversed(lines):
        s = line.strip()
        if s.startswith("@") or (out and s.endswith(",")):
            out.append(s)
        elif s:
            break
    return " ".join(reversed(out))


def jpa(text: str, rel: str, repo: str) -> list[dict]:
    out = []
    for doc, kind, via in ((r"@Entity\b", "table", "jpa"), (r"@Document\b", "collection", "mongo")):
        for m in re.finditer(doc + r"[^\n]*\n(?:\s*@[^\n]*\n)*\s*(?:public\s+|data\s+|open\s+)*class\s+(\w+)", text):
            cls = m.group(1)
            head = text[m.start():m.end()]
            named = re.search(r"@(?:Table|Document)\s*\(\s*(?:name\s*=\s*|collection\s*=\s*|value\s*=\s*)?\"(\w+)\"", head)
            start = text.find("{", m.end())
            end = len(text) if start < 0 else start + _brace_end(text[start:])
            body = text[start + 1:end] if start >= 0 else ""
            fields = []
            for fm in JAVA_FIELD.finditer(body):
                type_, name = fm.group(1).strip(), fm.group(2)
                if re.search(r"\b(static|return|import|package)\b", type_) or "(" in type_:
                    continue
                ann = _annotations_before(body, fm.start())
                if "@Transient" in ann:
                    continue
                col = re.search(r"@(?:Column|JoinColumn|Field)\s*\(\s*(?:name\s*=\s*)?\"(\w+)\"", ann)
                rel_ = re.search(r"@(ManyToOne|OneToOne|ManyToMany|OneToMany|DBRef|DocumentReference)", ann)
                target = re.sub(r".*<\s*([\w.]+)\s*>.*", r"\1", type_) if rel_ else None
                if rel_ and rel_.group(1) in ("OneToMany", "ManyToMany") and not col:
                    continue                                      # the other side or a join table holds the key
                fields.append(_f(col.group(1) if col else _snake(name) if kind == "table" and rel_ else name,
                                 type_.split(".")[-1], "@Id" in ann, target, None))
            for fm in KOTLIN_FIELD.finditer(body):
                ann = _annotations_before(body, fm.start())
                fields.append(_f(fm.group(1), fm.group(2).strip().rstrip("?"), "@Id" in ann, None, fm.group(2).strip().endswith("?")))
            name = named.group(1) if named else cls
            out.append(_entity(name, kind, via, f"{repo}:{rel}#L{_line(text, m.start())}", fields))
    return out


def _brace_end(text: str) -> int:
    depth = 0
    for i, ch in enumerate(text):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(text)


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower() + "_id"


def prisma(text: str, rel: str, repo: str) -> list[dict]:
    out = []
    for m in re.finditer(r"^model\s+(\w+)\s*\{(.*?)^\}", text, re.M | re.S):
        fields = []
        lines = [l.strip() for l in m.group(2).splitlines() if l.strip() and not l.strip().startswith(("//", "@@"))]
        refs = {}
        for l in lines:
            if r := re.search(r"@relation\(\s*fields:\s*\[(\w+)\]\s*,\s*references:\s*\[(\w+)\]", l):
                refs[r.group(1)] = f"{l.split()[1].rstrip('?[]')}.{r.group(2)}"
        for l in lines:
            parts = l.split()
            if len(parts) < 2 or "@relation" in l or parts[1].rstrip("?").endswith("[]"):
                continue
            fields.append(_f(parts[0], parts[1].rstrip("?"), "@id" in l, refs.get(parts[0]), parts[1].endswith("?")))
        out.append(_entity(m.group(1), "table", "prisma", f"{repo}:{rel}#L{_line(text, m.start())}", fields))
    return out


def sqlalchemy(text: str, rel: str, repo: str) -> list[dict]:
    out = []
    for m in re.finditer(r"^class\s+(\w+)\(([^)]*)\):\s*\n((?:[ \t]+.*\n?|\s*\n)*)", text, re.M):
        body = m.group(3)
        table = re.search(r"__tablename__\s*=\s*['\"](\w+)['\"]", body)
        if table:
            fields = []
            for c in re.finditer(r"^\s+(\w+)\s*(?::\s*Mapped\[([^\]]+)\])?\s*=\s*(?:Column|mapped_column)\((.*)\)\s*$", body, re.M):
                args = c.group(3)
                fk = re.search(r"ForeignKey\(\s*['\"]([\w.]+)['\"]", args)
                type_ = c.group(2) or (re.match(r"\s*(\w+)", args).group(1) if re.match(r"\s*(\w+)", args) else "")
                fields.append(_f(c.group(1), type_.replace("Optional[", "").rstrip("]"), "primary_key=True" in args,
                                 fk.group(1) if fk else None, None))
            out.append(_entity(table.group(1), "table", "sqlalchemy", f"{repo}:{rel}#L{_line(text, m.start())}", fields))
        elif "models.Model" in m.group(2):
            fields = []
            for c in re.finditer(r"^\s+(\w+)\s*=\s*models\.(\w+)\((.*)\)\s*$", body, re.M):
                ref = re.match(r"\s*['\"]?([\w.]+)['\"]?", c.group(3)) if c.group(2) in ("ForeignKey", "OneToOneField") else None
                fields.append(_f(c.group(1), c.group(2), "primary_key=True" in c.group(3), ref.group(1) if ref else None,
                                 "null=True" in c.group(3)))
            out.append(_entity(m.group(1), "table", "django", f"{repo}:{rel}#L{_line(text, m.start())}", fields))
    return out


def typeorm(text: str, rel: str, repo: str) -> list[dict]:
    out = []
    for m in re.finditer(r"@Entity\(\s*(?:['\"](\w+)['\"])?[^)]*\)\s*(?:export\s+)?class\s+(\w+)", text):
        start = text.find("{", m.end())
        body = text[start + 1:start + _brace_end(text[start:])]
        fields = []
        for c in re.finditer(r"((?:@\w+\((?:[^()]|\([^()]*\))*\)\s*)+)(\w+)[!?]?\s*:\s*([\w\[\]<>| ]+);", body):
            ann = c.group(1)
            if "@OneToMany" in ann or "@ManyToMany" in ann:
                continue
            target = re.search(r"\(\)\s*=>\s*(\w+)", ann)
            fields.append(_f(c.group(2), c.group(3).strip(), "Primary" in ann, target.group(1) if target else None, None))
        out.append(_entity(m.group(1) or m.group(2), "table", "typeorm", f"{repo}:{rel}#L{_line(text, m.start())}", fields))
    return out


def mongoose(text: str, rel: str, repo: str) -> list[dict]:
    out = []
    schemas = {}
    for m in re.finditer(r"(?:const|let|var)\s+(\w+)\s*=\s*new\s+(?:mongoose\.)?Schema\(\s*\{", text):
        start = m.end() - 1
        body = text[start + 1:start + _brace_end(text[start:])]
        fields, depth, i = [], 0, 0
        for f in re.finditer(r"(?m)^\s*(\w+)\s*:\s*(.+?),?\s*$", body):
            if body[:f.start()].count("{") - body[:f.start()].count("}") != 0:
                continue                                          # a key inside a nested option object
            spec = f.group(2)
            type_ = re.search(r"type\s*:\s*([\w.\[\]]+)", spec)
            ref = re.search(r"ref\s*:\s*['\"](\w+)['\"]", spec)
            plain = re.match(r"\[?\s*([\w.]+)", spec)
            fields.append(_f(f.group(1), (type_.group(1) if type_ else plain.group(1) if plain else "").split(".")[-1],
                             False, ref.group(1) if ref else None, None))
        schemas[m.group(1)] = (fields, _line(text, m.start()))
    for m in re.finditer(r"model\(\s*['\"](\w+)['\"]\s*,\s*(\w+)", text):
        if m.group(2) in schemas:
            fields, line = schemas[m.group(2)]
            out.append(_entity(m.group(1), "collection", "mongoose", f"{repo}:{rel}#L{line}", fields))
    return out


# ---------- Firestore ----------
def firestore_rules(text: str, rel: str, repo: str) -> list[dict]:
    out, stack, depth = [], [], 0
    for i, line in enumerate(text.splitlines(), 1):
        code = re.sub(r"//.*$", "", line)
        m = re.search(r"match\s+(/\S+?)\s*\{(?!\w)", code)              # the path's own {wildcards} are kept
        if m:
            path = m.group(1)
            stack.append((path, depth))
            parts = [p for p, _ in stack if not p.startswith("/databases/")]
            full = "/".join(seg for p in parts for seg in p.strip("/").split("/"))
            segs = full.split("/")
            if full and len(segs) % 2 == 0 and segs[-1].startswith("{") and not segs[0].startswith("{"):
                coll = "/".join(segs[:-1])
                parent = "/".join(segs[:-3]) if len(segs) > 2 else None
                out.append(_entity(coll, "collection", "firestore", f"{repo}:{rel}#L{i}", [], parent=parent))
        depth += code.count("{") - code.count("}")
        while stack and depth <= stack[-1][1]:
            stack.pop()
    return out


FS_COLLECTION = re.compile(r"collection\(\s*(?:\w+\s*,\s*)?((?:['\"][\w-]+['\"]|\w+)(?:\s*,\s*(?:['\"][\w-]+['\"]|\w+))*)\s*\)")
KEY = re.compile(r"(?:^|[,{])\s*(['\"]?\w+['\"]?)\s*:")   # the keys of an object literal
FS_WRITE = re.compile(r"\.(?:add|set|update)\(\s*\{|(?:addDoc|setDoc|updateDoc)\([^{]*\{")


def _segments(args: str) -> list[str]:
    return [a.strip().strip("'\"") for a in args.split(",")]


def firestore_code(text: str, rel: str, repo: str) -> list[dict]:
    if "firestore" not in text.lower() and "FirebaseFirestore" not in text:
        return []
    out = {}
    for m in FS_COLLECTION.finditer(text):
        segs = _segments(m.group(1))
        literal = [s for s in segs]
        if not re.fullmatch(r"[\w-]+", literal[0]) or re.search(r"\(\s*\w+\s*\)", m.group(0)) and len(segs) == 1 \
                and not re.search(r"['\"]", m.group(1)):
            continue
        chain = text[max(0, text.rfind("\n", 0, m.start())):m.start()]
        prior = [s for c in re.findall(r"collection\(\s*['\"]([\w-]+)['\"]\s*\)", chain) for s in (c,)]
        path_parts = prior + [literal[0]] + literal[1:]
        names = [p for k, p in enumerate(path_parts) if k % 2 == 0]
        if not all(re.fullmatch(r"[\w-]+", n) for n in names):
            continue
        coll = "/{id}/".join(names) if len(names) > 1 else names[0]
        coll = _rules_style(coll, names)
        stmt_end = text.find(";", m.end())
        stmt = text[text.rfind("\n", 0, m.start()) + 1:stmt_end if stmt_end > 0 else len(text)]   # addDoc(collection(…), {…})
        fields = []
        w = FS_WRITE.search(stmt)
        if not w:
            var = re.search(r"(?:final|const|let|var)\s+(\w+)\s*=\s*[^;]*$", text[max(0, text.rfind("\n", 0, m.start())):m.start()])
            if var:
                w2 = re.search(rf"\b{re.escape(var.group(1))}\.(?:add|set|update)\(\s*\{{", text[m.end():])
                if w2:
                    stmt = text[m.end() + w2.start():]
                    w = FS_WRITE.search(stmt)
        if w:
            brace = stmt.find("{", w.start())
            obj = stmt[brace + 1:brace + _brace_end(stmt[brace:])]
            fields = [_f(k.strip("'\"")) for k in re.findall(KEY, obj)]
        e = out.setdefault(coll, _entity(coll, "collection", "firestore", f"{repo}:{rel}#L{_line(text, m.start())}", [],
                                         parent=_parent(coll)))
        e["fields"] += [f for f in fields if f["name"] not in {x["name"] for x in e["fields"]}]
    for m in re.finditer(r"doc\(\s*\w+\s*,\s*['\"]([\w-]+)['\"]\s*,[^)]*\)\s*,\s*\{", text):
        start = m.end() - 1
        obj = text[start + 1:start + _brace_end(text[start:])]
        e = out.setdefault(m.group(1), _entity(m.group(1), "collection", "firestore",
                                               f"{repo}:{rel}#L{_line(text, m.start())}", [], parent=None))
        e["fields"] += [_f(k.strip("'\"")) for k in re.findall(KEY, obj)
                        if k.strip("'\"") not in {x["name"] for x in e["fields"]}]
    return list(out.values())


def _rules_style(coll: str, names: list[str]) -> str:
    """users/{id}/orders as the rules name it: users/{userId}/orders (the singular + Id), so code and rules meet."""
    if len(names) == 1:
        return names[0]
    out = names[0]
    for prev, cur in zip(names, names[1:]):
        out += "/{" + (prev[:-1] if prev.endswith("s") else prev) + "Id}/" + cur
    return out


def _parent(coll: str) -> str | None:
    parts = coll.split("/")
    return "/".join(parts[:-2]) if len(parts) > 2 else None


# ---------- the scan ----------
def scan_repo(name: str, repo: Path) -> dict:
    tables: dict[str, dict] = {}
    classes: list[dict] = []
    docs_: dict[str, dict] = {}
    tools: list[str] = []
    files = _files(repo)
    flyway = sorted((f for f in files if f[1].suffix == ".sql" and re.match(r"V[\d._]+__", f[1].name)),
                    key=lambda f: _flyway_key(f[0]))
    other_sql = [f for f in files if f[1].suffix == ".sql" and f not in flyway]
    for rel, p in flyway:
        sql(_read(p), rel, name, tables, via="flyway")
    if flyway:
        tools.append("Flyway")
    for rel, p in files:
        if "changelog" in p.name.lower() or "/changelog" in rel:
            try:
                if p.suffix == ".xml":
                    liquibase_xml(_read(p), rel, name, tables)
                elif p.suffix in (".yaml", ".yml"):
                    liquibase_yaml(_read(p), rel, name, tables)
                else:
                    continue
                tools.append("Liquibase")
            except (ET.ParseError, yaml.YAMLError, AttributeError, TypeError):
                continue
    for rel, p in other_sql:
        found: dict[str, dict] = {}
        sql(_read(p), rel, name, found)
        for t, e in found.items():
            tables.setdefault(t, e)
        if found:
            tools.append("SQL schema files")
    for rel, p in files:
        text = _read(p)
        if p.suffix in (".java", ".kt") and ("@Entity" in text or "@Document" in text):
            classes += jpa(text, rel, name)
        elif p.suffix == ".prisma":
            classes += prisma(text, rel, name)
        elif p.suffix == ".py" and ("__tablename__" in text or "models.Model" in text):
            classes += sqlalchemy(text, rel, name)
        elif p.suffix in (".ts", ".js", ".mjs") and "@Entity(" in text:
            classes += typeorm(text, rel, name)
        elif p.suffix in (".ts", ".js", ".mjs") and "Schema(" in text and "mongoose" in text:
            classes += mongoose(text, rel, name)
        if p.suffix == ".rules" and "cloud.firestore" in text:
            for e in firestore_rules(text, rel, name):
                docs_.setdefault(e["name"], e)
        elif p.suffix in (".ts", ".js", ".mjs", ".dart", ".java", ".kt", ".py"):
            for e in firestore_code(text, rel, name):
                cur = docs_.setdefault(e["name"], e)
                if cur is not e:
                    cur["fields"] += [f for f in e["fields"] if f["name"] not in {x["name"] for x in cur["fields"]}]
    for e in classes:
        key = e["name"].lower()
        if e["kind"] == "table":
            if key not in tables:
                tables[key] = e
        else:
            docs_.setdefault(e["name"], e)
    for via, label in (("jpa", "JPA entities"), ("prisma", "Prisma"), ("sqlalchemy", "SQLAlchemy"), ("django", "Django models"),
                       ("typeorm", "TypeORM"), ("mongo", "Spring Data MongoDB"), ("mongoose", "Mongoose")):
        if any(e["via"] == via for e in classes):
            tools.append(label)
    if docs_ and any(e["via"] == "firestore" for e in docs_.values()):
        tools.append("Firestore")
    stores = []
    if tables:
        stores.append({"kind": "sql", "engines": _engines(name, "sql"), "entities": sorted(tables.values(), key=lambda e: e["name"])})
    if docs_:
        engines = sorted({"Firestore" if e["via"] == "firestore" else "MongoDB" for e in docs_.values()})
        stores.append({"kind": "document", "engines": engines, "entities": sorted(docs_.values(), key=lambda e: e["name"])})
    sources = sorted({e["source"].split("#", 1)[0] for s in stores for e in s["entities"]})
    return {"repo": name, "stores": stores, "tools": list(dict.fromkeys(tools)), "sources": sources}


def _engines(repo: str, kind: str) -> list[str]:
    try:
        dbs = quickarch.scan()["dbs"]
    except Exception:  # noqa: BLE001 — the engines are a label; the tables stand without them
        return []
    return sorted({d["label"] for d in dbs.values() if repo in d["users"]} - {"MongoDB", "Firestore", "Redis"})


def scan() -> dict[str, dict]:
    return {r: scan_repo(r, repo_dir(r)) for r in docs.repo_names() if repo_dir(r).is_dir()}


# ---------- rendering: the generated block and the page ----------
def _ident(name: str) -> str:
    parts = [p for p in name.split("/") if not p.startswith("{")]
    return re.sub(r"\W", "_", "_".join(parts)).upper() or "ENTITY"


def _mtype(t: str) -> str:
    return re.sub(r"\W+", "_", t).strip("_") or "any"


def block_body(result: dict) -> str:
    if not result["stores"]:
        return "_No tables or collections found by the static scan._"
    lines = []
    for s in result["stores"]:
        names = {e["name"].lower(): e for e in s["entities"]}
        lines += [f"**{'SQL' if s['kind'] == 'sql' else 'Documents'}**" + (f" ({', '.join(s['engines'])})" if s["engines"] else ""),
                  "", "```mermaid", "erDiagram"]
        rels = []
        for e in s["entities"]:
            attrs = [f"    {_mtype(f['type'] or 'field')} {_mtype(f['name'])}" + (" PK" if f["pk"] else " FK" if f["ref"] else "")
                     for f in e["fields"]]
            lines += [f"  {_ident(e['name'])} {{", *attrs, "  }"] if attrs else [f"  {_ident(e['name'])} {{", "    id id", "  }"]
            for f in e["fields"]:
                target = (f["ref"] or "").split(".")[0].lower()
                if target and target in names:
                    rels.append(f'  {_ident(names[target]["name"])} ||--o{{ {_ident(e["name"])} : "{f["name"]}"')
            if e.get("parent") and e["parent"].lower() in names:
                rels.append(f'  {_ident(e["parent"])} ||--o{{ {_ident(e["name"])} : "subcollection"')
        lines += list(dict.fromkeys(rels)) + ["```", "",
                                              f"| {'Table' if s['kind'] == 'sql' else 'Collection'} | Fields | Source |", "|---|---|---|"]
        for e in s["entities"]:
            fields = ", ".join(f"`{f['name']}`" + (" (PK)" if f["pk"] else "") + (f" → `{f['ref']}`" if f["ref"] else "")
                               for f in e["fields"]) or "—"
            lines.append(f"| `{e['name']}` | {fields} | `{e['source'].split(':', 1)[1]}` |")
        lines.append("")
    return "\n".join(lines).strip()


def render_block(name: str, repo: Path) -> tuple[str, list[str]]:
    r = scan_repo(name, repo)
    return block_body(r), r["sources"]


PAGE = "data/{repo}.md"


def page(result: dict) -> str:
    from . import genblocks
    repo = result["repo"]
    n = sum(len(s["entities"]) for s in result["stores"])
    engines = sorted({e for s in result["stores"] for e in s["engines"]}) or ["its stores"]
    fm = {"type": "data-model", "title": f"{repo} data model",
          "description": f"The tables and collections {repo} declares, read from its migrations, schema files and entity "
                         "classes by a static scan (no AI).", "tags": [repo, "data"], "x-sources": result["sources"],
          "x-generated": True, "x-owner": "ai"}
    try:
        users = [(k, d) for k, d in quickarch.scan()["dbs"].items() if repo in d["users"]]
    except Exception:  # noqa: BLE001
        users = []
    own = ["| Store | Writers | Readers |", "|---|---|---|"] + (
        [f"| {k} | {', '.join(sorted(d['users']))} | {', '.join(sorted(d['users']))} |" for k, d in users]
        or [f"| {', '.join(engines)} | {repo} | {repo} |"])
    body = "\n".join([
        f"# {repo} data model", "",
        f"> **TL;DR:** {n} tables or collections in {', '.join(engines)}, read from the code by a static scan (no AI). "
        "The diagram below is refreshed from the code; the data unit adds what each one means and who owns it.", "",
        "## Entities", "", genblocks.block("schema", repo, block_body(result)), "",
        "## Ownership", "", *own, "",
        "## Migrations", "",
        ("How the schema is created: " + ", ".join(result["tools"]) + "." if result["tools"] else "No migration tool found."),
        ""])
    return docs.join_fm(fm, body)


def write_pages(log=print) -> list[str]:
    """A page per repo with tables or collections, only where none exists yet (someone else's page is never touched;
    an existing page's block is refreshed by genblocks.refresh)."""
    written = []
    for name, result in scan().items():
        if not result["stores"]:
            continue
        f = DOCS / PAGE.format(repo=name)
        if f.exists():
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(page(result), encoding="utf-8", newline="\n")
        written.append(f"docs/{PAGE.format(repo=name)}")
        log(f"✔ {name}: {sum(len(s['entities']) for s in result['stores'])} tables/collections → docs/{PAGE.format(repo=name)}")
    return written

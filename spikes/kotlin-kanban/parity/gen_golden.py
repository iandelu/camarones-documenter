"""Golden outputs of the Python kanban core on seeded random inputs: the oracle the Kotlin port is checked against.

Run from the kit root: uv run --with pyyaml python spikes/kotlin-kanban/parity/gen_golden.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[3] / ".camarones"
sys.path.insert(0, str(KIT))

from lib.kanban import deps, items, merge, state  # noqa: E402

OUT = Path(__file__).resolve().parent / "golden.json"
R = random.Random(20261112)

TOKENS = ["a", "b", "ana", "WI", "x y", " ", "  ", ":", ",", "#", "{", "}", "[", "]", '"', "'", "&", "*", "!", "|", ">",
          "%", "@", "`", "-", "?", ".", "~", "\t", "\n", "\r", "é", "ñ", "🦐", "\u0085", " ", "﻿", " ",
          "\x01", "\x7f", "yes", "No", "on", "OFF", "null", "Null", "true", "False", "0", "007", "0x1F", "0b101", "0b_",
          "0o17", "1_000", "12:30", "1:30.5", "1e3", "1.5", "1.", ".5", "+.5", "1.5e+3", "1.5e3", ".inf", "-.Inf", ".NaN",
          "2026-10-24", "2026-1-5", "2026-13-45", "2026-10-24 10:12", "2026-10-24T10:12:00Z", "2026-10-24t10:12:00.5+02:00",
          "<<", "=", "\\", "/", "٣", "İ", "ß", "x-", "WI-7"]
SAFE = [t for t in TOKENS if t not in ("2026-13-45", "0b_")]
STATUSES = list(state.__dict__.get("STATUSES", ())) or ["Backlog", "Ready", "In Progress", "In Review", "Done", "Blocked"]


def text(pool=TOKENS, n=3) -> str:
    return "".join(R.choice(pool) for _ in range(R.randint(1, n)))


def outcome(fn):
    try:
        return {"ok": fn()}
    except Exception as e:  # the type is what the port must match
        return {"raises": type(e).__name__}


def dumps(v) -> str:
    return json.dumps(v)


def stamp() -> str:
    return f"2026-10-{R.randint(20, 24):02d}T{R.randint(9, 11):02d}:00:00Z {R.choice(['ana', 'luis', 'zoe'])}"


def card(uid=None, pool=TOKENS) -> dict:
    t = {}
    for _ in range(R.randint(0, 3)):
        t[R.choice(["status", "ordinal", "assignee", "created", text(pool, 1)])] = stamp() if R.random() < .7 else text(pool)
    return {"uid": uid or "".join(R.choice("0123456789abcdefghjkmnpqrstvwxyz") for _ in range(8)),
            "status": R.choice(STATUSES) if R.random() < .7 else text(pool), "ordinal": R.randint(-2000, 9000),
            "assignee": [text(pool) for _ in range(R.randint(0, 3))], "t": t}


def scalars():
    cases = list(TOKENS) + [text() for _ in range(4000)]
    return [{"in": s, "out": outcome(lambda s=s: state._scalar(s))} for s in cases]


def boards():
    out = []
    for _ in range(400):
        cards = {}
        for _ in range(R.randint(0, 6)):
            key = f"WI-{R.randint(1, 60)}" if R.random() < .8 else text(SAFE, 2)
            cards[key] = card(pool=SAFE)
        dumped = outcome(lambda: state.dump_board(cards))
        out.append({"cards": cards, "out": dumped})
    return out


def loads(dumped_boards):
    texts = [b["out"]["ok"] for b in dumped_boards if "ok" in b["out"]]
    mutated = []
    for t in texts[:300]:
        i = R.randint(0, len(t))
        mutated.append(t[:i] + text(TOKENS, 2) + t[i:])
    extra = ["", "version: 1\n", "version: true\ncards: {}\n", "version: 1.0\ncards:\n  WI-1: {uid: 1, status: 2, ordinal: '12'}\n",
             "version: 1\ncards:\n  WI-1: {uid: a, status: S, ordinal: 1_0, assignee: ana, t: {s: 2026-10-24}}\n",
             "version: 1\ncards:\n  WI-1: {uid: a, status: S, ordinal: 1, t: 5}\n", "version: 1\ncards: [1]\n"]
    return [{"in": t, "out": outcome(lambda t=t: dumps(state.load_board(t)))} for t in texts + mutated + extra]


def fm_value():
    r = R.random()
    if r < .45:
        return text(SAFE)
    if r < .55:
        return R.randint(-10**6, 10**6)
    if r < .6:
        return R.choice([True, False])
    if r < .65:
        return R.choice([1e20, 0.1, 1e-5, -0.0, 2.5, 1e16, 123456.789])
    if r < .7:
        return None
    if r < .9:
        return [text(SAFE) for _ in range(R.randint(0, 3))]
    return {text(SAFE, 1): text(SAFE) for _ in range(R.randint(0, 2))}


def item_dumps():
    out = []
    keys = list(items.FIELD_ORDER) + ["zzz", "x-uid", "x-sources", "notes"]
    for _ in range(400):
        fm = {"id": f"WI-{R.randint(1, 99)}"}
        for _ in range(R.randint(0, 7)):
            fm[R.choice(keys) if R.random() < .8 else text(SAFE, 2)] = fm_value()
        body = text(SAFE, 4)
        out.append({"fm": fm, "body": body, "out": outcome(lambda: items.serialize_item(items.Item(fm, body)))})
    return out


FM_LINES = ["id: WI-1", "id: 7", "id: ''", "title: Hello world", "created_date: 2026-10-24", "updated_date: 2026-10-24 10:12",
            "due_date: 2026-10-24T10:12:00.5Z", "due_date: 2026-13-45", "n: 0x1F", "n: 0o17", "n: 1_000", "n: 1e3", "n: 12:30",
            "flag: yes", "flag: Off", "x: ~", "x: =", "labels: [a, b]", "labels:\n  - a\n  - 2026-10-24", "deps: WI-2",
            "1: one", "yes: key", "null: k", "x-uid: 01jb7q3m", "t: 'quoted: x'", 'q: "a\\tb"', "bad: [", "a: b: c",
            "nested: {a: 1, b: [x, 2026-10-24 10:12]}", "s: |\n  line1\n  line2", "f: 1.5", "f: .inf", "big: 123456789012345678901234567890"]


def item_parses():
    out = []
    for _ in range(600):
        lines = R.sample(FM_LINES, R.randint(0, 5))
        if R.random() < .8:
            lines.insert(0, "id: WI-1")
        head = R.choice(["---\n", "﻿---\n", "---\r\n", "--\n"])
        body = R.choice(["", "\n", "\nbody\n", "body", "\n\nx\r\ny\n"])
        raw = head + "\n".join(lines) + ("\n" if lines else "") + R.choice(["---\n", "---", "--- \t\n", "----\n"]) + body
        out.append({"in": raw, "out": outcome(lambda raw=raw: dumps({"fm": items.parse_item(raw).fm,
                                                                     "body": items.parse_item(raw).body}))})
    return out


def titles():
    cases = [text(TOKENS + ["word ", "  ", "<", "?", "*", "a" * 30], 8) for _ in range(1500)]
    cases += ["word " * 60, "x" * 300, "🦐" * 70, "a" * 59 + "🦐" + "b", ""]
    return [{"in": s, "out": outcome(lambda s=s: items.file_name("WI-7", s))} for s in cases]


def merges():
    out = []
    for _ in range(500):
        base = {f"WI-{i}": card(pool=SAFE) for i in R.sample(range(1, 40), R.randint(0, 5))}
        for c in base.values():
            c["t"] = {k: v for k, v in c["t"].items() if R.random() < .5} if R.random() < .3 else {
                k: stamp() for k in c["t"]}

        def side():
            s = {}
            for k, c in base.items():
                r = R.random()
                if r < .15:
                    continue
                c = json.loads(json.dumps(c))
                if r < .45:
                    f = R.choice(["status", "ordinal", "assignee"])
                    c[f] = {"status": R.choice(STATUSES), "ordinal": R.randint(0, 5000),
                            "assignee": [R.choice(["ana", "luis", "zoe", "é"])]}[f]
                    if R.random() < .85:
                        c["t"][f] = stamp()
                s[k] = c
            for _ in range(R.randint(0, 2)):
                k = f"WI-{R.randint(1, 45)}"
                if k not in base:
                    c = card(pool=SAFE)
                    c["t"] = {k2: stamp() for k2 in c["t"]}
                    s[k] = c
            return s

        ours, theirs = side(), side()
        if R.random() < .05:
            k = next(iter(ours), None)
            if k:
                ours[k]["t"]["status"] = "2026-02-30T10:00:00Z bad"
        bt, ot, tt = (outcome(lambda b=b: state.dump_board(b)) for b in (base, ours, theirs))
        if not all("ok" in x for x in (bt, ot, tt)):
            continue
        texts = [bt["ok"], ot["ok"], tt["ok"]]
        out.append({"in": texts, "out": outcome(lambda: list(merge.merge_boards(*texts)))})
    return out


FILES = ["api:a.py", "api:b.py", "api:B.py", "api:c.py", "web:x.js", "web:y.js", "cam-docs:docs/p.md"]


def graphs():
    out = []
    for _ in range(400):
        n = R.randint(0, 9)
        ids = [f"WI-{i}" for i in R.sample(range(1, 30), n)]
        nodes = []
        for i in ids:
            node = {"id": i, "status": R.choice(STATUSES), "priority": R.choice(["P0", "P1", "P2", "P3", None, "P9"]),
                    "touches": R.sample(FILES, R.randint(0, 2)) if R.random() < .8 else [],
                    "repos": R.sample(["api", "web"], R.randint(0, 2)),
                    "deps": R.sample(ids + ["WI-404"], R.randint(0, 2)) if ids and R.random() < .5 else [],
                    "archived": R.random() < .1}
            if ids and R.random() < .15:
                node["parent"] = R.choice(ids).lower() if R.random() < .3 else R.choice(ids)
            nodes.append(node)
        groups = {f: R.choice(["g1", "g2"]) for f in FILES} if R.random() < .5 else None
        case = {"nodes": nodes, "groups": groups}
        for agent in (True, False):
            case[f"waves_{agent}"] = outcome(lambda agent=agent: deps.waves(nodes, agent=agent))
            waiting: list = []
            case[f"ready_{agent}"] = outcome(lambda agent=agent, waiting=waiting: [deps.ready(nodes, agent=agent, waiting=waiting), waiting])
        case["blocked"] = outcome(lambda: [deps.blocked_by(x, nodes, agent=True) for x in nodes])
        case["conflicts"] = outcome(lambda: [deps.conflicts(x, nodes, groups=groups) for x in nodes])
        case["containers"] = sorted(deps.containers(nodes))
        case["sccs"] = deps.sccs({x["id"]: x["deps"] for x in nodes})
        out.append(case)
    return out


def touches():
    pool = ["api", "web", ":", "/", "\\", ".", "..", "src", "A.java", " ", "", "//", "./", "İ", "ß"]
    cases = ["".join(R.choice(pool) for _ in range(R.randint(1, 7))) for _ in range(1500)]
    return [{"in": s, "fold": f, "out": outcome(lambda s=s, f=f: deps.norm_touch(s, fold=f))} for s in cases for f in (True, False)]


def overlaps():
    out = []
    for _ in range(800):
        a = R.sample(FILES + ["api:*", "*", "API:a.py", "web:X.js"], R.randint(0, 3))
        b = R.sample(FILES + ["api:*", "*", "API:a.py", "web:X.js"], R.randint(0, 3))
        for fold in (True, False):
            out.append({"a": a, "b": b, "fold": fold, "out": sorted(deps.overlap(set(a), set(b), fold=fold))})
    return out


def stamps():
    cases = ["2026-10-24T10:12:00Z ana", "2026-1-5T1:2:3Z x", "2026-10-24t10:12:00z", "2026-02-30T10:00:00Z",
             "2026-10-24T24:00:00Z", "2026-10-24T10:12:60Z", "٢٠٢٦-١٠-٢٤T10:12:00Z", "2026-10-24T10:12:00", "2026-10-24T10:12:00Zx",
             "0000-01-01T00:00:00Z", "2026-10-24 10:12:00Z"]
    cases += [f"{R.randint(1990, 2100)}-{R.randint(0, 13)}-{R.randint(0, 32)}T{R.randint(0, 25)}:{R.randint(0, 61)}:"
              f"{R.randint(0, 62)}Z" for _ in range(500)]
    return [{"in": s, "out": outcome(lambda s=s: state.stamp_time(s).isoformat())} for s in cases]


def orders():
    pool = ["WI-1", "WI-2", "WI-10", "WI-42", "WI-42~zz", "WI-42~ab", "AB-3", "x", "WI-", "-5", "a-b-7", "WI-7\n", "🦐-1", "￿-1"]
    return [{"in": (ids := R.sample(pool, R.randint(0, len(pool)))), "out": sorted(ids, key=state.id_key)} for _ in range(400)]


def places():
    out = []
    for _ in range(600):
        col = [(f"c{i}", R.choice([R.randint(-3, 3), R.randint(0, 5000)])) for i in range(R.randint(0, 5))]
        ids = [c[0] for c in col] + ["zz"]
        kw = R.choice([{}, {"before": R.choice(ids)}, {"after": R.choice(ids)}])
        out.append({"col": col, "kw": kw, "out": outcome(lambda col=col, kw=kw: state.place(col, **kw))})
    return out


def main():
    dumped = boards()
    golden = {"scalar": scalars(), "dump": dumped, "load": loads(dumped), "item_dump": item_dumps(),
              "item_parse": item_parses(), "title": titles(), "merge": merges(), "graph": graphs(), "touch": touches(),
              "overlap": overlaps(), "stamp": stamps(), "order": orders(), "place": places()}
    OUT.write_text(json.dumps(golden, ensure_ascii=True), encoding="utf-8")
    print({k: len(v) for k, v in golden.items()})


if __name__ == "__main__":
    main()

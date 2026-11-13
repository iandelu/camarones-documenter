"""What the kit reads from the code without AI: changed files, llms.txt, the code graph, git history, generated blocks
and pages, page freshness, the C4 draft, stack radar, dependencies, schemas, and a repo's stack."""
from __future__ import annotations

import argparse
import json
import sys

from lib.interfaces.cli.registry import CliContext, Command, command


@command("changes", "both", "analyze", es="Ficheros cambiados desde la última documentación",
         en="Files changed since the docs were last updated")
class Changes(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import docs
        print(json.dumps(docs.changes(), indent=2))
        return 0


@command("llms", "app", "analyze", es="Regenerar llms.txt", en="Regenerate llms.txt")
class Llms(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import docs
        print(f"wrote docs/llms.txt ({docs.llms()} entries)")
        return 0


@command("graph", "app", "analyze", es="Reconstruir el grafo de código", en="Rebuild the code graph")
class Graph(Command):
    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        cli.services.viewers.graph(rebuild=True)
        return 0


@command("history", "app", "analyze", es="Historia del proyecto desde git", en="The project's history from git")
class History(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--months", type=int, default=12)

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import history
        from lib.core.paths import rel_file
        print(f"✔ {rel_file(history.write(args.months))}: last {args.months} months of git history")
        return 0


def cmd_blocks(a) -> int:
    from lib import genblocks, pages
    from lib.core.paths import cli_cmd
    old = pages.layout() == "old"                                               # the new layout has no reference.md
    created = genblocks.write_reference() if old else []
    out = {"created": created, **genblocks.refresh(force=a.force)}
    if a.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    made = f"{len(out['created'])} reference page(s) created, " if old else ""
    print(f"✔ {made}{len(out['updated'])} page(s) refreshed")
    for e in out["edited"]:
        print(f"  · kept, edited by hand: {e}")
    for h in out["human"]:
        print(f"  · not touched, owned by a person: {h}")
    if out["edited"]:
        print(f"Fix the source in the repo, or `{cli_cmd()} blocks --force` to take the code's version.")
    return 0


@command("blocks", "app", "analyze", es="Datos leídos del código para los bloques generados",
         en="Facts read from the code for the generated blocks")
class Blocks(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--json", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_blocks(args)


def cmd_pages(a) -> int:
    """`pages` and its alias `diagrams`: the pages from the code for the project's layout (`pages.write`), then every
    block refreshed; `--adopt` (pages only) moves an old-layout project to the new pages."""
    from lib import genblocks, pages
    from lib.core.paths import cli_cmd
    if getattr(a, "adopt", False):
        out = pages.adopt(log=(lambda _: None) if a.json else print)
        if a.json:
            print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    layout = pages.layout()
    out = {"layout": layout, "written": pages.write(log=lambda _: None), **genblocks.refresh()}
    if a.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    print(f"✔ {len(out['written'])} page(s) written, {len(out['updated'])} page(s) refreshed")
    for w in out["written"]:
        print(f"  → {w}")
    for e in out["edited"]:
        print(f"  · kept, edited by hand: {e}")
    for h in out["human"]:
        print(f"  · not touched, owned by a person: {h}")
    if out["edited"]:
        print(f"Fix the source in the repo, or `{cli_cmd()} blocks --force` to take the code's version.")
    return 0


@command("pages", "app", "analyze", es="Páginas desde el código, sin IA: el inicio y una por repo",
         en="Pages from the code, no AI: the home and one per repo")
class Pages(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--adopt", action="store_true")
        parser.add_argument("--json", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_pages(args)


@command("diagrams", "cli")                                    # alias of `pages`: the Taller shows `pages`
class Diagrams(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--json", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_pages(args)


def cmd_fresh(a) -> int:
    from lib.core.paths import cli_cmd
    from lib.harness import freshness
    if a.ack:
        if not a.by:
            print("usage: fresh --ack PAGE… --by NAME", file=sys.stderr)
            return 2
        done = freshness.ack(a.ack, a.by)
        print(f"✔ today's code is now the reference for: {', '.join(done) or 'no known page'}")
        return 0 if done else 1
    if a.plan:
        u = freshness.refresh_unit()
        print(f"✔ unit {u['id']}: {u['notes']}")
        return 0
    states = freshness.states()
    rows = [{"path": p, **s} for p, s in sorted(states.items())]
    if a.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    old = [r for r in rows if r["state"] in freshness.OUT_OF_DATE]
    counts = {k: sum(1 for r in rows if r["state"] == k) for k in ("fresh", "suspect", "stale", "unverified")}
    print("  ".join(f"{n} {k}" for k, n in counts.items()) + f"  (agents: {freshness.policy()})")
    for r in old:
        print(f"  {r['state']:<8} {r['path']}  ← {', '.join(freshness.code_paths(r['missing'] + r['changed']))}")
    if old:
        print(f"Refresh them (`{cli_cmd()} fresh --plan` adds a unit) or, if they still hold, "
              f"`{cli_cmd()} fresh --ack <page> --by <name>`.")
    return 0


@command("fresh", "both", "analyze", es="Páginas cuyo código citado cambió", en="Pages whose cited code changed")
class Fresh(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--ack", nargs="+", default=[])
        parser.add_argument("--by", default="")
        parser.add_argument("--plan", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        return cmd_fresh(args)


@command("mark-documented", "app", "analyze", es="Marcar los commits actuales como documentados",
         en="Record the current commits as documented")
class MarkDocumented(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("repos", nargs="*")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import docs
        print("marked documented:", ", ".join(docs.mark_documented(args.repos)))
        return 0


@command("arch-draft", "app", "analyze", es="Borrador C4 desde el código, sin IA", en="C4 draft from the code, no AI")
class ArchDraft(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--save", action="store_true")
        parser.add_argument("--overwrite", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import pages, quickarch
        m = quickarch.draft()
        print((m["dir"] / "model.c4").read_text(encoding="utf-8"))
        if args.save:                                                   # the new layout has no first-look.md
            print("\n".join(quickarch.save(m, overwrite=args.overwrite, page=pages.layout() == "old")))
        return 0


@command("radar", "app", "analyze", es="Stack y herramientas que ya usan los repos",
         en="Stack and tools the repos already use")
class Radar(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--json", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import radar
        from lib.core.fsutil import load_json
        from lib.core.paths import ROOT
        page = radar.run(log=(lambda _: None) if args.json else print)
        if args.json:
            print(json.dumps(load_json(radar.CACHE_FILE, {}), indent=2, ensure_ascii=False))
        else:
            for name, r in load_json(radar.CACHE_FILE, {}).items():
                print(f"{name:<20} {r['stack']}")
                print(f"{'':<20} " + (", ".join(t["label"] for t in r["tools"]) or "-"))
            print(f"→ {page.relative_to(ROOT).as_posix()}")
        return 0


@command("inventory", "both", "analyze", es="Dependencias de cada repo y sus vulnerabilidades",
         en="Each repo's dependencies and their vulnerabilities")
class Inventory(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--cves", action="store_true")
        parser.add_argument("--latest", action="store_true")
        parser.add_argument("--fail-on", choices=["high", "critical"], default=None)

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import inventory
        from lib.core.paths import ROOT
        # --json keeps stdout for the JSON; the progress goes to stderr, where the desktop app reads it as it comes
        page = inventory.run(log=(lambda m: print(m, file=sys.stderr, flush=True)) if args.json else print,
                             cves=args.cves, latest=args.latest)
        data = inventory.load()
        if args.json:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"→ {page.relative_to(ROOT).as_posix()}")
        return inventory.exit_code(data, args.fail_on)


@command("bump", "app", "analyze", es="Actualizar una librería de un repo en una rama nueva, sin commit",
         en="Update one library of a repo on a new branch, not committed")
class Bump(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("repo")
        parser.add_argument("library")
        parser.add_argument("version")
        parser.add_argument("--ecosystem")
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--yes", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import bump
        try:
            if not args.yes:
                p = bump.public(bump.plan(args.repo, args.library, args.version, args.ecosystem))
                print(json.dumps(p, indent=2, ensure_ascii=False) if args.json else
                      f"{p['repo']}: {p['name']} {p['from']} → {p['to']} on a new branch {p['branch']}\n"
                      f"  {' '.join(p['argv']) if p['argv'] else 'the version is rewritten in ' + p['manifest']}"
                      f"{' (property ' + p['property'] + ')' if p.get('property') else ''}\n"
                      "  run again with --yes to do it (nothing is committed or pushed)")
                return 0
            r = bump.apply(args.repo, args.library, args.version, args.ecosystem,
                           log=(lambda m: print(m, file=sys.stderr)) if args.json else print)
        except (KeyError, ValueError, RuntimeError) as e:
            print(f"✖ {e.args[0] if isinstance(e, KeyError) else e}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0


@command("schemas", "app", "analyze", es="Tablas y colecciones de cada repo", en="Each repo's tables and collections")
class Schemas(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--json", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import genblocks, pages, schemas
        found = schemas.scan()
        if args.json:
            print(json.dumps(found, indent=2, ensure_ascii=False))
            return 0
        written = schemas.write_pages() if pages.layout() == "old" else pages.write()   # new: tables in the repo pages
        updated = genblocks.refresh()["updated"]
        for name, r in found.items():
            n = sum(len(s["entities"]) for s in r["stores"])
            print(f"{name:<20} {n} tables/collections" + (f" ({', '.join(r['tools'])})" if r["tools"] else ""))
        for f in written + [u for u in updated if u.startswith("docs/data/")]:
            print(f"→ {f}")
        return 0


@command("stack", "app", "machine", es="Corregir el stack de un repo", en="Fix a repo's stack")   # here: it uses radar
class Stack(Command):
    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("repo")
        parser.add_argument("text", nargs="?", default="")
        parser.add_argument("--reset", action="store_true")

    def run(self, args: argparse.Namespace, cli: CliContext) -> int:
        from lib import radar
        if not args.reset and not args.text:
            cli.parser.error("stack: give the stack text or --reset")
        try:
            radar.set_stack(args.repo, None if args.reset else args.text)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 2
        print(f"{args.repo}: " + ("stack reset to the detected one" if args.reset else args.text.strip()))
        return 0

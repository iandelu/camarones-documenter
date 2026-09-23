# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6", "rich>=13", "questionary>=2", "keyring>=25"]
# ///
"""🦐 Camarones Documenter — project documentation kit (wizard + CLI). No arguments opens the wizard.

  setup [--ci]              install tools, sync repos, wire Claude Code/Codex + git hooks (idempotent)
  sync                      clone/pull repos from workspace.yaml
  detect                    add repos found in this folder to workspace.yaml
  changes                   files changed per repo since docs were last updated
  mark-documented [repo..]  record current commits as documented
  status [--json]           trust report: confirmed / draft / needs-reconfirm / orphans / translations
  check [--strict]          CI gate for docs
  confirm FILE.. --by NAME  mark pages as human-confirmed
  translated FILE..         stamp docs/i18n/<lang>/… pages as translations of the current canonical page
  llms                      regenerate docs/llms.txt
  graph                     rebuild the cross-repo code graph (.camarones/.cache/graph/graph.html)
  arch | arch-validate      live C4 editor | validate the C4 model
  portal | up [--port] [--no-docker] | down   build the static portal | serve it (Docker, or plain Python) | stop it
  ci [gitlab|github]        install the umbrella CI pipeline
  plan [sync|next|start|note|done|block|drop|add] …   session work plan (docs/.work/plan.yaml)
  plan note UNIT "text"     save a progress checkpoint of a unit (a closed session resumes from it)
  checkpoint ["message"]    commit docs progress locally in the umbrella repo (never pushes)
  feedback FILE "text" --by NAME   record a human review comment (applied by the review-fixes unit)
  version                   kit and pinned tool versions
  prompt UNIT [--lang es|en] [--unattended]      prompt for an agent session (UNIT may be 'update')
  arch-draft [--save]       quick static architecture scan → C4 draft (first look, no AI)
  doctor                    check prerequisites and tool versions
"""
from __future__ import annotations

import argparse, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Kit unzipped into its own subfolder (camarones-documenter/) inside the project → offer to install one level up.
if HERE.parent.name.lower().startswith(("camarones-documenter", "camarones-kit")) and not (HERE.parent / "docs").exists() \
        and len(sys.argv) == 1 and not os.environ.get("CAMARONES_ROOT"):
    from lib.wizard import install_from_kit_folder
    from lib.upgrade import relaunch
    if install_from_kit_folder(HERE.parent):
        target = HERE.parent.parent / ".camarones" / "camarones.py"
        if target.exists():
            os.chdir(HERE.parent.parent)               # the kit subfolder (old cwd) is gone
            relaunch(target)
    sys.exit(0)

from lib import docs, env, plan                     # noqa: E402
from lib.common import VERSIONS, cli_cmd, ROOT, CACHE   # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    if len(sys.argv) == 1:
        from lib.wizard import W, offer_upgrade
        if offer_upgrade():                        # newer kit found next to the project → installed → restart it
            from lib.upgrade import relaunch
            relaunch(ROOT / ".camarones" / "camarones.py")
        W().run()
        return 0
    p = argparse.ArgumentParser(prog=cli_cmd(), description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("help")
    s = sp.add_parser("setup"); s.add_argument("--ci", action="store_true")
    sp.add_parser("init")
    for c in ("sync", "detect", "changes", "llms", "graph", "arch", "arch-validate", "portal", "down", "doctor", "wizard", "version"):
        sp.add_parser(c)
    m = sp.add_parser("mark-documented"); m.add_argument("repos", nargs="*")
    s = sp.add_parser("status"); s.add_argument("--json", action="store_true")
    k = sp.add_parser("check"); k.add_argument("--strict", action="store_true")
    c = sp.add_parser("confirm"); c.add_argument("files", nargs="+"); c.add_argument("--by", required=True)
    t = sp.add_parser("translated"); t.add_argument("files", nargs="+")
    u = sp.add_parser("up"); u.add_argument("--port", type=int, default=8080); u.add_argument("--no-docker", action="store_true")
    ci = sp.add_parser("ci"); ci.add_argument("forge", nargs="?", choices=["gitlab", "github"])
    pl = sp.add_parser("plan"); pl.add_argument("action", nargs="?", default="show",
                                                choices=["show", "sync", "next", "start", "note", "done", "block", "drop", "add"])
    pl.add_argument("unit", nargs="?"); pl.add_argument("title", nargs="?")
    pl.add_argument("--note"); pl.add_argument("--type", default="flow"); pl.add_argument("--deps", nargs="*")
    pl.add_argument("--json", action="store_true")
    cp = sp.add_parser("checkpoint"); cp.add_argument("message", nargs="?", default="progress")
    fb = sp.add_parser("feedback"); fb.add_argument("file"); fb.add_argument("text"); fb.add_argument("--by", default="")
    ad = sp.add_parser("arch-draft"); ad.add_argument("--save", action="store_true"); ad.add_argument("--overwrite", action="store_true")
    pr = sp.add_parser("prompt"); pr.add_argument("unit"); pr.add_argument("--lang", default="es")
    pr.add_argument("--unattended", action="store_true")
    a = p.parse_args()

    if a.cmd == "help":
        print(__doc__)
    elif a.cmd == "wizard":
        from lib.wizard import W
        W().run()
    elif a.cmd == "setup":
        env.init_templates()
        env.setup(ci=a.ci)
        if not a.ci:
            plan.sync()
            plan.set_status("setup", "done", "cli setup")
    elif a.cmd == "init":
        env.init_templates()
        plan.sync()
    elif a.cmd == "sync":
        docs.sync_repos()
    elif a.cmd == "detect":
        ws = docs.workspace()
        known = set(docs.repo_names())
        new = [r for r in docs.detect_repos() if r["name"] not in known]
        ws["repos"] += new
        docs.save_workspace(ws)
        print(f"added {len(new)} repo(s): {', '.join(r['name'] for r in new) or '—'}")
    elif a.cmd == "changes":
        print(json.dumps(docs.changes(), indent=2))
    elif a.cmd == "mark-documented":
        print("marked documented:", ", ".join(docs.mark_documented(a.repos)))
    elif a.cmd == "status":
        rows = docs.collect()
        if a.json:
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        else:
            icon = {"confirmed": "✅", "needs-reconfirm": "⚠️ ", "draft": "🤖"}
            for r in rows:
                extra = ([f"ORPHAN({len(r['orphan_sources'])})"] if r["orphan_sources"] else []) + \
                        [f"{k}:{v}" for k, v in r["i18n"].items() if v != "current"]
                print(f"{icon[r['trust']]} {r['path']:<60} {' '.join(extra)}")
            s = docs.summary(rows)
            print(f"\n{s['total']} docs — confirmed {s['confirmed']}, needs-reconfirm {s['needs-reconfirm']}, "
                  f"draft {s['draft']}, orphans {s['orphans']}, untranslated {s['untranslated']}")
    elif a.cmd == "check":
        errors, warns = docs.check(a.strict)
        for w in warns:
            print("WARN ", w)
        for e in errors:
            print("ERROR", e)
        return 1 if errors else 0
    elif a.cmd == "confirm":
        for f in docs.confirm(a.files, a.by):
            print(f"confirmed {f} by {a.by}")
    elif a.cmd == "translated":
        for f in docs.translated(a.files):
            print("stamped", f)
    elif a.cmd == "llms":
        print(f"wrote docs/llms.txt ({docs.llms()} entries)")
    elif a.cmd == "graph":
        env.graph(rebuild=True)
    elif a.cmd == "arch":
        env.arch_start()
    elif a.cmd == "arch-validate":
        ok, msg = env.arch_validate()
        print(msg or ("✓ Valid" if ok else "invalid"))
        return 0 if ok else 1
    elif a.cmd == "portal":
        env.portal()
    elif a.cmd == "up":
        if not (CACHE / "site" / "index.html").exists():
            env.portal()
        (env.serve_local if a.no_docker else env.docker_up)(a.port)
    elif a.cmd == "down":
        env.docker_down()
    elif a.cmd == "ci":
        env.install_ci(a.forge)
    elif a.cmd == "doctor":
        for k, v in env.prerequisites().items():
            print(f"{'✔' if v['ok'] else ('✖' if v['need'] else '·')} {k:<7} {v.get('found', '')}  {'' if v['ok'] else v['hint']}")
            if v.get("note"):
                print(f"          {v['note']}")
        for tname in ("graphify", "likec4"):
            print(f"  {tname:<9} {env.tool_version(tname) or 'missing'} (pinned {VERSIONS[tname]})")
        print(f"  openwiki  {'ok' if env.openwiki_installed() else 'missing'} (pinned {VERSIONS['openwiki']})")
    elif a.cmd == "plan":
        return cmd_plan(a)
    elif a.cmd == "arch-draft":
        from lib import quickarch
        m = quickarch.draft()
        print((m["dir"] / "model.c4").read_text(encoding="utf-8"))
        if a.save:
            print("\n".join(quickarch.save(m, overwrite=a.overwrite)))
    elif a.cmd == "version":
        print(f"Camarones Documenter {VERSIONS['kit']} — " + ", ".join(f"{k} {v}" for k, v in VERSIONS.items() if k != "kit"))
    elif a.cmd == "checkpoint":
        print("✔ committed locally" if env.checkpoint_commit(a.message) else "nothing to commit")
    elif a.cmd == "feedback":
        docs.add_feedback(a.file, a.text, a.by or os.environ.get("USER", "human"))
        plan.ensure("review-fixes", "review-fixes")
        print(f"feedback recorded in {docs.FEEDBACK.relative_to(ROOT).as_posix()}; unit review-fixes is ready")
    elif a.cmd == "prompt":
        print(plan.prompt(a.unit, lang=a.lang, unattended=a.unattended))
    return 0


def cmd_plan(a) -> int:
    if a.action == "sync" or not plan.PLAN.exists():
        plan.sync()
    if a.action in ("show", "sync"):
        data = plan.load()
        print(json.dumps(data, indent=2, ensure_ascii=False) if a.json else plan.render(data))
    elif a.action == "next":
        ready = plan.available()
        if a.json:
            print(json.dumps(ready, indent=2, ensure_ascii=False))
        elif not ready:
            print("Plan complete 🦐 — use `prompt update` after code changes.")
        else:
            d, t = plan.progress()
            print(f"Progress {d}/{t}. Ready next:")
            for i, u in enumerate(ready[:6], 1):
                print(f"  {i}. {u['id']:<28} {u['title']}{'  [in progress]' if u['status'] == 'doing' else ''}"
                      f"{'  [wizard]' if u['runner'] == 'wizard' else ''}")
                if u["status"] == "doing" and plan.last_note(u["id"]):
                    print(f"       last checkpoint: {plan.last_note(u['id'])}")
    elif a.action == "note":
        if not a.unit or not (a.title or a.note):
            print('usage: plan note <unit> "what is done / what is next"'); return 2
        f = plan.note(a.unit, a.title or a.note)
        print(f"checkpoint saved → {f.relative_to(ROOT).as_posix()}")
    elif a.action in ("start", "done", "block", "drop"):
        if not a.unit:
            print("unit id required"); return 2
        status = {"start": "doing", "done": "done", "block": "blocked", "drop": "dropped"}[a.action]
        u = plan.set_status(a.unit, status, a.note)
        print(f"{u['id']} → {status}")
        if status != "doing" and env.checkpoint_commit(f"{u['id']} {status}"):
            print("✔ docs committed locally (checkpoint)")
    elif a.action == "add":
        if not a.unit or not a.title:
            print('usage: plan add <id> "<title>" [--type flow] [--deps a b]'); return 2
        u = plan.add(a.unit, a.title, a.type, a.deps)
        print(f"added {u['id']} ({u['type']}) deps={u['deps']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, KeyError, ValueError) as e:
        print(f"🦐✖ {e}", file=sys.stderr)
        sys.exit(1)

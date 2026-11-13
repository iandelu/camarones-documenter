"""The team's side of the docs: syncing with the team's remote, the online interview, and the KPIs with the questions
nobody found an answer to."""
from __future__ import annotations

import datetime as dt

from lib import docs, usage
from lib.app.portal_views import reviewer
from lib.core.paths import DOCS
from lib.interfaces.http.messages import Request, Response, json_response
from lib.interfaces.http.router import route


def kpis_miss(b: dict) -> dict:
    """A question nobody found an answer to: `question` adds it to the open questions for the next interview,
    `dismiss` just forgets it."""
    q, action = str(b.get("q") or ""), b.get("action")
    if q not in {m["q"] for m in usage.misses()}:
        raise KeyError(q)
    if action == "question":
        n = next(m["n"] for m in usage.misses() if m["q"] == q)
        f = DOCS / "interview" / "open-questions.md"
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("---\ntype: interview\ntitle: Open questions\ndescription: Questions agents could not answer "
                         "from the code; answer them in the next interview or inline.\n---\n# Open questions\n",
                         encoding="utf-8", newline="\n")
        text = f.read_text(encoding="utf-8")
        line = (f"- [ ] ({dt.date.today().isoformat()}, docs-gap) {q} — asked {n}× in the portal or by agents; "
                "no page answered it\n")
        f.write_text(text.rstrip("\n") + "\n" + line, encoding="utf-8", newline="\n")
    elif action != "dismiss":
        raise ValueError("action: question or dismiss")
    usage.forget(q)
    return {"misses": usage.misses()}


def api_interview(who: str = "") -> dict:
    """The team questionnaire for the portal's Interview view: the questions, the labels of the offline form (both
    languages), who answered and, with `who`, that person's own answers to edit them."""
    from lib import questionnaire
    try:
        data = questionnaire.load()
    except ValueError as e:
        return {"available": False, "reason": str(e), "mode": docs.interview_mode(), "chosen": docs.interview_mode_chosen()}
    mine = next((r for n, r in questionnaire.responses().items() if who and n.strip().lower() == who.strip().lower()), None)
    return {"available": True, "mode": docs.interview_mode(), "chosen": docs.interview_mode_chosen(), "id": data["id"], "title": data.get("title") or "",
            "intro": data.get("intro") or "", "questions": data["questions"], "labels": questionnaire.LABELS,
            "status": questionnaire.status(), "user": reviewer(), "mine": mine}


@route("GET", "/api/sync")
def get_sync(req: Request) -> Response:
    return json_response(req.services.share.sync_status(fetch=req.query.get("fetch") == "1"))


@route("POST", "/api/sync/share")
def post_share(req: Request) -> Response:
    # the team action: checkpoint, pull the team's work, push
    return json_response({"result": req.services.share.share(log=lambda _: None), "sync": req.services.share.sync_status()})


@route("GET", "/api/interview")
def get_interview(req: Request) -> Response:
    return json_response(api_interview(req.query.get("who", "")))


@route("POST", "/api/interview/answer")
def post_interview_answer(req: Request) -> Response:
    from lib import questionnaire
    questionnaire.answer(req.body)
    return json_response(questionnaire.status())


@route("GET", "/api/kpis")
def get_kpis(req: Request) -> Response:
    from lib.harness import kpis
    return json_response(kpis.dashboard())


@route("POST", "/api/kpis/miss")
def post_kpis_miss(req: Request) -> Response:
    try:
        return json_response(kpis_miss(req.body))
    except KeyError as e:
        return json_response({"error": f"not in the list: {e}"}, 404)

"""The C4 model in the portal: a view's elements and relations, and the edits of its panel (fields, confirm, add or
remove a relation, remove an element)."""
from __future__ import annotations

from lib.interfaces.http.messages import Request, Response, json_response
from lib.interfaces.http.router import route


def api_c4_view(view: str, static: bool = False) -> dict:
    """A C4 view's elements for the portal's panel: fields, draft/confirmed, and the relations in and out of each.
    `static`: the server serves the read-only export, where nothing is edited."""
    from lib import c4edit
    idx = c4edit.index()
    shown = c4edit.view_elements(view, idx)
    keep = ("fqn", "kind", "title", "technology", "description", "tags", "draft", "confirmed", "confirmedBy",
            "confirmedAt", "file", "line")
    rel = lambda r: {k: r[k] for k in ("from", "to", "label", "kind")}  # noqa: E731
    return {"view": view, "kinds": idx["kinds"], "relKinds": idx["relKinds"], "editable": not static,
            "all": [{"fqn": f, "title": e["title"]} for f, e in idx["elements"].items()],
            "elements": [{**{k: idx["elements"][f][k] for k in keep},
                          "out": [rel(r) for r in idx["relations"] if r["from"] == f],
                          "in": [rel(r) for r in idx["relations"] if r["to"] == f]} for f in shown]}


def c4_change(path: str, b: dict, by: str) -> dict:
    from lib import c4edit
    if path == "element":
        changes = {k: b[k] for k in c4edit.EDITABLE if k in b}
        return c4edit.edit(b["fqn"], **changes)
    if path == "confirm":
        return {"confirmed": c4edit.confirm_view(b["view"], by) if b.get("view") else c4edit.confirm(b["fqns"], by)}
    if path == "relation" and b.get("action") == "add":
        return c4edit.add_relation(b["from"], b["to"], str(b.get("label") or ""), b.get("kind") or None)
    if path == "remove":
        return c4edit.remove_element(b["fqn"])
    if path == "relation" and b.get("action") == "remove":
        return c4edit.remove_relation(b["from"], b["to"], str(b.get("label") or ""))
    raise ValueError(f"unknown C4 change {path!r}")


@route("GET", "/api/c4/view")
def get_c4_view(req: Request) -> Response:
    return json_response(api_c4_view(req.query.get("id", ""), req.static))


@route("POST", "/api/c4/{change:element|confirm|relation|remove}")
def post_c4_change(req: Request) -> Response:
    try:
        return json_response(c4_change(req.params["change"], req.body, req.by))
    except KeyError as e:
        return json_response({"error": f"not in the model: {e}"}, 404)

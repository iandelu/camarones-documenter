"""Board items: Backlog.md (v1.55.3) task files, read and written byte-compatibly."""
from __future__ import annotations

from pathlib import Path

import pytest

FIX = Path(__file__).resolve().parent / "fixtures" / "backlogmd"
WI42 = FIX / "wi-42 - Idempotent PaymentRequested handling.md"


def wi42() -> str:
    return WI42.read_bytes().decode("utf-8")


def test_round_trip_keeps_backlogmd_bytes(kit):
    from lib.kanban.items import parse_item, serialize_item
    text = wi42()
    assert serialize_item(parse_item(text)) == text


def test_field_order_then_unknown_then_x_fields(kit):
    from lib.kanban.items import Item, serialize_item
    out = serialize_item(Item({"x-uid": "u", "title": "T", "id": "WI-1", "zzz": 1, "status": "Ready"}, "b\n"))
    keys = [ln.split(":")[0] for ln in out.split("---\n")[1].splitlines()]
    assert keys == ["id", "title", "status", "zzz", "x-uid"]


def test_empty_lists_and_none(kit):
    from lib.kanban.items import Item, serialize_item
    out = serialize_item(Item({"id": "WI-1", "title": "T", "labels": [], "assignee": None,
                               "created_date": "2026-10-24 10:12", "documentation": ["a", "b"]}, ""))
    assert "labels: []\n" in out and "assignee" not in out
    assert "documentation:\n  - a\n  - b\n" in out
    assert "created_date: '2026-10-24 10:12'\n" in out
    assert out.startswith("---\n") and out.endswith("---\n\n")


def test_unquoted_dates_stay_text(kit):
    from lib.kanban.items import parse_item
    assert parse_item("---\nid: WI-1\ncreated_date: 2026-10-24\n---\n").fm["created_date"] == "2026-10-24"


def test_crlf_parses_like_lf(kit):
    from lib.kanban.items import parse_item
    raw = (FIX / "crlf.md").read_bytes().decode("utf-8")
    assert "\r\n" in raw
    assert parse_item(raw).fm == parse_item(raw.replace("\r\n", "\n")).fm
    assert parse_item(raw).body == parse_item(raw.replace("\r\n", "\n")).body


def test_bad_yaml_raises_item_error(kit):
    from lib.kanban.items import ItemError, parse_item
    with pytest.raises(ItemError):
        parse_item("---\nid: WI-1\ntitle: a: b: [\n---\n")
    with pytest.raises(ItemError):
        parse_item("no frontmatter here\n")


def test_missing_id_raises_item_error(kit):
    from lib.kanban.items import ItemError, parse_item
    with pytest.raises(ItemError):
        parse_item("---\ntitle: T\n---\n\nbody\n")


def test_properties(kit):
    from lib.kanban.items import parse_item
    it = parse_item(wi42())
    assert (it.id, it.uid, it.type, it.title) == ("WI-42", "01jb7q3m", "story", "Idempotent PaymentRequested handling")


def test_file_name_is_lowercase_id_and_sanitised(kit):
    from lib.kanban.items import file_name
    assert file_name("WI-42", "Idempotent PaymentRequested handling") == "wi-42 - Idempotent PaymentRequested handling.md"
    n = file_name("WI-7", 'a<b>:c"/d\\e|f?g*. ')
    assert not any(c in n[len("wi-7 - "):] for c in '<>:"/\\|?*')
    assert not n[:-3].endswith((".", " "))
    n = file_name("WI-7", "word " * 60)
    assert len(n[len("wi-7 - "):-len(".md")]) <= 60
    assert not file_name("WI-7", "x" * 300)[:-3].endswith(" ")
    assert "🦐 Gambas" in file_name("WI-7", "🦐 Gambas")


def test_checklists(kit):
    from lib.kanban.items import checklist, description, parse_item
    body = parse_item(wi42()).body
    assert checklist(body, "AC") == [{"n": 1, "done": False, "text": "A duplicate message has no second effect"},
                                     {"n": 2, "done": False, "text": "After 3 retries the message goes to the DLQ"}]
    assert checklist(body, "DOD") == [{"n": 1, "done": False, "text": "acceptance criteria met"}]
    assert checklist(body.replace("- [ ] #1 A dup", "- [x] #1 A dup"), "AC")[0]["done"] is True
    assert description(body) == "As … I want … so that …"


def test_templates_per_type_and_language(kit):
    from lib.kanban.items import default_dod, new_body
    b = new_body("story", "es", ["x"])
    for marker in ("<!-- SECTION:DESCRIPTION:BEGIN -->", "<!-- AC:BEGIN -->", "<!-- DOD:BEGIN -->", "- [ ] #1 x"):
        assert marker in b
    assert all(w in b.lower() for w in ("como", "quiero", "para"))
    b = new_body("bug", "en", []).lower()
    assert all(w in b for w in ("steps", "expected", "actual", "environment"))
    for t in ("epic", "story", "bug", "spike", "task"):
        for lang in ("en", "es"):
            assert "DESCRIPTION:END" in new_body(t, lang, [])
    assert default_dod("en")[0] == "acceptance criteria met" and len(default_dod("es")) == 3


def test_load_dir_reports_problems(kit, tmp_path):
    from lib.kanban.items import load_dir
    d = tmp_path / "tasks"
    d.mkdir()
    (d / "wi-1 - ok.md").write_text("---\nid: WI-1\ntitle: ok\n---\n\nb\n", encoding="utf-8")
    (d / "bad.md").write_text("---\ntitle: no id\n---\n", encoding="utf-8")
    items, problems = load_dir(d)
    assert [i.id for i in items] == ["WI-1"] and items[0].path == d / "wi-1 - ok.md"
    assert len(problems) == 1 and problems[0]["path"] == d / "bad.md" and problems[0]["error"]
    assert load_dir(tmp_path / "nope") == ([], [])


def test_paths_are_under_cam_docs_backlog(kit):
    from lib import kanban
    assert kanban.TASKS == kit.root / "backlog" / "tasks" and kanban.PREFIX == "WI"
    assert not kanban.enabled()
    kanban.BOARD.parent.mkdir(parents=True)
    kanban.BOARD.write_text("version: 1\ncards: {}\n", encoding="utf-8")
    assert kanban.enabled()


def test_init_templates_does_not_copy_board_templates(wired):
    assert not (wired.root / "board").exists()


def test_new_body_takes_a_description_and_criteria(kit):
    from lib.kanban.items import checklist, description, new_body
    b = new_body("task", "en", ["done"], description="Do it.\nTwice.", criteria=["a", " b  c ", " "])
    assert description(b) == "Do it.\nTwice."
    assert [(c["n"], c["text"]) for c in checklist(b, "AC")] == [(1, "a"), (2, "b c")]
    assert [c["text"] for c in checklist(b, "DOD")] == ["done"]
    assert new_body("task", "en", ["done"]) == new_body("task", "en", ["done"], description="  ", criteria=())


def test_set_description_and_add_criteria_keep_the_rest(kit):
    from lib.kanban.items import add_criteria, checklist, description, new_body, set_description
    b = new_body("task", "en", ["done"], criteria=["one"])
    b = b.replace("- [ ] #1 one", "- [x] #1 one")
    b2 = add_criteria(set_description(b, "New."), ["two"])
    assert description(b2) == "New." and checklist(b2, "DOD") == checklist(b, "DOD")
    assert [(c["n"], c["done"]) for c in checklist(b2, "AC")] == [(1, True), (2, False)]
    assert add_criteria(b2, [" "]) == b2
    bare = "just notes\n"
    assert description(set_description(bare, "D")) == "D" and set_description(bare, "D").endswith("just notes\n")
    assert [c["text"] for c in checklist(add_criteria(bare, ["x"]), "AC")] == ["x"]
    plain = "## Definition of Done\n<!-- DOD:BEGIN -->\n- [ ] #1 d\n<!-- DOD:END -->\n"
    out = add_criteria(plain, ["x"])
    assert out.index("AC:BEGIN") < out.index("DOD:BEGIN") and checklist(out, "DOD")[0]["text"] == "d"

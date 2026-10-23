"""A board sketched from a C4 view reads like a diagram: people on top, then apps, services and stores in rows, boxes
wide enough for their titles, arrows that go around boxes instead of through them, one arrow per pair of elements and
every relation label visible (bound text, the way Excalidraw draws labels)."""
from __future__ import annotations

import pytest

# Shaped like a real Firebase project: a mobile admin app, two web apps, functions, Firestore and Storage.
C4 = """model {
  dj = actor 'DJ'
  club = system 'Enjoy the club' {
    adminApp = mobileApp 'AdminDJApp'
    adminFns = service 'AdminDJApp Cloud Functions'
    downloads = service 'EnjoyScreenDownloads'
    enjoyWeb = service 'EnjoyWeb'
    screenApp = webapp 'ScreenManagementApp'
    userApp = webapp 'UserWebApp'
    userFns = service 'UserWebApp Cloud Functions'
    firestore = database 'Firestore: enjoy-the-club'
    storage = database 'Firebase Storage: enjoy-the-club'
  }
  dj -> club.adminApp 'manages the session'
  club.adminApp -> club.adminFns 'calls'
  club.adminApp -> club.userFns 'calls'
  club.adminApp -> club.firestore 'reads'
  club.adminApp -> club.firestore 'writes'
  club.adminApp -> club.storage 'uploads'
  club.enjoyWeb -> club.screenApp 'serves'
  club.screenApp -> club.firestore 'listens'
  club.screenApp -> club.adminFns 'calls'
  club.userApp -> club.userFns 'calls'
  club.userFns -> club.userApp 'pushes'
  club.userApp -> club.firestore 'reads'
  club.userApp -> club.storage 'reads'
  club.userFns -> club.firestore 'writes'
  club.adminFns -> club.firestore 'writes'
}
views {
  view containers of club {
    include *
  }
}
"""

ROW = {"el-club.adminApp": 1, "el-club.screenApp": 1, "el-club.userApp": 1,
       "el-club.adminFns": 2, "el-club.userFns": 2, "el-club.enjoyWeb": 2, "el-club.downloads": 2,
       "el-club.firestore": 3, "el-club.storage": 3}


@pytest.fixture
def scene(kit):
    arch = kit.root / "docs" / "architecture"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "model.c4").write_text(C4, encoding="utf-8")
    from lib import boards
    return boards.sketch("containers")["elements"]


def by_type(elements, kind):
    return [e for e in elements if e["type"] == kind]


def box(e):
    return e["x"], e["y"], e["x"] + e["width"], e["y"] + e["height"]


def polyline(arrow):
    return [(arrow["x"] + dx, arrow["y"] + dy) for dx, dy in arrow["points"]]


def segment_hits_box(a, b, rect, margin=1.0):
    """An axis-aligned segment through the inside of a box (touching its border does not count)."""
    x0, y0, x1, y1 = rect[0] + margin, rect[1] + margin, rect[2] - margin, rect[3] - margin
    (ax, ay), (bx, by) = a, b
    if ax == bx:
        return x0 < ax < x1 and min(ay, by) < y1 and max(ay, by) > y0
    if ay == by:
        return y0 < ay < y1 and min(ax, bx) < x1 and max(ax, bx) > x0
    raise AssertionError(f"diagonal segment {a} → {b}")


def test_rows_follow_the_c4_kind(scene):
    rects = {e["id"]: e for e in by_type(scene, "rectangle")}
    assert set(rects) == set(ROW)
    tops = {}
    for rid, row in ROW.items():
        tops.setdefault(row, set()).add(rects[rid]["y"])
    assert all(len(ys) == 1 for ys in tops.values())                          # one row per kind
    assert max(tops[1]) < min(tops[2]) < min(tops[3])                         # apps, services, stores


def test_boxes_never_overlap_and_fit_their_titles(scene):
    rects = by_type(scene, "rectangle")
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            ax0, ay0, ax1, ay1 = box(a)
            bx0, by0, bx1, by1 = box(b)
            assert ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0, (a["id"], b["id"])
    texts = {e["containerId"]: e for e in by_type(scene, "text") if e["containerId"].startswith("el-")}
    for r in rects:
        longest = max(len(line) for line in texts[r["id"]]["text"].splitlines())
        assert r["width"] >= longest * texts[r["id"]]["fontSize"] * 0.6, r["id"]


def test_one_arrow_per_pair_with_both_heads_when_it_goes_both_ways(scene):
    arrows = by_type(scene, "arrow")
    pairs = [frozenset((a["startBinding"]["elementId"], a["endBinding"]["elementId"])) for a in arrows]
    assert len(pairs) == len(set(pairs)) == 12
    both = [a for a in arrows if a["startArrowhead"]]
    assert [frozenset((a["startBinding"]["elementId"], a["endBinding"]["elementId"])) for a in both] == \
        [frozenset(("el-club.userApp", "el-club.userFns"))]


def test_every_arrow_is_bound_and_labelled_with_bound_text(scene):
    ids = {e["id"]: e for e in scene}
    labels = {e["containerId"]: e["text"] for e in by_type(scene, "text") if e["containerId"].startswith("rel-")}
    for a in by_type(scene, "arrow"):
        assert "label" not in a
        for end in ("startBinding", "endBinding"):
            target = ids[a[end]["elementId"]]
            assert {"type": "arrow", "id": a["id"]} in target["boundElements"]
        bound = [b["id"] for b in a["boundElements"] if b["type"] == "text"]
        assert len(bound) == 1 and labels[a["id"]] and ids[bound[0]]["containerId"] == a["id"]
    reads = next(t for cid, t in labels.items()
                 if ids[cid]["startBinding"]["elementId"] == "el-club.adminApp"
                 and ids[cid]["endBinding"]["elementId"] == "el-club.firestore")
    assert reads == "reads / writes"                                            # parallel relations merged


def test_arrows_go_around_boxes(scene):
    rects = {e["id"]: box(e) for e in by_type(scene, "rectangle")}
    for a in by_type(scene, "arrow"):
        pts = polyline(a)
        ends = {a["startBinding"]["elementId"], a["endBinding"]["elementId"]}
        for p, q in zip(pts, pts[1:]):
            for rid, rect in rects.items():
                if rid not in ends:
                    assert not segment_hits_box(p, q, rect), (a["id"], rid)
        assert pts[0] != pts[-1]


def test_a_top_level_view_still_sketches(kit, scene):
    from lib import boards
    (kit.root / "docs" / "architecture" / "views.c4").write_text("views {\n  view index {\n    include *\n  }\n}\n",
                                                                     encoding="utf-8")
    top = boards.sketch("index")["elements"]
    assert {e["id"] for e in by_type(top, "rectangle")} == {"el-dj", "el-club"}
    assert len(by_type(top, "arrow")) == 1

"""Editor stage A: manual edits of metal spots, geovents and start points (atlasforge/edits.py, /api/edit)."""
import json
import math
import urllib.error
import urllib.request

import pytest

from atlasforge import forge
from atlasforge.app.server import serve
from atlasforge.edits import apply_edits, editor_checks, side_of
from atlasforge.symmetry import RotSymmetry

QUIET = dict(log=lambda *a, **k: None)
FAST = {"erosion": 0, "rocks": 0, "wrecks": 0}
DUEL = dict(FAST, size=12, gates=2)


@pytest.fixture(scope="module")
def duel():
    return forge.make("chokepoint", DUEL, seed=3, **QUIET)


@pytest.fixture(scope="module")
def ffa():
    return forge.make("ffa_ring", dict(FAST, players=5, size=20), seed=2, **QUIET)


def _xy(d):
    return sorted((round(m["x"], 3), round(m["z"], 3)) for m in d.mexes)


def _side_metal(d):
    out = {}
    for m in d.mexes:
        out[m["side"]] = out.get(m["side"], 0) + m["metal"]
    return out


def _has(points, p, tol=1e-6):
    return any(math.hypot(q[0] - p[0], q[1] - p[1]) < tol for q in points)


def _free_spot(d):
    """A spot off the centre line and 150+ elmos from every mex, geo and start."""
    W, H = d.sym.W, d.sym.H
    pts = [(m["x"], m["z"]) for m in d.mexes] + list(d.geos) + list(d.starts)
    for fx in (0.3, 0.25, 0.35, 0.2):
        for fz in (0.3, 0.45, 0.6, 0.2):
            p = (fx * W, fz * H)
            if all(math.hypot(p[0] - q[0], p[1] - q[1]) > 150 for q in pts):
                return p
    raise AssertionError("no free spot")


def test_input_design_is_not_modified(duel):
    before = _xy(duel)
    m = duel.mexes[0]
    apply_edits(duel, [{"op": "del_mex", "at": [m["x"], m["z"]]}])
    assert _xy(duel) == before


def test_move_mex_moves_the_mirror_image(duel):
    m = duel.mexes[0]
    to = _free_spot(duel)
    d, problems = apply_edits(duel, [{"op": "move_mex", "from": [m["x"], m["z"]], "to": list(to)}])
    assert not problems
    assert len(d.mexes) == len(duel.mexes)
    pts = [(q["x"], q["z"]) for q in d.mexes]
    assert _has(pts, to) and _has(pts, duel.sym.mirror(*to))
    s = _side_metal(d)
    assert abs(s[0] - s[1]) < 1e-6                          # still fair


def test_symmetry_off_moves_only_one(duel):
    m = duel.mexes[0]
    to = _free_spot(duel)
    d, problems = apply_edits(duel, [{"op": "move_mex", "from": [m["x"], m["z"]], "to": list(to)}], symmetry=False)
    assert not problems
    assert sum(1 for q in d.mexes if math.hypot(q["x"] - to[0], q["z"] - to[1]) < 1e-6) == 1
    assert not _has([(q["x"], q["z"]) for q in d.mexes], duel.sym.mirror(*to))


def test_add_delete_set_metal_and_undo_by_shortening(duel):
    to = _free_spot(duel)
    edits = [{"op": "add_mex", "at": list(to), "metal": 3.5}]
    d1, p1 = apply_edits(duel, edits)
    assert not p1 and len(d1.mexes) == len(duel.mexes) + 2
    edits.append({"op": "set_metal", "at": list(to), "metal": 1.5})
    d2, p2 = apply_edits(duel, edits)
    assert not p2
    new = [q for q in d2.mexes if abs(q["metal"] - 1.5) < 1e-9]
    assert len(new) == 2 and {q["side"] for q in new} == {0, 1}
    edits.append({"op": "del_mex", "at": list(to)})
    d3, p3 = apply_edits(duel, edits)
    assert not p3 and _xy(d3) == _xy(duel)
    d4, _ = apply_edits(duel, edits[:-2])                   # undo = shorter list
    assert len(d4.mexes) == len(duel.mexes) + 2


def test_geo_edits(duel):
    to = _free_spot(duel)
    d, p = apply_edits(duel, [{"op": "add_geo", "at": list(to)}])
    assert not p and len(d.geos) == len(duel.geos) + 2
    d, p = apply_edits(duel, [{"op": "add_geo", "at": list(to)}, {"op": "del_geo", "at": list(to)}])
    assert not p and sorted(d.geos) == sorted(duel.geos)


def test_move_start_keeps_starts_and_teams_in_sync(duel):
    s0 = duel.starts[0]
    to = (s0[0] + 200, s0[1] + 150)
    d, p = apply_edits(duel, [{"op": "move_start", "from": list(s0), "to": list(to)}])
    assert not p
    assert _has(d.starts, to) and _has(d.starts, duel.sym.mirror(*to))
    assert sorted(q for t in d.teams for q in t) == sorted(d.starts)


def test_orphans_and_rejections_are_reported_not_raised(duel):
    W, H = duel.sym.W, duel.sym.H
    m = duel.mexes[0]
    edits = [
        {"op": "del_mex", "at": [1, 1]},                                         # nothing there
        {"op": "move_mex", "from": [m["x"], m["z"]], "to": [W / 2, H / 2]},       # centre: no mirror image
        {"op": "move_mex", "from": [m["x"], m["z"]], "to": [-50, 10]},            # off the map
        {"op": "add_mex", "at": [m["x"] + 10, m["z"]], "metal": 2},               # on top of another spot
        {"op": "fly_mex"},
        {"op": "move_mex", "from": "x", "to": [1, 2]},
    ]
    d, problems = apply_edits(duel, edits)
    assert [p["index"] for p in problems] == [0, 1, 2, 3, 4, 5]
    assert all(p["reason"] for p in problems)
    assert _xy(d) == _xy(duel)


def test_ffa_rotation_orbit(ffa):
    assert isinstance(ffa.sym, RotSymmetry)
    m = ffa.mexes[0]
    to = ffa.sym.polar(2300, 9, 0)
    d, p = apply_edits(ffa, [{"op": "move_mex", "from": [m["x"], m["z"]], "to": list(to)}])
    assert not p
    pts = [(q["x"], q["z"]) for q in d.mexes]
    assert all(_has(pts, ffa.sym.rotate(to[0], to[1], k)) for k in range(ffa.sym.n))
    s = _side_metal(d)
    assert len(s) == ffa.sym.n and max(s.values()) - min(s.values()) < 1e-6


def test_ffa_start_moves_for_all_players(ffa):
    s0 = ffa.starts[0]
    to = ffa.sym.polar(math.hypot(s0[0] - ffa.sym.cx, s0[1] - ffa.sym.cz) * 0.9, 4, 0)
    d, p = apply_edits(ffa, [{"op": "move_start", "from": list(s0), "to": list(to)}])
    assert not p
    assert all(_has(d.starts, ffa.sym.rotate(to[0], to[1], k)) for k in range(ffa.sym.n))


def test_editor_checks_unequal_metal_and_water(duel):
    m = duel.mexes[0]
    d, _ = apply_edits(duel, [{"op": "set_metal", "at": [m["x"], m["z"]], "metal": 7}], symmetry=False)
    texts = [i["text"] for i in editor_checks(d, symmetry=False)]
    assert any("Metal is not equal" in t and "symmetry is off" in t for t in texts)
    wet = duel.hm.min() < 0
    if wet:                                                 # a spot on water is an error
        zz, xx = [int(v[0]) for v in (duel.hm < 0).nonzero()]
        x, z = xx * 8.0, zz * 8.0
        d, _ = apply_edits(duel, [{"op": "add_geo", "at": [x, z]}], symmetry=False)
        assert any(i["level"] == "error" for i in editor_checks(d, symmetry=False))


def test_orphan_move_is_reported_and_map_unchanged(duel):
    m = duel.mexes[0]
    miss = [m["x"] + 30, m["z"]]                            # beyond TOL (24): no mex is addressed
    d, problems = apply_edits(duel, [{"op": "move_mex", "from": miss, "to": _free_spot(duel)}])
    assert [p["index"] for p in problems] == [0]
    assert "nothing there" in problems[0]["reason"]
    assert _xy(d) == _xy(duel)


def test_ffa_add_and_delete_cover_the_whole_orbit(ffa):
    n = ffa.sym.n
    to = ffa.sym.polar(2300, 9, 0)
    d, p = apply_edits(ffa, [{"op": "add_mex", "at": list(to), "metal": 2.0}])
    assert not p and len(d.mexes) == len(ffa.mexes) + n
    pts = [(q["x"], q["z"]) for q in d.mexes]
    assert all(_has(pts, ffa.sym.rotate(to[0], to[1], k)) for k in range(n))
    d, p = apply_edits(ffa, [{"op": "add_mex", "at": list(to), "metal": 2.0},
                             {"op": "del_mex", "at": list(to)}])
    assert not p and _xy(d) == _xy(ffa)


def test_add_mex_rejects_centre_and_spots_too_close(duel):
    cx, cz = duel.sym.W / 2, duel.sym.H / 2
    m = duel.mexes[0]
    edits = [
        {"op": "add_mex", "at": [cx, cz], "metal": 2.0},                    # fixed point: no mirror image
        {"op": "add_mex", "at": [m["x"] + 10, m["z"]], "metal": 2.0},       # closer than MIN_GAP to a mex
    ]
    d, problems = apply_edits(duel, edits)
    assert [p["index"] for p in problems] == [0, 1]
    assert _xy(d) == _xy(duel)


def test_ffa_centre_is_rejected(ffa):
    d, problems = apply_edits(ffa, [{"op": "add_mex", "at": [ffa.sym.cx, ffa.sym.cz], "metal": 2.0}])
    assert len(problems) == 1 and _xy(d) == _xy(ffa)


def test_symmetry_off_warns_not_symmetric(duel):
    m = duel.mexes[0]
    to = _free_spot(duel)
    if side_of(duel.sym, *to) == m["side"]:                 # cross to the other side so the totals change
        to = duel.sym.mirror(*to)
    d, problems = apply_edits(duel, [{"op": "move_mex", "from": [m["x"], m["z"]], "to": list(to)}], symmetry=False)
    assert not problems
    assert len(d.mexes) == len(duel.mexes)
    assert sum(1 for q in d.mexes if math.hypot(q["x"] - to[0], q["z"] - to[1]) < 1e-6) == 1
    checks = editor_checks(d, symmetry=False)
    warns = [i for i in checks if i["level"] == "warn" and "Metal is not equal" in i["text"]]
    assert warns and "symmetry is off" in warns[0]["text"]
    assert not any(i["level"] == "error" and "Metal" in i["text"] for i in checks)


def test_same_edits_on_fresh_copies_give_same_result(duel):
    m0, m1 = duel.mexes[0], duel.mexes[1]
    to = _free_spot(duel)
    edits = [
        {"op": "move_mex", "from": [m0["x"], m0["z"]], "to": list(to)},
        {"op": "add_geo", "at": list(to)},
        {"op": "set_metal", "at": [m1["x"], m1["z"]], "metal": 2.5},
        {"op": "del_mex", "at": [m1["x"], m1["z"]]},
    ]
    a, pa = apply_edits(duel, edits)
    b, pb = apply_edits(duel, list(edits))
    assert pa == pb and a.mexes == b.mexes and a.geos == b.geos and a.starts == b.starts and a.teams == b.teams


# ----------------------------------------------------------------------------- server
@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    srv, url, state = serve(0)

    def call(path, body=None):
        req = urllib.request.Request(url + "api/" + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"X-Forge-Token": state.token})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    yield call, state
    srv.shutdown()


def test_api_edit_end_to_end(app):
    call, state = app
    p = call("preview", {"template": "chokepoint", "values": DUEL, "seed": 3})
    assert p["edits"] == [] and p["sym"]["kind"] == "mirror"
    n = len(p["mexes"])
    to = _free_spot(state.entry(p["id"]).design)
    add = [{"op": "add_mex", "at": list(to), "metal": 2.5}]
    r = call("edit", {"id": p["id"], "edits": add, "symmetry": True})
    assert len(r["mexes"]) == n + 2 and r["problems"] == [] and "lines" in r and "teams" in r
    assert len(state.entry(p["id"]).design.mexes) == n + 2          # a build uses the edited design
    r2 = call("edit", {"id": p["id"], "edits": [], "symmetry": True})          # undo everything
    assert len(r2["mexes"]) == n and r2["lines"] == p["lines"]
    r3 = call("edit", {"id": p["id"], "edits": [{"op": "del_mex", "at": [3, 3]}], "symmetry": True})
    assert len(r3["problems"]) == 1 and len(r3["mexes"]) == n
    with pytest.raises(urllib.error.HTTPError):
        call("edit", {"id": "nope", "edits": []})


def test_preview_with_edits_and_project_roundtrip(app):
    call, state = app
    p = call("preview", {"template": "chokepoint", "values": DUEL, "seed": 3})
    to = _free_spot(state.entry(p["id"]).design)
    edits = [{"op": "add_geo", "at": list(to)}]
    q = call("preview", {"template": "chokepoint", "values": DUEL, "seed": 3, "edits": edits, "symmetry": True})
    assert len(q["geos"]) == len(p["geos"]) + 2 and q["edits"] == edits
    text = call("project_dump", {"data": dict(template="chokepoint", values=q["values"], seed=3, symmetry=True,
                                              edits=edits, title="T", mine="kept")})["text"]
    back = call("project_load", {"text": text})
    assert back["project"]["edits"] == edits and back["extra"] == {"mine": "kept"}
    with pytest.raises(urllib.error.HTTPError):
        call("project_load", {"text": json.dumps(dict(back["project"], version=99))})

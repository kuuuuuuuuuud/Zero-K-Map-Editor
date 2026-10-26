"""set_box edits: moving/reshaping start box polygons, mirrored with the symmetry, and the Lua round trip."""
import pytest

from atlasforge import forge
from atlasforge.app.luatable import startboxes
from atlasforge.edits import apply_edits
from atlasforge.formats import startboxes_lua, startboxes_to_lua
from atlasforge.symmetry import orbit

QUIET = dict(log=lambda *a: None)


def _boxes(d):
    return startboxes(d.startboxes if d.startboxes is not None else startboxes_lua(d.sym, d.starts))


def _shift(poly, dx, dz):
    return [[x + dx, z + dz] for x, z in poly]


@pytest.fixture(scope="module")
def arena():
    return forge.make("arena", {"size": 12, "erosion": 0}, seed=2, **QUIET)


@pytest.fixture(scope="module")
def chokepoint():
    return forge.make("chokepoint", {"size": 12}, seed=3, **QUIET)


@pytest.fixture(scope="module")
def skirmish():                                  # generated boxes: no map_startboxes.lua of its own
    return forge.make("skirmish", {"size": 12}, seed=3, **QUIET)


@pytest.fixture(scope="module")
def ffa():
    return forge.make("ffa_ring", {"size": 20, "players": 5}, seed=2, **QUIET)


def test_roundtrip_own_lua_and_generated(arena, chokepoint):
    for d in (arena, chokepoint):
        b = _boxes(d)
        assert startboxes(startboxes_to_lua(b)) == b


def test_template_without_lua_has_no_boxes_until_edited(skirmish):
    assert skirmish.startboxes is None
    d, problems = apply_edits(skirmish, [])
    assert problems == [] and d.startboxes is None
    d, problems = apply_edits(skirmish, [{"op": "set_box", "team": 0, "poly": 0,
                                          "points": [[10, 10], [900, 10], [900, 900]]}], symmetry=False)
    assert problems == [] and d.startboxes and startboxes(d.startboxes)[0]["polygons"][0][1] == [900.0, 10.0]


def test_untouched_boxes_stay_byte_identical(arena):
    before = arena.startboxes
    d, problems = apply_edits(arena, [{"op": "del_geo", "at": [-999, -999]}])
    assert d.startboxes == before


def test_own_lua_template_box_is_replaced(arena):
    boxes = _boxes(arena)
    poly = _shift(boxes[0]["polygons"][0], 40, 0)
    d, problems = apply_edits(arena, [{"op": "set_box", "team": 0, "poly": 0, "points": poly}], symmetry=False)
    assert problems == []
    after = _boxes(d)
    assert after[0]["polygons"][0] == [[float(x), float(z)] for x, z in poly]
    assert after[0]["polygons"][1:] == boxes[0]["polygons"][1:]
    assert [b["team"] for b in after] == [b["team"] for b in boxes]
    assert all(a["polygons"] == b["polygons"] for a, b in zip(after[1:], boxes[1:]))


def test_mirror_symmetry_moves_the_other_team(chokepoint):
    sym = chokepoint.sym
    boxes = _boxes(chokepoint)
    poly = _shift(boxes[0]["polygons"][0], 60, 30)
    d, problems = apply_edits(chokepoint, [{"op": "set_box", "team": 0, "poly": 0, "points": poly}])
    assert problems == []
    after = _boxes(d)
    assert after[0]["polygons"][0] == [[float(x), float(z)] for x, z in poly]
    mirrored = [list(orbit(sym, x, z)[1]) for x, z in poly]
    got = after[1]["polygons"][0]
    assert all(abs(g[0] - m[0]) < 1.0 and abs(g[1] - m[1]) < 1.0 for g, m in zip(got, mirrored))


def test_no_symmetry_changes_only_the_clicked_box(chokepoint):
    boxes = _boxes(chokepoint)
    poly = _shift(boxes[0]["polygons"][0], 60, 30)
    d, problems = apply_edits(chokepoint, [{"op": "set_box", "team": 0, "poly": 0, "points": poly}], symmetry=False)
    assert problems == []
    after = _boxes(d)
    assert after[1]["polygons"] == boxes[1]["polygons"]


def test_ffa_rotation_maps_each_team_to_its_own_image(ffa):
    sym = ffa.sym
    boxes = [b for b in _boxes(ffa) if b["startpoints"]]
    src = boxes[0]
    poly = _shift(src["polygons"][0], 30, 0)
    d, problems = apply_edits(ffa, [{"op": "set_box", "team": src["team"], "poly": 0, "points": poly}])
    assert problems == []
    after = {b["team"]: b for b in _boxes(d)}
    for j, b in enumerate(boxes[1:], start=1):
        exp = [list(orbit(sym, x, z)[j]) for x, z in poly]
        if all(0 <= x <= sym.W and 0 <= z <= sym.H for x, z in exp):
            got = after[b["team"]]["polygons"][0]
            assert all(abs(g[0] - e[0]) < 1.0 and abs(g[1] - e[1]) < 1.0 for g, e in zip(got, exp))


def test_unknown_box_is_a_problem_not_an_error(chokepoint):
    pts = [[10, 10], [50, 10], [50, 50]]
    _, problems = apply_edits(chokepoint, [{"op": "set_box", "team": 9, "poly": 0, "points": pts}])
    assert problems and problems[0]["reason"] == "start box not found"
    _, problems = apply_edits(chokepoint, [{"op": "set_box", "team": 0, "poly": 7, "points": pts}])
    assert problems and problems[0]["reason"] == "start box not found"


def test_too_few_points_is_rejected(chokepoint):
    _, problems = apply_edits(chokepoint, [{"op": "set_box", "team": 0, "poly": 0, "points": [[1, 1], [2, 2]]}])
    assert problems and "3 [x, z] points" in problems[0]["reason"]


def test_deterministic(chokepoint):
    boxes = _boxes(chokepoint)
    edit = [{"op": "set_box", "team": 0, "poly": 0, "points": _shift(boxes[0]["polygons"][0], 25, 5)}]
    a, _ = apply_edits(chokepoint, edit)
    b, _ = apply_edits(chokepoint, edit)
    assert a.startboxes == b.startboxes

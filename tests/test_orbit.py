"""Unified orbit()/match_orbit()/orbit_degenerate() for Symmetry and RotSymmetry (editor snapping)."""
import math
import random

import pytest

from atlasforge.symmetry import RotSymmetry, Symmetry, match_orbit, orbit, orbit_degenerate

W = 8192.0
H = 8192.0

SYMS = [Symmetry(layout, W, H) for layout in ("ew", "ns", "diag")] + [RotSymmetry(n, W) for n in range(3, 9)]
SYM_IDS = ["ew", "ns", "diag"] + ["rot%d" % n for n in range(3, 9)]


def _orbit_len(sym):
    return sym.n if isinstance(sym, RotSymmetry) else 2


def _generic_points(sym, i):
    """Non-degenerate sample points (orbit copies clearly farther apart than min_dist)."""
    rng = random.Random(1000 + i)
    pts = []
    if isinstance(sym, RotSymmetry):
        for _ in range(6):
            r = rng.uniform(300.0, 2000.0)
            a = rng.uniform(0.0, 2 * math.pi)
            pts.append((sym.cx + r * math.cos(a), sym.cz + r * math.sin(a)))
    else:
        for _ in range(6):
            pts.append((rng.uniform(0.05 * W, 0.45 * W), rng.uniform(0.05 * H, 0.45 * H)))
    return pts


_CASES = []
for _i, _sym in enumerate(SYMS):
    for _x, _z in _generic_points(_sym, _i):
        _CASES.append((_sym, _x, _z))

CASE_IDS = ["%s-%d" % (SYM_IDS[_c // 6], _c % 6) for _c in range(len(_CASES))]


def _noise(i):
    return (((i * 7) % 21) - 10.0, ((i * 5) % 19) - 9.0)


@pytest.mark.parametrize(("sym", "x", "z"), _CASES, ids=CASE_IDS)
def test_orbit_shape_and_original(sym, x, z):
    pts = orbit(sym, x, z)
    assert len(pts) == _orbit_len(sym)
    for px, pz in pts:
        assert isinstance(px, float) and isinstance(pz, float)
    assert math.hypot(pts[0][0] - x, pts[0][1] - z) < 1e-6


@pytest.mark.parametrize(("sym", "x", "z"), _CASES, ids=CASE_IDS)
def test_orbit_group_closure(sym, x, z):
    for qx, qz in orbit(sym, x, z):
        sub = orbit(sym, qx, qz)
        assert min(math.hypot(px - x, pz - z) for px, pz in sub) < 1e-6


@pytest.mark.parametrize(("sym", "x", "z"), _CASES, ids=CASE_IDS)
def test_match_orbit_exact(sym, x, z):
    pts = orbit(sym, x, z)
    assert match_orbit(sym, (x, z), list(pts)) == list(range(len(pts)))


@pytest.mark.parametrize(("sym", "x", "z"), _CASES, ids=CASE_IDS)
def test_match_orbit_noisy(sym, x, z):
    pts = orbit(sym, x, z)
    others = [(px + _noise(i)[0], pz + _noise(i)[1]) for i, (px, pz) in enumerate(pts)]
    assert match_orbit(sym, (x, z), others) == list(range(len(pts)))


@pytest.mark.parametrize(("sym", "x", "z"), _CASES, ids=CASE_IDS)
def test_match_orbit_none_when_missing(sym, x, z):
    n = _orbit_len(sym)
    assert match_orbit(sym, (x, z), []) == [None] * n
    far = [(W - 200.0, H - 200.0)]
    pts = orbit(sym, x, z)
    assert all(math.hypot(px - far[0][0], pz - far[0][1]) > 24 for px, pz in pts)
    assert match_orbit(sym, (x, z), far) == [None] * n


@pytest.mark.parametrize(("sym", "x", "z"), _CASES, ids=CASE_IDS)
def test_match_orbit_partial(sym, x, z):
    pts = orbit(sym, x, z)
    assert match_orbit(sym, (x, z), list(pts[:2])) == [0, 1] + [None] * (_orbit_len(sym) - 2)


@pytest.mark.parametrize(("sym", "x", "z"), _CASES, ids=CASE_IDS)
def test_match_orbit_never_reuses_object(sym, x, z):
    pts = orbit(sym, x, z)
    mids = [
        ((pts[i][0] + pts[(i + 1) % len(pts)][0]) / 2.0, (pts[i][1] + pts[(i + 1) % len(pts)][1]) / 2.0)
        for i in range(len(pts))
    ]
    res = match_orbit(sym, (x, z), mids)
    picked = [v for v in res if v is not None]
    assert len(picked) == len(set(picked))


def test_match_orbit_conflict_single_winner():
    sym = SYMS[0]  # ew: orbit points only 30 elmos apart, one object between them
    p = (W / 2 - 15.0, 1000.0)
    res = match_orbit(sym, p, [(W / 2.0, 1000.0)])
    assert sum(v is not None for v in res) == 1


def test_match_orbit_conflict_rot():
    sym = RotSymmetry(8, W)
    r = 15.0 / math.sin(math.pi / 8)  # adjacent orbit points exactly 30 elmos apart (non-degenerate)
    p = (sym.cx + r, sym.cz)
    pts = orbit(sym, *p)
    mid = ((pts[0][0] + pts[1][0]) / 2.0, (pts[0][1] + pts[1][1]) / 2.0)
    assert not orbit_degenerate(sym, *p)
    res = match_orbit(sym, p, [mid])
    assert sum(v is not None for v in res) == 1


def test_orbit_degenerate_center():
    for sym in SYMS:
        assert orbit_degenerate(sym, W / 2.0, H / 2.0) is True


def test_orbit_degenerate_mirror_line():
    ew = Symmetry("ew", W, H)
    ns = Symmetry("ns", W, H)
    diag = Symmetry("diag", W, H)
    assert orbit_degenerate(ew, W / 2.0, 0.3 * H) is True
    assert orbit_degenerate(ns, 0.3 * W, H / 2.0) is True
    assert orbit_degenerate(diag, W / 2.0 - 100.0, H / 2.0 + 77.0) is False


@pytest.mark.parametrize(("sym", "x", "z"), _CASES, ids=CASE_IDS)
def test_orbit_degenerate_generic_false(sym, x, z):
    assert orbit_degenerate(sym, x, z) is False


def test_orbit_degenerate_min_dist_param():
    ew = SYMS[0]
    p = (W / 2.0 - 30.0, 500.0)  # mirror copy 60 elmos away
    assert orbit_degenerate(ew, *p, min_dist=8.0) is False
    assert orbit_degenerate(ew, *p, min_dist=100.0) is True
    rot = RotSymmetry(4, W)
    q = (rot.cx + 30.0, rot.cz)  # adjacent rotation ~42 elmos away
    assert orbit_degenerate(rot, *q, min_dist=8.0) is False
    assert orbit_degenerate(rot, *q, min_dist=60.0) is True

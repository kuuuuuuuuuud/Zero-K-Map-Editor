"""Free-for-all maps: rotational symmetry, one start box per player, fair resources, builds."""
import math

import numpy as np
import pytest

from atlasforge import forge
from atlasforge.app.luatable import startboxes
from atlasforge.resources import parts
from atlasforge.symmetry import RotSymmetry

QUIET = dict(log=lambda *a, **k: None)
FAST = {"erosion": 0, "rocks": 0, "wrecks": 0}


def _orbit_ok(points, sym, tol=2.0):
    """Every point has its rotated copy in the list."""
    pts = np.array(points, float)
    for x, z in pts:
        rx, rz = sym.rotate(x, z, 1)
        if np.hypot(pts[:, 0] - rx, pts[:, 1] - rz).min() > tol:
            return False
    return True


def test_rot_symmetry_points():
    s = RotSymmetry(5, 10240)
    x, z = s.polar(3000, 12, 0)
    assert s.sector(x, z) == 0
    assert all(s.sector(*s.rotate(x, z, k)) == k for k in range(5))
    a, b = s.orbit(x, z)[0], s.rotate(*s.orbit(x, z)[4], 1)
    assert math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6


@pytest.mark.parametrize("players, size", [(3, 16), (5, 20), (8, 24)])
def test_ffa_ring_fair(players, size):
    d = forge.make("ffa_ring", dict(FAST, players=players, size=size), seed=2, **QUIET)
    ok, lines = forge.check(d)
    assert ok, "\n".join(lines)
    assert len(d.teams) == players and all(len(t) == 1 for t in d.teams)
    assert parts(d) == players
    assert len(d.mexes) % players == 0 and len(d.geos) == players
    assert _orbit_ok([(m["x"], m["z"]) for m in d.mexes], d.sym)
    assert _orbit_ok(d.geos, d.sym)
    boxes = startboxes(d.startboxes)
    assert len(boxes) == players and all(b["polygons"] for b in boxes)
    # terrain is rotationally symmetric inside the playable circle (up to interpolation)
    rot = d.sym.rotate_grid(d.hm, 1)
    n = d.hm.shape[0]
    zz, xx = np.mgrid[0:n, 0:n]
    inside = np.hypot(xx - n // 2, zz - n // 2) < 0.42 * n
    assert np.median(np.abs(rot - d.hm)[inside]) < 1.0


def test_ffa_general_settings():
    d = forge.make("ffa_ring", dict(players=6, size=20, mex_count=14, geos=2, rocks=1.0, wrecks=1.0), seed=4, **QUIET)
    ok, lines = forge.check(d)
    assert ok, "\n".join(lines)
    assert len(d.mexes) / 6 == pytest.approx(14, abs=0.5)
    assert len(d.geos) / 6 == pytest.approx(2, abs=0.5)
    assert _orbit_ok([(m["x"], m["z"]) for m in d.mexes], d.sym)
    assert any("per player" in l for l in lines)
    feats = [(x, z) for (_n, x, z, _r) in d.features]
    assert feats and _orbit_ok(feats, d.sym, tol=3.0)


def test_ffa_build(tmp_path):
    from atlasforge import watermark
    from atlasforge.config import ForgeConfig
    d = forge.make("ffa_ring", dict(FAST, players=4, size=16), seed=1, **QUIET)
    info = forge.build(d, outdir=str(tmp_path), config=ForgeConfig(author="Test"), log=lambda *a: None)
    import zipfile
    with zipfile.ZipFile(info["path"]) as z:
        mi = z.read("mapinfo.lua").decode()
        sb = z.read("mapconfig/map_startboxes.lua").decode()
    assert mi.count("startpos") == 4
    assert len(startboxes(sb)) == 4
    r = watermark.verify(info["path"])
    assert r["forge"] and r["payload"]["template"] == "ffa_ring"

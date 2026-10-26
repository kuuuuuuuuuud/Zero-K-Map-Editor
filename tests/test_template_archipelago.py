"""Contract, geometry and archive tests for the archipelago naval template."""
import json
import zipfile

import numpy as np
import pytest
from scipy import ndimage

from atlasforge import forge
from atlasforge.templates import get

TID = "archipelago"
QUIET = lambda *a: None


@pytest.mark.parametrize("seed", range(1, 11))
def test_defaults_pass_the_check(seed):
    d = forge.make(TID, seed=seed, log=QUIET)
    ok, lines = forge.check(d)
    assert ok, "\n".join(lines)
    assert d.mexes and len(d.teams) == 2
    assert d.movement_profile == "naval"
    assert (d.hm < -15).mean() > 0.45
    assert (d.hm > 0).any()
    assert any(d.hm[int(m["z"] / 8), int(m["x"] / 8)] < -15 for m in d.mexes)


def test_symmetry_and_determinism():
    a = forge.make(TID, {"erosion": 0}, seed=2, log=QUIET)
    b = forge.make(TID, {"erosion": 0}, seed=2, log=QUIET)
    assert np.array_equal(a.hm, b.hm)
    assert np.array_equal(a.hm, a.hm[:, ::-1])
    assert a.mexes == b.mexes and a.starts == b.starts
    W = (a.hm.shape[0] - 1) * 8
    lookup = {(round(m["x"], 6), round(m["z"], 6), m["metal"], m["side"]) for m in a.mexes}
    for m in a.mexes:
        assert (round(W - m["x"], 6), round(m["z"], 6), m["metal"], 1 - m["side"]) in lookup
    assert a.sym.mirror(*a.starts[0]) == a.starts[1]
    assert a.sym.mirror(*a.naval_starts[0][0]) == a.naval_starts[1][0]
    assert {(round(W - x, 6), round(z, 6)) for x, z in a.geos} == {(round(x, 6), round(z, 6)) for x, z in a.geos}
    assert a.startboxes and "West" in a.startboxes and "East" in a.startboxes
    c = forge.make(TID, {"erosion": 0}, seed=3, log=QUIET)
    assert not np.array_equal(a.hm, c.hm)


def test_advanced_extremes_do_not_crash():
    t = get(TID)
    for p in t.params:
        if p.kind in ("int", "float"):
            vals = p.limits(True)
        elif p.kind == "choice":
            vals = p.options(True)
        else:
            vals = (False, True)
        for val in vals:
            d = forge.make(TID, {p.key: val, "erosion": 0}, seed=1, log=QUIET, advanced=True)
            assert d.hm.dtype == np.float32 and np.isfinite(d.hm).all(), (p.key, val)
            # Even extreme maps must be inspectable by the check and preview paths.
            forge.check(d)
            assert forge.preview(d, size=128).size == (128, 128)
    for high in (False, True):
        values = {"erosion": 0, "size": 8}
        for p in t.params:
            if p.kind in ("int", "float"):
                values[p.key] = p.limits(True)[int(high)]
        d = forge.make(TID, values, seed=4, log=QUIET, advanced=True)
        assert np.isfinite(d.hm).all()
        forge.check(d)


def test_info_and_preview():
    json.dumps(get(TID).info())
    d = forge.make(TID, log=QUIET)
    assert forge.preview(d, size=256).size == (256, 256)
    # Conservative heavy-ship lanes have room beyond a single sample-wide path.
    mask = ndimage.binary_erosion(d.hm < -15, iterations=4)
    from atlasforge.checks import connected
    assert connected(mask, d.naval_starts[0][0], d.naval_starts[1][0])


def test_build(tmp_path):
    from atlasforge.config import ForgeConfig
    d = forge.make(TID, {"size": get(TID).param("size").choices[0]}, log=QUIET)
    info = forge.build(d, outdir=str(tmp_path), config=ForgeConfig(author="Test"), log=QUIET)
    assert info["bytes"] > 1_000_000
    with zipfile.ZipFile(info["path"]) as archive:
        assert "mapinfo.lua" in archive.namelist()
        assert any(name.endswith(".smf") for name in archive.namelist())
        assert any("metal" in name.lower() for name in archive.namelist())
    from atlasforge.watermark import verify
    assert verify(info["path"])["payload"]["template"] == TID


@pytest.mark.parametrize("size", (12, 20))
def test_regular_size_limits(size):
    d = forge.make(TID, {"size": size}, seed=1, log=QUIET)
    ok, lines = forge.check(d)
    assert ok, "\n".join(lines)


def test_safe_parameter_limits():
    for p in get(TID).params:
        if p.kind not in ("int", "float"):
            continue
        for value in p.limits():
            d = forge.make(TID, {p.key: value, "erosion": 0}, seed=1, log=QUIET)
            ok, lines = forge.check(d)
            assert ok, f"{p.key}={value}: " + "\n".join(lines)

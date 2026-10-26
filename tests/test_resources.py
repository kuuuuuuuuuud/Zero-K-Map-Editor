"""General settings: metal spot and geo counts, wind, tidal, explanations for every setting."""
import numpy as np
import pytest

from atlasforge import forge
from atlasforge.resources import WIND, parts
from atlasforge.templates import all_templates

QUIET = dict(log=lambda *a, **k: None)
FAST = {"erosion": 0, "rocks": 0, "wrecks": 0}


@pytest.mark.parametrize("tid, size", [("chokepoint", 12), ("arena", 16), ("open_sea", 16)])
@pytest.mark.parametrize("mex, geo", [(6, 0), (20, 2)])
def test_counts(tid, size, mex, geo):
    d = forge.make(tid, dict(FAST, size=size, mex_count=mex, geos=geo), seed=4, **QUIET)
    k = parts(d)
    assert len(d.mexes) / k == pytest.approx(mex, abs=0.5)
    assert len(d.geos) / k == pytest.approx(geo, abs=0.5)
    assert forge.check(d)[0]
    # symmetric: the heightmap stays mirrored after flattening new spots
    assert np.abs(d.hm - d.hm[:, ::-1]).max() < 0.5


def test_default_keeps_template():
    a = forge.make("river", dict(FAST, size=12), seed=2, **QUIET)
    b = forge.make("river", dict(FAST, size=12, mex_count=0, geos="default"), seed=2, **QUIET)
    assert len(a.mexes) == len(b.mexes) and len(a.geos) == len(b.geos)


def test_base_spots_stay():
    d = forge.make("chokepoint", dict(FAST, size=12, mex_count=1), seed=1, **QUIET)
    assert len(d.mexes) >= 2
    assert any("belong to the bases" in n for n in d.notes)


def test_wind_and_tidal():
    d = forge.make("chokepoint", dict(FAST, size=12, wind="storm", tidal=20), seed=1, **QUIET)
    assert tuple(d.biome["wind"]) == WIND["storm"]
    assert d.biome["tidal"] == 20


def test_every_setting_is_explained():
    for t in all_templates():
        for p in t.all_params():
            assert len(p.info) > 60, f"{t.id}.{p.key} needs an info text"
            assert p.to_dict()["info"] == p.info


def test_display_order():
    order = ("Map", "Resources", "Terrain", "")
    for t in all_templates():
        groups = [p.group for p in t.all_params()]
        idx = [order.index(g) for g in groups]
        assert idx == sorted(idx), t.id

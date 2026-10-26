"""Procedural families must vary geography, preserve openings and support each orientation."""
import numpy as np
import pytest
from scipy import ndimage

from atlasforge import forge, templates
from tools.template_workflow import load_template, validate_design

IDS = ("highlands", "watershed", "dune_sea")


@pytest.fixture(params=IDS)
def family(request, monkeypatch):
    t = load_template(request.param)
    monkeypatch.setitem(templates._REGISTRY, t.id, t)
    return t


def make(t, values=None, seed=1):
    return forge.make(t.id, dict(erosion=0, rocks=0, wrecks=0, **(values or {})), seed=seed, log=lambda *a: None)


def test_seeds_change_macro_geography(family):
    a, b = (make(family, seed=s) for s in (1, 7))
    small_a = ndimage.zoom(a.hm, 32 / len(a.hm), order=1)[:32, :32]
    small_b = ndimage.zoom(b.hm, 32 / len(b.hm), order=1)[:32, :32]
    delta = abs(small_a - small_b)
    assert delta.mean() > 15, (family.id, delta.mean())
    assert (delta > 15).mean() > 0.25, family.id
    high_a = small_a > np.percentile(small_a, 70)
    high_b = small_b > np.percentile(small_b, 70)
    assert (high_a & high_b).sum() / (high_a | high_b).sum() < 0.75


def test_forms_change_terrain_formula(family):
    forms = family.param("form").choices
    designs = [make(family, {"form": f}) for f in forms]
    for d in designs:
        ok, lines = forge.check(d)
        assert ok, "\n".join(lines)
    for i in range(len(designs)):
        for j in range(i):
            assert abs(designs[i].hm - designs[j].hm).mean() > 10


@pytest.mark.parametrize("layout", ("diag", "ns", "ew"))
def test_orientations_keep_complete_symmetry(family, layout):
    d = make(family, {"layout": layout}, seed=3)
    validate_design(d, "competitive")
    assert np.array_equal(d.hm, d.sym.mirror_grid(d.hm))
    assert forge.check(d)[0]


def test_openings_and_future_parameter_contract(family):
    d = make(family, seed=4)
    fixed = [m for m in d.mexes if m.get("fixed")]
    assert len(fixed) == 6
    assert sum(m["side"] == 0 for m in fixed) == 3
    assert all(m["metal"] == 2.0 for m in fixed)
    assert "mexes" not in [p.key for p in family.params]
    for p in family.params:
        assert p.group == ("Map" if p.key in ("size", "biome") else "")
        assert len(p.info.split(". ")) >= 2


@pytest.mark.parametrize("mex_count,geos", ((6, "0"), (6, "3"), (20, "0"), (20, "3")))
def test_general_resource_controls(family, mex_count, geos):
    d = make(family, {"mex_count": mex_count, "geos": geos}, seed=4)
    validate_design(d, "competitive")
    assert forge.check(d)[0]
    assert len([m for m in d.mexes if m.get("fixed")]) == 6
    assert len(d.mexes) == 2 * mex_count
    assert len(d.geos) == 2 * int(geos)


def test_every_setting_is_explained(family):
    for p in family.all_params():
        assert len(p.info) > 60
        assert p.to_dict()["info"] == p.info


def test_family_scale_changes_routes_and_landforms(family):
    key = {"highlands": "regions", "watershed": "branches", "dune_sea": "dune_bands"}[family.id]
    lo, hi = family.param(key).limits()
    a, b = make(family, {key: lo}), make(family, {key: hi})
    assert abs(a.hm - b.hm).mean() > 10

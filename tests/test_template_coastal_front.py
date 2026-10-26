"""Contract tests for coastal_front; add tests for its unique gameplay rules."""
import pytest
from atlasforge import templates
from tools.template_workflow import load_template, run_case, validate_design

TID = "coastal_front"

@pytest.fixture()
def template(monkeypatch):
    t = load_template(TID)
    monkeypatch.setitem(templates._REGISTRY, TID, t)
    return t

@pytest.mark.parametrize("seed", range(1, 11))
def test_defaults(template, seed):
    from atlasforge import forge
    d = forge.make(TID, seed=seed, log=lambda *a: None)
    validate_design(d, "naval")
    ok, lines = forge.check(d)
    assert ok, "\n".join(lines)

def test_repeatable(template):
    from atlasforge import forge
    import numpy as np
    a = forge.make(TID, {"erosion": 0}, seed=1, log=lambda *a: None)
    b = forge.make(TID, {"erosion": 0}, seed=1, log=lambda *a: None)
    assert np.array_equal(a.hm, b.hm)
    assert a.mexes == b.mexes and a.starts == b.starts and a.geos == b.geos

def test_seed_changes_microrelief(template):
    from atlasforge import forge
    import numpy as np
    a = forge.make(TID, {"erosion": 0}, seed=1, log=lambda *a: None)
    b = forge.make(TID, {"erosion": 0}, seed=2, log=lambda *a: None)
    assert not np.array_equal(a.hm, b.hm)

def test_parameter_extremes(template):
    from tools.template_workflow import parameter_cases
    for name, values, advanced in parameter_cases(template):
        row, _ = run_case(template, name, values, 1, advanced, "naval",
                          required_playable=not advanced)
        assert row["passed"], row

def test_info_and_preview(template):
    import json
    from atlasforge import forge
    json.dumps(template.info())
    d = forge.make(TID, seed=1, log=lambda *a: None)
    assert forge.preview(d, size=256).size == (256, 256)

# Full archive export and regression suite: run the workflow's release level.

@pytest.mark.parametrize("values", [
    {},
    {"size": 12, "land_share": 0.58, "headlands": 0.06, "depth": 320,
     "beach_slope": 10, "coast_noise": 100, "sea_metal": 0.8},
    {"size": 12, "land_share": 0.38, "headlands": 0.06, "depth": 100,
     "beach_slope": 18, "coast_noise": 100, "sea_metal": 0.3},
])
def test_land_front_and_wide_fleet_route_coexist(template, values):
    import numpy as np
    from scipy import ndimage
    from atlasforge import forge
    from atlasforge.checks import connected, unit_masks
    d = forge.make(TID, values, seed=7, log=lambda *a: None)
    ok, lines = forge.check(d)
    assert ok, "\n".join(lines)
    W = (d.hm.shape[0] - 1) * 8
    zz = np.arange(d.hm.shape[0])[:, None] * 8
    masks = unit_masks(d.hm)
    assert connected(masks["tanks"] & (zz < 0.28 * W), d.starts[0], d.starts[1])
    # A wide ship corridor, not just a one-cell connection between ports.
    deep_clear = ndimage.binary_erosion(masks["ships"], iterations=12)
    assert connected(deep_clear, d.naval_starts[0][0], d.naval_starts[1][0])
    assert any(d.hm[int(m["z"] / 8), int(m["x"] / 8)] > 60 for m in d.mexes)
    assert any(d.hm[int(m["z"] / 8), int(m["x"] / 8)] < -15 for m in d.mexes)

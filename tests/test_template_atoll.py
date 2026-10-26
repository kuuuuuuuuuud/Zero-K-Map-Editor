"""Contract tests for atoll; add tests for its unique gameplay rules."""
import pytest
from atlasforge import templates
from tools.template_workflow import load_template, run_case, validate_design

TID = "atoll"

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
    {"size": 12, "ring_radius": 0.32, "ring_width": 0.14, "passage_width": 400,
     "beach_slope": 10, "depth": 320, "coast_noise": 100, "sea_metal": 0.3},
    {"size": 12, "ring_radius": 0.28, "ring_width": 0.09, "passage_width": 800,
     "beach_slope": 18, "depth": 100, "coast_noise": 100, "sea_metal": 0.8},
])
def test_lagoon_and_outer_ocean_are_one_fleet_network(template, values):
    from scipy import ndimage
    from atlasforge import forge
    from atlasforge.checks import connected, unit_masks
    d = forge.make(TID, values, seed=5, log=lambda *a: None)
    ok, lines = forge.check(d)
    assert ok, "\n".join(lines)
    W = (d.hm.shape[0] - 1) * 8
    ships = ndimage.binary_erosion(unit_masks(d.hm)["ships"], iterations=6)
    port = d.naval_starts[0][0]
    for p in [(0.5 * W, 0.04 * W), (0.5 * W, 0.96 * W),
              (0.017 * W, 0.5 * W), (0.983 * W, 0.5 * W), d.naval_starts[1][0]]:
        assert connected(ships, port, p), p
    import numpy as np
    xx = np.arange(d.hm.shape[1])[None, :] * 8
    assert connected(ships & (xx < 0.08 * W), (0.017 * W, 0.12 * W), (0.017 * W, 0.88 * W))

def test_default_arcs_are_separated_and_can_be_landed_on(template):
    from atlasforge import forge
    from atlasforge.checks import connected, unit_masks
    d = forge.make(TID, seed=2, log=lambda *a: None)
    m = unit_masks(d.hm)
    assert not connected(m["tanks"], *d.starts)
    assert connected(m["amphibians"], *d.starts)
    assert connected(m["hovers"], *d.starts)
    assert 0.10 < (d.hm > 0).mean() < 0.50

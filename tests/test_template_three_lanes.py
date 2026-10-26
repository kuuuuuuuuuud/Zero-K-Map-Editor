"""Contract tests for three_lanes; add tests for its unique gameplay rules."""
import pytest
from atlasforge import templates
from tools.template_workflow import load_template, run_case, validate_design

TID = "three_lanes"

@pytest.fixture()
def template(monkeypatch):
    t = load_template(TID)
    monkeypatch.setitem(templates._REGISTRY, TID, t)
    return t

@pytest.mark.parametrize("seed", range(1, 11))
def test_defaults(template, seed):
    from atlasforge import forge
    d = forge.make(TID, seed=seed, log=lambda *a: None)
    validate_design(d, "competitive")
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
        row, _ = run_case(template, name, values, 1, advanced, "competitive",
                          required_playable=not advanced)
        assert row["passed"], row

def test_info_and_preview(template):
    import json
    from atlasforge import forge
    json.dumps(template.info())
    d = forge.make(TID, seed=1, log=lambda *a: None)
    assert forge.preview(d, size=256).size == (256, 256)

# Full archive export and regression suite: run the workflow's release level.

def test_three_independent_fronts_and_lateral_crossings(template):
    import numpy as np
    from atlasforge import forge
    from atlasforge.checks import connected, unit_masks
    d = forge.make(TID, {"erosion": 0}, seed=4, log=lambda *a: None)
    W = (d.hm.shape[0] - 1) * 8
    zz, xx = np.mgrid[:d.hm.shape[0], :d.hm.shape[1]] * 8
    tanks = unit_masks(d.hm)["tanks"]
    for z in (0.18 * W, 0.5 * W, 0.82 * W):
        assert connected(tanks & (abs(zz - z) < 0.10 * W), (0.18 * W, z), (0.82 * W, z))
    # Ridge tops block direct tank crossings far from the designed openings.
    narrow_mid = tanks & (abs(xx - 0.5 * W) < 0.035 * W)
    assert not connected(narrow_mid, (W / 2, 0.18 * W), (W / 2, 0.82 * W))
    for x in (0.28 * W, 0.72 * W):
        assert connected(tanks & (abs(xx - x) < 0.025 * W), (x, 0.18 * W), (x, 0.82 * W))
    d = forge.make(TID, {"central_crossing": True, "erosion": 0}, seed=4, log=lambda *a: None)
    assert connected(unit_masks(d.hm)["tanks"] & (abs(xx - W / 2) < 0.025 * W),
                     (W / 2, 0.18 * W), (W / 2, 0.82 * W))

def test_each_lane_has_contested_economy(template):
    from atlasforge import forge
    d = forge.make(TID, seed=8, log=lambda *a: None)
    W = (d.hm.shape[0] - 1) * 8
    for z in (0.18 * W, 0.5 * W, 0.82 * W):
        forward = [m for m in d.mexes if 0.40 * W < m["x"] < 0.60 * W and abs(m["z"] - z) < 0.06 * W]
        assert len(forward) >= 2
        assert all(m["metal"] > 2.5 for m in forward)

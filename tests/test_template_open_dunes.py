"""Contract tests for open_dunes; add tests for its unique gameplay rules."""
import pytest
from atlasforge import templates
from tools.template_workflow import load_template, run_case, validate_design

TID = "open_dunes"

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

@pytest.mark.parametrize('seed', (1, 3, 7))
def test_defaults_remain_open_for_mobile_armies(template, seed):
    from atlasforge import forge
    from atlasforge.checks import unit_masks
    d = forge.make(TID, {'erosion': 0}, seed=seed, log=lambda *a: None)
    assert (d.hm > 0).all()
    assert unit_masks(d.hm)['tanks'].mean() > 0.93
    assert d.hm.std() < 30


@pytest.mark.parametrize('mex_count,geos', ((6, 0), (6, 3), (20, 0), (20, 3)))
def test_general_resource_controls(template, mex_count, geos):
    from atlasforge import forge
    d = forge.make(TID, {'erosion': 0, 'mex_count': mex_count, 'geos': geos}, seed=4, log=lambda *a: None)
    assert forge.check(d)[0]
    assert len(d.mexes) == mex_count * 2
    assert len(d.geos) == geos * 2
    assert sum(m.get('fixed', False) for m in d.mexes) == 6
    for p in template.all_params():
        assert len(p.info) > 60

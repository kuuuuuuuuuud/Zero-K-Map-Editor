"""Contract tests for river_delta; add tests for its unique gameplay rules."""
import pytest
from atlasforge import templates
from tools.template_workflow import load_template, run_case, validate_design

TID = "river_delta"

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

@pytest.mark.parametrize('crossing_type', ('fords','causeways'))
@pytest.mark.parametrize('relief', (.5,1,1.6))
def test_each_crossing_is_usable_at_safe_relief(template,crossing_type,relief):
    from atlasforge import forge
    from atlasforge.checks import connected,unit_masks
    from atlasforge.templates.river_delta import crossing_rows
    d=forge.make(TID, {'erosion':0,'crossing_type':crossing_type,'relief':relief},seed=3,log=lambda *a:None)
    tanks=unit_masks(d.hm)['tanks']
    if crossing_type=='causeways':tanks &= d.hm>6
    W=d.sym.W
    for k,z in enumerate(crossing_rows(d.values,W)):
        assert connected(tanks & dict(d.gates)[f'Delta crossing {k+1}'],(.12*W,z),(.88*W,z))


def test_delta_contains_contested_dry_islands(template):
    from scipy import ndimage
    from atlasforge import forge
    d=forge.make(TID, {'erosion':0},seed=1,log=lambda *a:None)
    land=d.hm>6
    labels,count=ndimage.label(land)
    sizes=ndimage.sum(land,labels,range(1,count+1))
    assert sum(sizes>500)>=4
    assert (d.hm < -22).mean()>.02


@pytest.mark.parametrize('mex_count,geos', ((6,0),(6,3),(20,0),(20,3)))
def test_general_resource_controls(template,mex_count,geos):
    from atlasforge import forge
    d=forge.make(TID, {'erosion':0,'mex_count':mex_count,'geos':geos},seed=4,log=lambda *a:None)
    assert forge.check(d)[0]
    assert len(d.mexes)==2*mex_count
    assert len(d.geos)==2*geos
    assert sum(m.get('fixed',False) for m in d.mexes)==6
    for p in template.all_params():assert len(p.info)>60

"""Contract tests for fjord_coast; add tests for its unique gameplay rules."""
import pytest
from atlasforge import templates
from tools.template_workflow import load_template, run_case, validate_design

TID = "fjord_coast"

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

@pytest.mark.parametrize('fjords',(2,3,4))
@pytest.mark.parametrize('seed',(1,7))
def test_each_safe_inlet_count_has_fleet_access(template,fjords,seed):
    from atlasforge import forge
    from atlasforge.checks import connected,unit_masks
    d=forge.make(TID,{'erosion':0,'fjords':fjords},seed=seed,log=lambda *a:None)
    ok,lines=forge.check(d)
    assert ok,'\n'.join(lines)
    assert len(d.gates)==2*fjords
    ships=unit_masks(d.hm)['ships']
    for x,z,label,_ in d.marks:
        if label.startswith('Fjord '):assert connected(ships,d.naval_starts[0][0],(x,z))
    assert all('yes' in n for n in d.notes if n.startswith('Fleet access'))


@pytest.mark.parametrize('mex_count,geos',((6,0),(6,3),(20,0),(20,3)))
def test_general_resource_controls(template,mex_count,geos):
    from atlasforge import forge
    d=forge.make(TID,{'erosion':0,'mex_count':mex_count,'geos':geos},seed=4,log=lambda *a:None)
    assert forge.check(d)[0]
    assert len(d.mexes)==2*mex_count
    assert len(d.geos)==2*geos
    assert sum(m.get('fixed',False) for m in d.mexes)==6
    for p in template.all_params():assert len(p.info)>60


@pytest.mark.parametrize('seed',(1,7))
def test_fjord_shore_joins_remain_smooth(template,seed):
    from tools.naval_quality import inspect_design
    _,_,metrics=inspect_design(TID,seed)
    for kind,m in metrics.items():
        if kind=='flank_contacts' and m['candidates']==0:continue
        assert m['samples']>=100,(kind,m)
        assert m['ratio']<=1.5,(kind,m)


@pytest.mark.parametrize('seed',(1,5,7))
def test_small_deep_map_with_four_narrow_long_inlets(template,seed):
    from atlasforge import forge
    d=forge.make(TID,dict(size=12,depth=320,beach_slope=10,coast_noise=100,fjords=4,
                         fjord_reach=1200,fjord_width=800,coast_depth=.30,sea_metal=.8,
                         erosion=0),seed=seed,log=lambda *a:None)
    ok,lines=forge.check(d)
    assert ok,'\n'.join(lines)

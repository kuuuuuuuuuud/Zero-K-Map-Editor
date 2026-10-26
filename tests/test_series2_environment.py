"""Series two uses the published common biome, lighting, sky and grass controls."""
import pytest

from atlasforge import forge,templates
from tools.template_workflow import load_template,validate_design

IDS=('open_dunes','twin_plateaus','lake_district','river_delta','fjord_coast')


@pytest.mark.parametrize('tid',IDS)
@pytest.mark.parametrize('biome,sun,sky,grass',(
    ('jungle','morning','painted',2),
    ('swamp','evening','engine',0),
    ('industrial','noon','painted',1),
))
def test_published_environment_settings(monkeypatch,tid,biome,sun,sky,grass):
    t=load_template(tid)
    monkeypatch.setitem(templates._REGISTRY,tid,t)
    keys=[p.key for p in t.all_params()]
    assert len(keys)==len(set(keys))
    d=forge.make(tid,dict(biome=biome,sun=sun,sky=sky,grass=grass,erosion=0),seed=4,log=lambda *a:None)
    validate_design(d,'naval' if tid=='fjord_coast' else 'competitive')
    assert forge.check(d)[0]
    assert 'sundir' in d.biome
    assert d.biome.get('grass_mul',1)==grass
    if sky=='engine':assert d.biome['skybox'] is False
    if tid=='fjord_coast':assert d.biome['water_damage']==0
    for p in t.all_params():assert p.to_dict()['info'] and len(p.info)>60

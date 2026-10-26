"""Every template designs a valid map with its defaults and passes its own checks; parameters validate."""
import pytest

from atlasforge import forge
from atlasforge.templates import all_templates, get

SMALL = {"skirmish": {"size": 8}, "chokepoint": {"size": 12}, "river": {"size": 12}, "arena": {"size": 12},
         "volcano": {}, "chicken": {"size": 16}, "open_sea": {"size": 16}, "archipelago": {"size": 16},
         "straits": {"size": 16}, "ffa_ring": {"size": 16, "players": 4}}


@pytest.mark.parametrize("tid", [t.id for t in all_templates()])
def test_template_designs_and_checks(tid):
    d = forge.make(tid, SMALL.get(tid, {}), seed=3, log=lambda *a: None)
    ok, lines = forge.check(d)
    assert ok, "\n".join(lines)
    assert d.mexes and d.starts and len(d.teams) >= 2
    img = forge.preview(d, size=256)
    assert img.size == (256, 256)
    for path, code in d.extra_files.items():
        assert path.startswith(("mapconfig/", "LuaRules/Gadgets/", "features/", "objects3d/", "unittextures/")), path


def test_parameters_are_checked():
    t = get("chokepoint")
    assert t.resolve({"gates": "2"})["gates"] == 2
    with pytest.raises(ValueError):
        t.resolve({"gates": 9})
    with pytest.raises(KeyError):
        t.resolve({"nonsense": 1})
    with pytest.raises(ValueError):
        get("river").resolve({"mode": "magma"})
    assert get("arena").resolve({"lava_tops": "yes"})["lava_tops"] is True


def test_template_info_is_serialisable():
    import json
    json.dumps([t.info() for t in all_templates()])


def test_volcano_bombs_hit_solid_ground():
    import re
    d = forge.make("volcano", {"bomb_radius": 400}, seed=5, log=lambda *a: None)
    conf = d.extra_files["mapconfig/atlas_eruption.lua"]
    assert "bombRadius = 400" in conf
    pts = [(int(x), int(z)) for x, z in re.findall(r"\{(\d+), (\d+)\}", conf.split("islandTargets")[1].split("causeways")[0])]
    assert len(pts) > 300
    assert all(d.hm[z // 8, x // 8] > 46 + 15 for x, z in pts)   # above the flood line, never in the lava


def test_build_small_template(tmp_path):
    from atlasforge.config import ForgeConfig
    d = forge.make("chokepoint", {"size": 12, "gates": 2}, seed=1, log=lambda *a: None)
    info = forge.build(d, outdir=str(tmp_path), config=ForgeConfig(author="Test"), log=lambda *a: None)
    assert info["name"] == "Forge Chokepoint Front v1"
    assert info["template"] == "chokepoint"
    from atlasforge import watermark                       # hidden mark is in every built map
    r = watermark.verify(info["path"])
    assert r["forge"] and r["confidence"] == "certain"
    assert r["payload"]["template"] == "chokepoint" and r["payload"]["seed"] == 1

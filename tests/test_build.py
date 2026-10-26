"""Build a small procedural map and check the archive; compile every Lua file the forge writes."""
import os
import struct
import zipfile

import numpy as np
import pytest

from atlasforge import gadgets
from atlasforge.checks import report, unit_masks
from atlasforge.config import ForgeConfig
from atlasforge.procedural import generate
from atlasforge.terrain import grid, plateau


def lua_compile(code):
    lupa = pytest.importorskip("lupa")
    lua = lupa.LuaRuntime()
    ok, err = lua.eval("function(s) local f, e = load(s); return f ~= nil, e end")(code)
    assert ok, err


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("maps")
    cfg = ForgeConfig(author="Test")
    info = generate("Test Hills", (4, 4), seed=3, biome="temperate", style="hills", outdir=str(out), config=cfg,
                    log=lambda *a: None)
    return info


def test_archive_contents(built):
    assert built["name"] == "Forge Test Hills v1"
    with zipfile.ZipFile(built["path"]) as z:
        names = set(z.namelist())
        for f in ("mapinfo.lua", "maps/Forge_Test_Hills_v1.smf", "maps/Forge_Test_Hills_v1.smt",
                  "maps/minimap_ingame.dds", "mapconfig/map_metal_layout.lua", "mapconfig/map_startboxes.lua"):
            assert f in names, f
        mi = z.read("mapinfo.lua").decode()
        assert 'name        = "Forge Test Hills v1"' in mi
        assert "Made with Atlas Map Forge." in mi
        smf = z.read("maps/Forge_Test_Hills_v1.smf")
        hdr = struct.unpack("<16s7i2f7i", smf[:80])
        assert hdr[0].startswith(b"spring map file") and hdr[3] == 256 and hdr[4] == 256
        for f in names:
            if f.endswith(".lua"):
                lua_compile(z.read(f).decode())
    assert built["mexes"] >= 6
    assert os.path.exists(built["preview"])


def test_gadget_sources_compile():
    for f in ("lua_lava_cliffs.lua", "lua_tide_warning.lua", "lua_eruption.lua"):
        lua_compile(gadgets._lua(f))
    for files in (gadgets.tide_files([(0, 0, 100, 100)], 60),
                  gadgets.eruption_files((512, 512), 100, 400, 500, 46, [[(0, 0), (10, 0), (10, 10), (0, 10)]])):
        for path, code in files.items():
            lua_compile(code)
    lua_compile(gadgets.lava_config(60))


def test_wall_blocks_tanks_and_becomes_lava_cliff():
    n = 257
    h = np.full((n, n), 100.0, np.float32)
    xx, zz = grid(n)
    plateau(h, np.abs(xx - 1024) - 150, 400, side_deg=74)          # north-south wall through the middle
    team0, team1 = [(300.0, 1024.0)], [(1748.0, 1024.0)]
    ok, lines = report(h, team0, team1)
    assert not ok and lines[0].startswith("Tanks") and "NO" in lines[0]
    assert unit_masks(h)["spiders"][128, 128]
    mask = gadgets.lava_cliff_mask(h, team0 + team1)
    assert mask[128, 128] and not mask[128, 30]
    files, cells = gadgets.lava_cliff_files(mask)
    assert cells > 0 and "mapconfig/atlas_lava_cliffs.lua" in files


def test_config_names():
    assert ForgeConfig(author="A").map_name("Ridge", 2) == "Forge Ridge v2"     # prefix is fixed
    assert ForgeConfig().describe("Hills.") == "Hills. Made with Atlas Map Forge."
    with pytest.raises(ValueError):
        ForgeConfig().require_author()
    with pytest.raises(ValueError):
        ForgeConfig(author='bad"name').validate()


def test_set_box_edit_is_in_the_archive(tmp_path):
    from atlasforge.app.luatable import startboxes
    from atlasforge.edits import apply_edits
    from atlasforge import forge
    from atlasforge.forge import build
    d = forge.make("arena", {"size": 12, "erosion": 0}, seed=2, log=lambda *a: None)
    poly = [[100.0, 100.0], [700.0, 100.0], [700.0, 700.0], [100.0, 700.0]]
    d, problems = apply_edits(d, [{"op": "set_box", "team": 0, "poly": 0, "points": poly}], symmetry=False)
    assert problems == []
    info = build(d, outdir=str(tmp_path), log=lambda *a: None, preview=False)
    with zipfile.ZipFile(info["path"]) as z:
        lua = z.read("mapconfig/map_startboxes.lua").decode()
    assert startboxes(lua)[0]["polygons"][0] == poly

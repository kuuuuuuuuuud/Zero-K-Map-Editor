"""Surface types (Water / Lava / Void) are self-contained and selectable.

The Forge Editor's "Blank Sand" template writes the mapinfo.lua water table
(and, for void maps, the LuaRules/Gadgets/void_death.lua gadget) entirely on its
own - no manual mapinfo.lua edits are needed. See atlasforge/surfaces.py.
"""
import zipfile

import pytest

from atlasforge import forge
from atlasforge.biomes import BIOMES
from atlasforge.config import ForgeConfig
from atlasforge.editor import flat_sand_design
from atlasforge.formats import lua_syntax_check, mapinfo_lua
from atlasforge.surfaces import (SURFACES, SURFACE_LABELS, VOID_GADGET, surface_extra_files,
                                 surface_key, surface_water)

STARTS = [(0, 128), (1024, 128)]
BIOME = BIOMES["desert"]
QUIET = lambda *a, **k: None


def _mi(surface):
    return mapinfo_lua("Surface", "d", "A", 0.0, 200.0, "t.smt", STARTS, BIOME, 0.0, "t.smf",
                       water=surface_water(surface))


@pytest.mark.parametrize("key,label", list(zip(SURFACES, SURFACE_LABELS)))
def test_surface_key_normalises_labels_and_keys(key, label):
    assert surface_key(key) == key
    assert surface_key(label) == key


def test_surface_key_rejects_unknown():
    with pytest.raises(ValueError):
        surface_key("magma")


def test_water_surface():
    w = surface_water("water")
    assert w["voidwater"] is False and w["damage"] == 0.0 and w["waterlevel"] == 0.0
    assert w["plane"] == (0.05, 0.2, 0.3)
    mi = _mi("water")
    assert "voidwater       = false" in mi and "damage         = 0.0" in mi
    assert "planecolor     = {0.050, 0.200, 0.300}" in mi
    ok, msg = lua_syntax_check(mi)
    assert ok, msg


def test_lava_surface():
    w = surface_water("lava")
    assert w["voidwater"] is False and w["damage"] == 100.0 and w["waterlevel"] == 0.0
    assert w["plane"] == (0.9, 0.3, 0.05)
    mi = _mi("lava")
    assert "voidwater       = false" in mi and "damage         = 100.0" in mi
    assert "planecolor     = {0.900, 0.300, 0.050}" in mi
    assert "surfacecolor   = {1.000, 0.450, 0.100}" in mi
    ok, msg = lua_syntax_check(mi)
    assert ok, msg


def test_void_surface_and_gadget():
    w = surface_water("void")
    assert w["voidwater"] is True and w["damage"] == 0.0
    assert w["plane"] is None
    mi = _mi("void")
    assert "voidwater       = true" in mi and "planecolor" not in mi
    ok, msg = lua_syntax_check(mi)
    assert ok, msg
    files = surface_extra_files("void")
    assert files["LuaRules/Gadgets/void_death.lua"] == VOID_GADGET
    assert "VOID_Y" in VOID_GADGET and "Spring.DestroyUnit" in VOID_GADGET
    assert surface_extra_files("water") == {} and surface_extra_files("lava") == {}


def test_water_colours_always_written():
    # Task 4: every surface writes the full water colour table, never black defaults.
    for s in SURFACES:
        mi = _mi(s)
        for token in ("basecolor", "mincolor", "surfacecolor", "specularcolor", "absorb"):
            assert token in mi, (s, token)


def test_flat_sand_design_surface_wiring():
    for s in SURFACES:
        d = flat_sand_design(16, 4, seed=1, surface=s, log=QUIET)
        assert d.water == surface_water(s)
        assert d.extra_files == surface_extra_files(s)
        assert d.values["surface"] == s


def test_editor_template_exposes_surface_choice():
    from atlasforge.templates import get
    t = get("editor")
    p = t.param("surface")
    assert p.kind == "choice" and p.default == "None (Dry)"
    assert list(p.choices) == list(SURFACE_LABELS)
    for label, key in zip(SURFACE_LABELS, SURFACES):
        v = t.resolve(dict(surface=label))
        d = t.make(v, seed=1, log=QUIET)
        assert d.values["surface"] == key
        assert d.water == surface_water(key)


def test_build_packs_surface_water_table_and_void_gadget(tmp_path):
    cfg = ForgeConfig(author="Test")
    expect_gadget = {"water": False, "lava": False, "void": True}
    for s in ("water", "lava", "void"):
        d = flat_sand_design(16, 4, seed=1, surface=s, log=QUIET)
        info = forge.build(d, outdir=str(tmp_path), title=f"Surf {s}", version=1, config=cfg,
                           log=QUIET, preview=False)
        with zipfile.ZipFile(info["path"]) as z:
            names = z.namelist()
            mi = z.read("mapinfo.lua").decode("utf8")
        has_gadget = "LuaRules/Gadgets/void_death.lua" in names
        assert has_gadget is expect_gadget[s]
        # the full water colour table made it through the real pipeline
        assert "basecolor" in mi and "mincolor" in mi and "surfacecolor" in mi
        if s == "lava":
            assert "damage         = 100.0" in mi
        else:
            assert "damage         = 0.0" in mi

"""Cliff terrain type: steep SMF typemap cells read as type 1 and mapinfo.lua carries the Cliff entry."""
import numpy as np

from atlasforge.archive import CLIFF_SLOPE_DEG, _typemap_slope
from atlasforge.biomes import BIOMES
from atlasforge.formats import lua_syntax_check, mapinfo_lua

STARTS = [(0, 128), (1024, 128)]


def test_mapinfo_cliff_entry_non_void():
    mi = mapinfo_lua("Slope Test", "desc", "Author", 0.0, 500.0, "t.smt", STARTS,
                     BIOMES["desert"], 0.0, "t.smf")
    assert "Cliff" in mi and "[1] =" in mi
    assert "tank = 0.5" in mi and "kbot = 0.7" in mi
    assert "hover = 1.0" in mi and "ship = 0.0" in mi
    ok, msg = lua_syntax_check(mi)
    assert ok, msg


def test_mapinfo_cliff_entry_void_biome():
    mi = mapinfo_lua("T2", "d", "A", -50.0, 200.0, "t.smt", STARTS,
                     BIOMES["asteroid"], 0.0, "t.smf")
    assert "Cliff" in mi and "[255] =" in mi
    ok, msg = lua_syntax_check(mi)
    assert ok, msg


def test_typemap_slope_shape_and_flat():
    nz = nx = 128
    hm = np.zeros((nz + 1, nx + 1), np.float32)
    sl = _typemap_slope(hm)
    assert sl.shape == (nz // 2, nx // 2)
    assert float(sl.max()) < 1.0


def test_typemap_slope_detects_wall():
    nz = nx = 128
    hm = np.zeros((nz + 1, nx + 1), np.float32)
    hm[:, 64:72] = 80.0                                   # ~84 deg flanks
    sl = _typemap_slope(hm)
    typemap = (sl >= CLIFF_SLOPE_DEG).astype(np.uint8)
    assert 0 < typemap.sum() < typemap.size


def test_typemap_slope_survives_16bit_quantisation():
    nz = nx = 128
    hm = np.zeros((nz + 1, nx + 1), np.float32)
    hm[:, 64:72] = 80.0
    hmin, hmax = float(hm.min()), float(hm.max())
    hm16 = np.clip(np.round((hm - hmin) / (hmax - hmin) * 65535), 0, 65535).astype(np.uint16)
    hmq = hm16.astype(np.float32) / 65535 * (hmax - hmin) + hmin
    assert (_typemap_slope(hmq) >= CLIFF_SLOPE_DEG).any()

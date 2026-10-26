"""Biomes, sky box, grass map and sun direction."""
import re
import struct
import zipfile

import numpy as np
import pytest

from atlasforge import forge, watermark
from atlasforge.biomes import BIOMES, GROUND_MAT
from atlasforge.config import ForgeConfig
from atlasforge.sky import panorama

QUIET = dict(log=lambda *a, **k: None)
REQUIRED = ("bed", "shore", "low", "mid", "high", "rock", "cliff", "peak", "patch", "sun", "sky", "fog", "gamb",
            "gdif", "water_base", "water_min", "water_surf", "wind", "trees", "tree_density", "peak_level")


@pytest.mark.parametrize("name", sorted(BIOMES))
def test_biome_complete(name):
    b = BIOMES[name]
    assert all(k in b for k in REQUIRED), [k for k in REQUIRED if k not in b]
    assert name in GROUND_MAT
    img = panorama(b, seed=1, width=256)
    assert img.shape == (128, 256, 3)
    top, horizon = img[:8].mean(), img[60:68].mean()
    assert abs(top - horizon) < 120                     # a sky, not noise


def test_new_biomes_present():
    assert {"jungle", "swamp", "industrial"} <= set(BIOMES)


def test_sun_presets_change_light():
    a = forge.make("chokepoint", {"size": 12, "erosion": 0}, seed=1, **QUIET)
    b = forge.make("chokepoint", {"size": 12, "erosion": 0, "sun": "evening"}, seed=1, **QUIET)
    assert "sundir" in b.biome and b.biome["sundir"][1] < 0.4
    assert b.biome["sun"][2] < a.biome["sun"][2]          # warmer evening light


@pytest.mark.parametrize("biome, grass", [("swamp", True), ("industrial", False)])
def test_build_sky_and_grass(tmp_path, biome, grass):
    d = forge.make("chokepoint", {"size": 12, "biome": biome, "erosion": 0, "grass": 1.0, "rocks": 0, "wrecks": 0}, seed=1, **QUIET)
    info = forge.build(d, outdir=str(tmp_path), config=ForgeConfig(author="Test"), log=lambda *a: None)
    with zipfile.ZipFile(info["path"]) as z:
        names = z.namelist()
        mi = z.read("mapinfo.lua").decode()
        smf = z.read([n for n in names if n.endswith(".smf")][0])
    assert "maps/skybox.jpg" in names and 'skybox       = "skybox.jpg"' in mi
    hdr = struct.unpack("<16s7i2f7i", smf[:80])
    nx, nz, n_extra = hdr[3], hdr[4], hdr[-1]
    assert n_extra == (1 if grass else 0)
    if grass:
        size, typ, pos = struct.unpack("<3i", smf[80:92])
        assert (size, typ) == (12, 1)
        g = np.frombuffer(smf[pos:pos + nx // 4 * nz // 4], np.uint8)
        assert len(g) == nx // 4 * nz // 4 and 0.05 < (g > 0).mean() < 0.8
        assert "grassShadingTex" in mi and re.search(r"bladeColor\s*=", mi)
    assert watermark.verify(info["path"])["forge"]


def test_engine_sky_option(tmp_path):
    d = forge.make("chokepoint", {"size": 12, "sky": "engine", "grass": 0, "erosion": 0}, seed=1, **QUIET)
    info = forge.build(d, outdir=str(tmp_path), config=ForgeConfig(author="Test"), log=lambda *a: None)
    with zipfile.ZipFile(info["path"]) as z:
        assert "maps/skybox.jpg" not in z.namelist()
        assert "skybox" not in z.read("mapinfo.lua").decode()
        smf = z.read([n for n in z.namelist() if n.endswith(".smf")][0])
    assert struct.unpack("<16s7i2f7i", smf[:80])[-1] == 0

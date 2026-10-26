"""Asteroid template: void around the rock, identical sectors, low gravity, space sky."""
import struct
import zipfile

import numpy as np
import pytest

from atlasforge import forge, watermark
from atlasforge.config import ForgeConfig

QUIET = dict(log=lambda *a, **k: None)
FAST = {"erosion": 0, "rocks": 0, "wrecks": 0}


@pytest.mark.parametrize("vals", [{}, {"players": 3, "size": 18, "centre": "mesa"},
                                  {"players": 4, "size": 20, "relief": 520}, {"centre": "flat", "edge": 1.2}])
@pytest.mark.parametrize("seed", [1, 4])
def test_asteroid_checks(vals, seed):
    d = forge.make("asteroid", dict(FAST, **vals), seed=seed, **QUIET)
    ok, lines = forge.check(d)
    assert ok, "\n".join(lines)
    n = vals.get("players", 2)
    assert len(d.starts) == n and len(d.mexes) % n == 0
    assert d.blocked is not None and d.blocked.mean() > 0.2          # space around the rock
    assert d.biome["void"] and d.biome["gravity"] == 80


def test_asteroid_build(tmp_path):
    d = forge.make("asteroid", dict(FAST, size=12), seed=2, **QUIET)
    info = forge.build(d, outdir=str(tmp_path), config=ForgeConfig(author="Test"), log=lambda *a: None)
    with zipfile.ZipFile(info["path"]) as z:
        mi = z.read("mapinfo.lua").decode()
        smf = z.read([n for n in z.namelist() if n.endswith(".smf")][0])
        assert "maps/skybox.jpg" in z.namelist()
    assert "voidwater       = true" in mi and "gravity         = 80" in mi and "[255]" in mi
    assert "planecolor" not in mi                 # no water plane over the lower sky
    assert "damage         = 2000" in mi          # the void destroys what goes down there
    h = struct.unpack("<16s7i2f7i", smf[:80])
    nx, nz, type_ptr = h[3], h[4], h[11]
    typ = np.frombuffer(smf[type_ptr:type_ptr + nx // 2 * nz // 2], np.uint8)
    assert 0.2 < (typ == 255).mean() < 0.8
    assert watermark.verify(info["path"])["payload"]["template"] == "asteroid"

"""Rocks, crystals and wrecks: models, feature definitions, symmetric placement, archive contents."""
import math
import zipfile

import numpy as np

from atlasforge import forge
from atlasforge.models import crystal_mesh, feature_pack, read_s3o, rock_mesh, s3o_bytes


def test_s3o_round_trip_and_outward_faces():
    rng = np.random.default_rng(3)
    for v, n, uv, f in (rock_mesh(rng, 40), crystal_mesh(rng, 30)):
        fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
        assert ((fn * n[f].mean(1)).sum(1) > 0).mean() > 0.99          # winding matches the normals (S3O rule)
        radius, height, v2, f2, t1, t2 = read_s3o(s3o_bytes(v, n, uv, f, "a.png", "b.png"))
        assert np.allclose(v2, v) and (f2 == f).all() and t1 == "a.png" and height > 0


def test_feature_pack_lua():
    from atlasforge.biomes import BIOMES
    files, kinds = feature_pack("alien", BIOMES["alien"], np.random.default_rng(1))
    assert any(k.family == "crystal" for k in kinds.values())
    lua = files["features/forge_rocks.lua"].decode()
    import lupa
    defs = lupa.LuaRuntime().execute(lua)
    for name in kinds:
        assert defs[name]["object"] == f"{name}.s3o" and f"objects3d/{name}.s3o" in files


def test_placement_is_symmetric_and_keeps_bases_free():
    d = forge.make("chokepoint", {"size": 12, "rocks": 1.5, "wrecks": 1.0}, seed=4, log=lambda *a: None)
    assert d.features
    W = (d.hm.shape[1] - 1) * 8
    pts = {(n, round(x), round(z)) for n, x, z, _ in d.features}
    for n, x, z in pts:                                                # every feature has its mirror image
        assert any(n2 == n and abs(W - x - x2) <= 1 and abs(z - z2) <= 1 for n2, x2, z2 in pts)
    for n, x, z, _ in d.features:
        assert all(math.hypot(x - sx, z - sz) > 700 for sx, sz in d.starts)
        assert all(math.hypot(x - m["x"], z - m["z"]) > 150 for m in d.mexes)
    assert any(l.startswith("Reclaim") for l in d.notes)


def test_build_contains_feature_files(tmp_path):
    from atlasforge.config import ForgeConfig
    d = forge.make("skirmish", {"size": 8, "rocks": 1.0, "wrecks": 1.0}, seed=2, log=lambda *a: None)
    info = forge.build(d, outdir=str(tmp_path), config=ForgeConfig(author="T"), log=lambda *a: None, preview=False)
    names = zipfile.ZipFile(info["path"]).namelist()
    assert "features/forge_rocks.lua" in names and any(n.startswith("objects3d/forge_rock") for n in names)
    assert "unittextures/forge_rock1.png" in names

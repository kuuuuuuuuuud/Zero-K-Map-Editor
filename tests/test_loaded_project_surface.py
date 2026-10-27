"""Regression: surface types and the Cliff typemap work for LOADED (old) projects.

Old editor projects predate the ``surface`` feature and have no ``surface`` key in
``values``. Loading must default it, and building the restored design must apply
both the surface water table and the slope-based Cliff typemap - independent of
when the project was created.
"""
import json
import struct
import zipfile

import numpy as np
import pytest

from atlasforge import forge
from atlasforge.app.server import Forge
from atlasforge.archive import CLIFF_SLOPE_DEG, _typemap_slope
from atlasforge.surfaces import SURFACE_LABEL_BY_KEY, surface_label
from atlasforge.templates import get

QUIET = lambda *a, **k: None


def test_surface_label_maps_keys_to_labels():
    assert surface_label("water") == "Water"
    assert surface_label("Void (Death Pit)") == "Void (Death Pit)"
    assert SURFACE_LABEL_BY_KEY["void"] == "Void (Death Pit)"
    with pytest.raises(ValueError):
        surface_label("magma")


def test_editor_template_resolve_accepts_keys_and_labels():
    t = get("editor")
    assert t.resolve({"surface": "lava"})["surface"] == "Lava"
    assert t.resolve({"surface": "Void (Death Pit)"})["surface"] == "Void (Death Pit)"
    assert t.resolve({})["surface"] == "None (Dry)"


@pytest.fixture()
def forge_state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    fs = Forge()
    fs.set_config(dict(projdir=str(tmp_path / "projects"),
                       outdir=str(tmp_path / "out"), author="Tester"))
    return fs, tmp_path


def _write_old_project(tmp_path, title, values):
    proj = tmp_path / "projects"
    proj.mkdir(exist_ok=True)
    hm = np.full((4 * 64 + 1, 16 * 64 + 1), 50.0, dtype=np.float32)
    hm[48:208, 320:704] = 260.0                    # steep plateau -> Cliff typemap cells
    name = title.replace(" ", "_")
    np.save(proj / f"{name}.heightmap.npy", hm)
    data = {
        "format": "atlas-forge-project",
        "version": 1,
        "app_version": "0.4.20",
        "template": "editor",
        "values": dict(values),
        "seed": 7,
        "symmetry": True,
        "edits": [],
        "title": title,
        "author": "Tester",
        "description": "old-format project",
        "heightmap_path": f"{name}.heightmap.npy",
    }
    path = proj / f"{name}.forge.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _typemap_from_sdz(sdz):
    with zipfile.ZipFile(sdz) as z:
        names = z.namelist()
        mi = z.read("mapinfo.lua").decode("utf-8")
        smf = next(n for n in names if n.endswith(".smf"))
        with z.open(smf) as f:
            head = f.read(80)
            n_extra = struct.unpack("<i", head[76:80])[0]
            if n_extra:
                f.read(12 * n_extra)
            f.read((16 * 64 + 1) * (4 * 64 + 1) * 2)
            tm = np.frombuffer(f.read((4 * 64 // 2) * (16 * 64 // 2)), dtype=np.uint8)
    return mi, names, tm.reshape(4 * 64 // 2, 16 * 64 // 2)


def test_project_load_defaults_surface_for_old_editor_project(forge_state):
    fs, tmp_path = forge_state
    path = _write_old_project(tmp_path, "Old Dry", {"width": 16, "height": 4})
    res = fs._project_load({"path": str(path)})
    assert res["project"]["values"]["surface"] == "None (Dry)"
    assert res["design"]["values"]["surface"] == "None (Dry)"


def test_loaded_project_build_applies_surface_and_cliff(forge_state):
    fs, tmp_path = forge_state
    path = _write_old_project(tmp_path, "Old Void",
                              {"width": 16, "height": 4, "surface": "Void (Death Pit)"})
    res = fs._project_load({"path": str(path)})
    design = fs.entry(res["design"]["id"]).design
    info = forge.build(design, outdir=str(tmp_path / "out"), title="Old Void",
                       version=1, log=QUIET, preview=False, author="Tester")
    mi, names, tm = _typemap_from_sdz(info["path"])
    # void surface -> no water plane, water level at the pit floor, death gadget packed
    assert "voidwater       = true" in mi
    assert "waterlevel     = 0" in mi
    assert "LuaRules/Gadgets/void_death.lua" in names
    # steep painted walls must be marked Cliff in the SMF typemap
    cliff = int((tm == 1).sum())
    assert cliff > 0
    hmin, hmax = float(design.hm.min()), float(design.hm.max())
    hmq = (np.clip(np.round((design.hm - hmin) / (hmax - hmin) * 65535), 0, 65535)
           .astype(np.uint16).astype(np.float32) / 65535 * (hmax - hmin) + hmin)
    assert cliff == int((_typemap_slope(hmq) >= CLIFF_SLOPE_DEG).sum())


def test_loaded_project_build_applies_water_surface(forge_state):
    fs, tmp_path = forge_state
    path = _write_old_project(tmp_path, "Old Water",
                              {"width": 16, "height": 4, "surface": "water"})
    res = fs._project_load({"path": str(path)})
    assert res["project"]["values"]["surface"] == "Water"
    design = fs.entry(res["design"]["id"]).design
    info = forge.build(design, outdir=str(tmp_path / "out"), title="Old Water",
                       version=1, log=QUIET, preview=False, author="Tester")
    mi, names, _ = _typemap_from_sdz(info["path"])
    assert "voidwater       = false" in mi
    assert "waterlevel     = 0" in mi
    assert "damage         = 0.0" in mi
    assert "LuaRules/Gadgets/void_death.lua" not in names

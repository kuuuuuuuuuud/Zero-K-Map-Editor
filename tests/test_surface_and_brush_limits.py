"""Regression: surface changes keep the painted heightmap, and brush min/max height limits.

Changing the Surface Type is a map SETTING, not a template generator: the live
design's water table and values update, but ``design.hm`` stays byte-for-byte the
same. The terrain brush clamps the painted height to min/max bounds (0 = disabled).
"""
import numpy as np
import pytest

from atlasforge.app.server import Forge
from atlasforge.brushes import apply_brush


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
    return fs


# ------------------------------------------------------------------ brush limits
def test_apply_brush_clamps_to_max_height():
    hm = np.full((33, 33), 50.0, dtype=np.float32)
    out = apply_brush(hm, 16, 16, 5, 500, "raise", symmetry="none", max_limit=150.0)
    assert float(out.max()) == 150.0


def test_apply_brush_clamps_to_min_height():
    hm = np.full((33, 33), 50.0, dtype=np.float32)
    out = apply_brush(hm, 16, 16, 5, 500, "lower", symmetry="none", min_limit=10.0)
    assert float(out.min()) == 10.0


def test_apply_brush_zero_limit_is_disabled():
    hm = np.full((33, 33), 50.0, dtype=np.float32)
    out = apply_brush(hm, 16, 16, 5, 500, "raise", symmetry="none", max_limit=0.0)
    assert float(out.max()) > 50.0          # 0 means "no limit"


# ------------------------------------------------------------------ surface endpoint
def _preview_editor(fs):
    m = fs.preview({"template": "editor",
                    "values": {"width": 16, "height": 4, "surface": "None (Dry)"},
                    "seed": 1})
    return m["id"]


def test_surface_endpoint_preserves_heightmap(forge_state):
    fs = forge_state
    did = _preview_editor(fs)
    hm0 = fs.entry(did).design.hm.copy()
    r = fs.surface({"id": did, "surface": "Water"})
    design = fs.entry(did).design
    assert np.array_equal(hm0, design.hm)          # painted terrain is untouched
    assert design.water["voidwater"] is False
    assert design.values["surface"] == "water"
    assert r["surface"] == "Water"


def test_surface_endpoint_switches_to_void_and_back(forge_state):
    fs = forge_state
    did = _preview_editor(fs)
    hm0 = fs.entry(did).design.hm.copy()
    fs.surface({"id": did, "surface": "Void (Death Pit)"})
    design = fs.entry(did).design
    assert "LuaRules/Gadgets/void_death.lua" in design.extra_files
    assert np.array_equal(hm0, design.hm)
    fs.surface({"id": did, "surface": "none"})
    design = fs.entry(did).design
    assert "LuaRules/Gadgets/void_death.lua" not in design.extra_files
    assert design.water["voidwater"] is True
    assert design.water["waterlevel"] == -1000.0
    assert np.array_equal(hm0, design.hm)

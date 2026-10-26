"""Numeric tests for the Forge Editor new-project defaults and the symmetric brush.

These are pure numeric checks - no image files are opened or inspected.
"""
import numpy as np

from atlasforge.brushes import apply_brush
from atlasforge.editor import SAND_RGB, flat_sand_design


def test_flat_sand_defaults():
    d = flat_sand_design(16, 4, seed=1)
    assert d.size == (16, 4)
    assert d.hm.shape == (4 * 64 + 1, 16 * 64 + 1)
    assert d.hm.dtype == np.float32
    assert float(d.hm.min()) == 50.0 and float(d.hm.max()) == 50.0

    tex = np.asarray(d.diffuse)
    assert tex.shape == (4 * 64 * 8, 16 * 64 * 8, 3)
    assert tex.dtype == np.uint8
    assert tuple(tex[0, 0]) == SAND_RGB
    assert np.all(tex == SAND_RGB)                    # solid colour everywhere


def test_flat_sand_rejects_odd_and_out_of_range():
    import pytest
    with pytest.raises(ValueError):
        flat_sand_design(15, 4)
    with pytest.raises(ValueError):
        flat_sand_design(4, 5)
    with pytest.raises(ValueError):
        flat_sand_design(2, 4)
    with pytest.raises(ValueError):
        flat_sand_design(34, 4)


def test_apply_brush_raise_lower_and_falloff():
    hm = np.full((5, 9), 50.0, dtype=np.float32)
    out = apply_brush(hm, 4, 2, 3.0, 10.0, "raise", "none")
    assert out.shape == hm.shape and out.dtype == hm.dtype
    assert hm[2, 4] == 50.0                       # input untouched
    assert out[2, 4] > 50.0                       # centre raised
    assert out[0, 0] == 50.0                      # far corner unchanged
    # gaussian falloff: monotonic away from the centre
    assert out[2, 4] > out[2, 3] > out[2, 1]
    lowered = apply_brush(hm, 4, 2, 3.0, 10.0, "lower", "none")
    assert lowered[2, 4] < 50.0


def test_apply_brush_symmetry():
    hm = np.full((7, 9), 50.0, dtype=np.float32)
    ew = apply_brush(hm, 2, 1, 3.0, 10.0, "raise", "ew")
    assert np.allclose(ew, ew[:, ::-1])
    ns = apply_brush(hm, 2, 1, 3.0, 10.0, "raise", "ns")
    assert np.allclose(ns, ns[::-1, :])
    both = apply_brush(hm, 2, 1, 3.0, 10.0, "raise", "ew_ns")
    assert np.allclose(both, both[:, ::-1]) and np.allclose(both, both[::-1, :])
    none = apply_brush(hm, 2, 1, 3.0, 10.0, "raise", "none")
    assert not np.allclose(none, none[:, ::-1])

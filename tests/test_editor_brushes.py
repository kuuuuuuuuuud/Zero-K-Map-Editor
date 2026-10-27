"""Numeric tests for the Forge Editor new-project defaults and the symmetric brush.

These are pure numeric checks - no image files are opened or inspected.
"""
import numpy as np

from atlasforge.brushes import apply_brush, apply_brush_line, apply_ramp
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


def test_preview_matches_map_aspect():
    """The quick preview must keep the map's aspect ratio: the 16x4 corridor used to be rendered
    as a square crop (left quarter stretched across the full width)."""
    from atlasforge import forge
    assert forge.preview(flat_sand_design(16, 4, seed=1, log=lambda *a: None), size=1024,
                         overlays=False).size == (1024, 256)
    assert forge.preview(flat_sand_design(4, 16, seed=1, log=lambda *a: None), size=1024,
                         overlays=False).size == (1024, 4096)
    assert forge.preview(flat_sand_design(8, 8, seed=1, log=lambda *a: None), size=1024,
                         overlays=False).size == (1024, 1024)


def test_apply_brush_hard_edge_raise_lower():
    hm = np.full((5, 9), 50.0, dtype=np.float32)
    out = apply_brush(hm, 4, 2, 3.0, 10.0, "raise", "none")
    assert out.shape == hm.shape and out.dtype == hm.dtype
    assert hm[2, 4] == 50.0                       # input untouched
    assert out[2, 4] == 60.0                      # centre raised by exactly strength
    assert out[2, 3] == 60.0                      # hard edge: inside is one flat height
    assert out[2, 1] == 60.0                      # boundary cell (d == radius) included
    assert out[2, 0] == 50.0                      # outside the radius: untouched
    assert out[0, 0] == 50.0                      # far corner unchanged
    lowered = apply_brush(hm, 4, 2, 3.0, 10.0, "lower", "none")
    assert lowered[2, 4] == 40.0
    assert lowered[2, 0] == 50.0


def test_apply_brush_square_shape():
    hm = np.full((7, 9), 50.0, dtype=np.float32)
    out = apply_brush(hm, 4, 3, 1.5, 10.0, "raise", "none", shape="square")
    assert out[3, 4] == 60.0                      # a square of half-width 1.5 covers cols 3..5, rows 2..4
    assert out[3, 5] == 60.0
    assert out[2, 4] == 60.0
    assert out[1, 4] == 50.0                      # row 1 is outside
    assert out[3, 6] == 50.0                      # column 6 is outside


def test_apply_brush_limit():
    hm = np.full((5, 9), 50.0, dtype=np.float32)
    raised = apply_brush(hm, 4, 2, 3.0, 20.0, "raise", "none", limit=55.0)
    assert raised[2, 4] == 55.0                   # clamped at max height
    assert raised[2, 3] == 55.0
    lowered = apply_brush(hm, 4, 2, 3.0, 20.0, "lower", "none", limit=40.0)
    assert lowered[2, 4] == 40.0                  # clamped at min height
    assert lowered[0, 0] == 50.0                  # cells outside the brush are never clamped


def test_apply_brush_smooth_reduces_cliff():
    hm = np.full((7, 9), 50.0, dtype=np.float32)
    hm[3, 2:7] = 90.0                             # a hard cliff inside the brush area
    out = apply_brush(hm, 4, 3, 3.0, 2, "smooth", "none")
    assert out[3, 4] < 90.0                       # the cliff edge is averaged with its neighbours
    assert out[2, 4] > 50.0
    assert out[4, 4] > 50.0


def test_apply_ramp_linear_interpolation():
    hm = np.full((8, 8), 50.0, dtype=np.float32)
    out = apply_ramp(hm, 1, 3, 6, 3, 2, 0.0, 100.0, "none")
    line = out[3, 1:7]
    assert float(line[0]) == 0.0 and float(line[-1]) == 100.0
    assert np.all(np.diff(line.astype(np.float64)) >= 0.0)   # monotone from A to B
    assert hm[3, 1] == 50.0                        # input untouched


def test_apply_ramp_symmetry():
    hm = np.full((16, 16), 50.0, dtype=np.float32)
    out = apply_ramp(hm, 2, 2, 6, 2, 2, 0.0, 100.0, "ew_ns")
    assert np.allclose(out, out[:, ::-1])          # mirrored across the vertical centre
    assert np.allclose(out, out[::-1, :])          # mirrored across the horizontal centre
    assert hm[2, 2] == 50.0                        # input untouched


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


def test_apply_brush_line_point_equals_apply_brush():
    hm = np.full((9, 9), 50.0, dtype=np.float32)
    dab = apply_brush(hm, 4, 4, 2.0, 10.0, "raise", "none")
    line = apply_brush_line(hm, 4, 4, 4, 4, 2.0, 10.0, "raise", "none")
    assert np.array_equal(dab, line)                 # a degenerate segment is a single dab
    assert hm[4, 4] == 50.0                          # input untouched


def test_apply_brush_line_covers_segment_and_mirrors():
    hm = np.full((16, 16), 50.0, dtype=np.float32)
    out = apply_brush_line(hm, 2, 8, 13, 8, 2.0, 10.0, "raise", "ew_ns")
    assert out[8, 2] == 60.0 and out[8, 13] == 60.0  # both endpoints painted
    assert out[8, 8] == 60.0                         # midpoint painted (continuous stroke)
    assert np.allclose(out, out[:, ::-1]) and np.allclose(out, out[::-1, :])
    assert hm[8, 2] == 50.0                          # input untouched

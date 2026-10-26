"""Terrain brushes (SCU-40): atlasforge.brushes raise_/lower/flatten/smooth on a heightmap array."""
import numpy as np
from numpy.testing import assert_allclose

from atlasforge import SQ
from atlasforge.brushes import flatten, lower, ramp, raise_, smooth


def _hm(dtype=np.float32, nz=32, nx=48):
    """Deterministic gentle terrain (elmo values 5..60) in the given dtype."""
    x = np.arange(nx)[None, :] * SQ
    z = np.arange(nz)[:, None] * SQ
    h = 30.0 + 12.0 * np.sin(x / 90.0) * np.cos(z / 70.0) + (x + z) / 48.0
    return h.astype(dtype)


def _disk_mask(hm, cx, cz, radius):
    """Cells inside the brush: elmo distance of the cell centre from (cx, cz) below radius."""
    x = np.arange(hm.shape[1])[None, :] * SQ - cx
    z = np.arange(hm.shape[0])[:, None] * SQ - cz
    return np.hypot(x, z) < radius


CX, CZ, RADIUS = 31.0 * SQ, 19.0 * SQ, 48.0   # well inside a 32x48 cell array (elmos 256 x 384)


def test_input_unchanged_and_dtype_preserved():
    for dtype in (np.float32, np.float64):
        hm = _hm(dtype)
        before = hm.copy()
        outs = [raise_(hm, CX, CZ, RADIUS, 1.0), lower(hm, CX, CZ, RADIUS, 1.0),
                flatten(hm, CX, CZ, RADIUS, 1.0), smooth(hm, CX, CZ, RADIUS, 1.0)]
        assert np.array_equal(hm, before)                       # input never modified
        for out in outs:
            assert out is not hm                                # a new array ...
            assert out.shape == hm.shape and out.dtype == hm.dtype   # ... with shape and dtype preserved


def test_outside_radius_identical():
    for fn in (lambda h: raise_(h, CX, CZ, RADIUS, 0.7),
               lambda h: lower(h, CX, CZ, RADIUS, 0.7),
               lambda h: flatten(h, CX, CZ, RADIUS, 0.7),
               lambda h: smooth(h, CX, CZ, RADIUS, 0.7)):
        hm = _hm()
        out = fn(hm)
        mask = ~_disk_mask(hm, CX, CZ, RADIUS)                  # w == 0 there
        assert np.array_equal(out[mask], hm[mask])              # ... exactly untouched outside


def test_raise_then_lower_restores_original():
    for dtype in (np.float32, np.float64):
        hm = _hm(dtype)
        roundtrip = lower(raise_(hm, CX, CZ, RADIUS, 1.0), CX, CZ, RADIUS, 1.0)
        tol = {"rtol": 0.0, "atol": 1e-4 if dtype == np.float32 else 1e-9}   # one rounding per call
        assert_allclose(roundtrip, hm, **tol)


def test_flatten_strength_one_centre_equals_target():
    x = np.arange(48)[None, :] * SQ
    z = np.arange(32)[:, None] * SQ
    h = 5.0 + x / 16.0 + z / 32.0                               # dyadic values: exact in both dtypes
    for dtype in (np.float32, np.float64):
        hm = h.astype(dtype)
        cx, cz = 10.0 * SQ, 8.0 * SQ                            # exactly on a cell centre
        out = flatten(hm, cx, cz, RADIUS, 1.0, target=50.0)     # w == 1 there
        assert float(out[round(cz / SQ), round(cx / SQ)]) == 50.0


def test_flatten_default_target_is_centre_height():
    hm = _hm()
    cx, cz = 24.0 * SQ, 16.0 * SQ
    iz, ix = round(cz / SQ), round(cx / SQ)
    out = flatten(hm, cx, cz, RADIUS, 1.0)                      # target defaults to h[iz, ix]
    assert float(out[iz, ix]) == float(hm[iz, ix])


def test_smooth_reduces_variance_inside_radius():
    rng = np.random.default_rng(7)
    hm = (_hm() + 8.0 * rng.standard_normal(_hm().shape)).astype(np.float32)
    out = smooth(hm, CX, CZ, RADIUS, 1.0)
    mask = _disk_mask(hm, CX, CZ, RADIUS)
    assert np.var(out[mask]) < np.var(hm[mask])


def test_centre_outside_array_no_exception():
    hm = _hm()
    for cx, cz in ((-5.0 * SQ, -3.0 * SQ), (float(hm.shape[1] + 5) * SQ, CZ)):
        for fn in (raise_, lower, flatten, smooth):             # centre outside the array ...
            out = fn(hm, cx, cz, 24.0, 1.0)                     # ... and radius too small to reach it
            assert np.array_equal(out, hm)                      # unchanged copy
            assert out.shape == hm.shape and out.dtype == hm.dtype


def test_centre_on_border_no_exception():
    hm = _hm()
    for cx, cz in ((0.0, 0.0), (float(hm.shape[1] - 1) * SQ, float(hm.shape[0] - 1) * SQ)):
        out = raise_(hm, cx, cz, 32.0, 1.0)                     # corner cells: brush clipped at the border
        assert np.all(np.isfinite(out)) and out.dtype == hm.dtype
    assert float(raise_(hm, 0.0, 0.0, 32.0, 1.0)[0, 0]) > float(hm[0, 0])


def test_deterministic():
    hm = _hm()
    for fn in (raise_, lower):
        a, b = fn(hm, CX, CZ, RADIUS, 0.8), fn(hm, CX, CZ, RADIUS, 0.8)
        assert np.array_equal(a, b)
    a, b = flatten(hm, CX, CZ, RADIUS, 0.8), flatten(hm, CX, CZ, RADIUS, 0.8)
    assert np.array_equal(a, b)
    a, b = smooth(hm, CX, CZ, RADIUS, 0.8), smooth(hm, CX, CZ, RADIUS, 0.8)
    assert np.array_equal(a, b)


# horizontal segment across row 16 of the 32x48 array; half-width 6 < SQ, so only row 16 carries weight on it
AX, AZ = 10.0 * SQ, 16.0 * SQ
BX, BZ = 38.0 * SQ, 16.0 * SQ
WIDTH = 12.0


def test_ramp_centreline_monotonic():
    for dtype in (np.float32, np.float64):
        hm = _hm(dtype)
        ha, hb = float(hm[16, 10]), float(hm[16, 38])          # heights at the line endpoints
        if hb < ha:                                             # orient A->B so the profile rises
            x0, z0, x1, z1 = BX, BZ, AX, AZ
        else:
            x0, z0, x1, z1 = AX, AZ, BX, BZ
        out = ramp(hm, x0, z0, x1, z1, WIDTH, 1.0)
        line = out[16, 10:39].astype(np.float64)                # w == 1 on the centreline at strength 1
        assert np.all(np.diff(line) >= 0.0)                     # monotonically from hm(A) to hm(B)


def test_ramp_endpoints_exact_at_strength_one():
    x = np.arange(48)[None, :] * SQ
    z = np.arange(32)[:, None] * SQ
    h = 5.0 + x / 16.0 + z / 32.0                               # dyadic values: exact in both dtypes
    for dtype in (np.float32, np.float64):
        hm = h.astype(dtype)
        out = ramp(hm, AX, AZ, BX, BZ, WIDTH, 1.0)             # w == 1 at A and B
        assert float(out[16, 10]) == 5.0 + AX / 16.0 + AZ / 32.0      # hm(A) ...
        assert float(out[16, 38]) == 5.0 + BX / 16.0 + BZ / 32.0      # ... and hm(B), exactly


def test_ramp_outside_strip_identical():
    for dtype in (np.float32, np.float64):
        hm = _hm(dtype)
        out = ramp(hm, AX, AZ, BX, BZ, WIDTH, 0.7)             # half-width 6 < SQ: strip is row 16 only
        mask = np.ones_like(hm, dtype=bool)                    # every cell but the centreline ones ...
        mask[16, 10:39] = False                                # ... has d >= width/2 and w == 0 exactly
        assert np.array_equal(out[mask], hm[mask])             # ... and is left bit-exact untouched


def test_ramp_input_unchanged_and_dtype_preserved():
    for dtype in (np.float32, np.float64):
        hm = _hm(dtype)
        before = hm.copy()
        out = ramp(hm, 8.0 * SQ, 8.0 * SQ, 40.0 * SQ, 24.0 * SQ, 20.0, 1.0)   # diagonal segment inside the array
        assert np.array_equal(hm, before)                       # input never modified
        assert out is not hm                                    # a new array ...
        assert out.shape == hm.shape and out.dtype == hm.dtype  # ... with shape and dtype preserved


def test_ramp_degenerate_segment_unchanged():
    for dtype in (np.float32, np.float64):
        hm = _hm(dtype)
        before = hm.copy()
        out = ramp(hm, 16.0 * SQ, 10.0 * SQ, 16.0 * SQ, 10.0 * SQ, WIDTH, 1.0)   # A == B
        assert np.array_equal(out, before)                    # unchanged copy ...
        assert out is not hm and out.dtype == hm.dtype        # ... still a new array of the same dtype


def test_ramp_segment_partly_outside_array():
    for dtype in (np.float32, np.float64):
        hm = _hm(dtype)
        before = hm.copy()
        out = ramp(hm, -8.0 * SQ, 16.0 * SQ, 50.0 * SQ, 16.0 * SQ, WIDTH, 1.0)   # A left of the array, B right of it
        assert np.array_equal(hm, before)                     # input never modified ...
        assert out.shape == hm.shape and out.dtype == hm.dtype   # ... borders clipped, dtype preserved
        assert np.all(np.isfinite(out))                       # clamped segment stays finite
        ha, hb = float(hm[16, 0]), float(hm[16, -1])          # A/B clamp to the border cells of row 16
        line = out[16, :].astype(np.float64)                  # whole row lies on the clamped line (w == 1)
        if hb >= ha:
            assert np.all(np.diff(line) >= 0.0)               # monotone along the clamped segment
        else:
            assert np.all(np.diff(line) <= 0.0)

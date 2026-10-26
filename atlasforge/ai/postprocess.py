"""Selective post-processing for AI-generated terrain (Phase 3.5).

The raw DeepInfra heightmap is a "painting": it holds coherent large features
(fortresses, cliffs, chasms, hills) *plus* high-frequency SDXL artifacts
(pixel-level spikes and near-vertical micro-cliffs).  These two helpers remove
the artifacts without flattening the real terrain:

* ``denoise``               replaces only cells whose local 3x3 roughness
                            (standard deviation) exceeds ``roughness_threshold``
                            with a Gaussian-smoothed value.  The interior of a
                            large feature has low local roughness and is left
                            untouched; a pixel-level spike has high roughness
                            and is smoothed away.
* ``selective_slope_clamp`` clamps only near-vertical micro-cliff edges (slope
                            > ``max_slope_deg``, default 75 deg).  Slopes between
                            30 deg and 75 deg are intentional terrain and are
                            left alone.  An edge is only treated as a micro-cliff
                            when the elevated side falls back to low ground within
                            ``max_edge_cells`` cells, so wide fortress walls and
                            plateau edges are preserved.
"""

import math

import numpy as np
from scipy import ndimage


def denoise(hm, roughness_threshold=8.0, sigma=1.5):
    """Replace only high-roughness cells with a Gaussian-smoothed value.

    Local roughness is the standard deviation of the 3x3 cell neighbourhood
    (in elmos).  Cells whose neighbourhood roughness exceeds
    ``roughness_threshold`` are SDXL pixel-noise and get ``sigma``-Gaussian
    smoothing; everything else (the interior of real features) is copied
    through unchanged.

    Returns ``(hm_out, pct_cells_smoothed)`` where ``pct_cells_smoothed`` is
    the percentage of cells replaced (0.0 - 100.0).
    """
    hm = np.asarray(hm, dtype=np.float32)
    if hm.ndim != 2:
        raise ValueError(f"heightmap must be 2D, got shape {hm.shape}")

    kernel = np.full((3, 3), 1.0 / 9.0, dtype=np.float32)
    mean = ndimage.convolve(hm, kernel, mode="nearest")
    sq_mean = ndimage.convolve(hm * hm, kernel, mode="nearest")
    var = np.maximum(sq_mean - mean * mean, 0.0)
    roughness = np.sqrt(var).astype(np.float32)

    smoothed = ndimage.gaussian_filter(hm, float(sigma), mode="nearest").astype(np.float32)
    mask = roughness > float(roughness_threshold)
    out = np.where(mask, smoothed, hm).astype(np.float32)
    pct = 100.0 * float(np.count_nonzero(mask)) / float(mask.size)
    return out, pct


def selective_slope_clamp(hm, cell_size=8.0, max_slope_deg=75.0, max_edge_cells=3):
    """Clamp only near-vertical micro-cliff edges; leave real terrain alone.

    For each adjacent cell pair the slope is ``atan(|dh| / (dist * cell_size))``.
    Only edges steeper than ``max_slope_deg`` are considered, and only when the
    elevated side is a *micro*-feature: the terrain must fall back to within one
    ``max_slope_deg`` step of the low side inside ``max_edge_cells`` cells.
    Those edges are clamped by lowering the high side down to
    ``low + tan(max_slope_deg) * dist * cell_size`` (the low side is never
    raised, so no ring bumps appear).  Wide fortress walls, plateau rims and
    gentle 30-75 deg slopes are preserved.

    Returns ``(hm_out, num_edges_clamped)``.
    """
    hm = np.asarray(hm, dtype=np.float32).copy()
    if hm.ndim != 2:
        raise ValueError(f"heightmap must be 2D, got shape {hm.shape}")
    if hm.size == 0:
        return hm, 0

    max_dh_unit = math.tan(math.radians(float(max_slope_deg))) * float(cell_size)
    if max_dh_unit <= 0.0:
        return hm, 0
    m = max(1, int(max_edge_cells))
    nz, nx = hm.shape

    # Four forward offsets cover every undirected adjacent edge exactly once.
    offsets = ((1, 0, 1.0), (0, 1, 1.0), (1, 1, math.sqrt(2.0)), (1, -1, math.sqrt(2.0)))

    total = 0
    # A micro-feature is at most ``m`` cells wide, so ``m`` passes let the
    # downward clamp settle across its full width without ever touching a
    # wide (persistent) feature.
    for _ in range(m):
        padded = np.pad(hm, m, mode="edge")
        hi = np.full((nz + 2 * m, nx + 2 * m), np.inf, dtype=np.float32)
        for di, dj, dist in offsets:
            max_dh = max_dh_unit * dist
            cur = padded[m:m + nz, m:m + nx]
            nb = padded[m + di:m + di + nz, m + dj:m + dj + nx]
            dh = nb - cur
            steep = np.abs(dh) > max_dh
            if not steep.any():
                continue

            # Min height within ``m`` cells continuing past the high side, in
            # both directions.  If that min drops back to the low side's level,
            # the high side is a micro-cliff; if it stays high, it is wide.
            fwd = np.full((nz, nx), np.inf, dtype=np.float32)
            back = np.full((nz, nx), np.inf, dtype=np.float32)
            for k in range(1, m + 1):
                np.minimum(
                    fwd,
                    padded[m + k * di:m + k * di + nz, m + k * dj:m + k * dj + nx],
                    out=fwd,
                )
                np.minimum(
                    back,
                    padded[m - k * di:m - k * di + nz, m - k * dj:m - k * dj + nx],
                    out=back,
                )

            nb_high = dh > 0.0
            micro = np.where(nb_high, fwd - cur <= max_dh, back - nb <= max_dh)
            clamp = steep & micro
            n = int(np.count_nonzero(clamp))
            if n == 0:
                continue
            total += n

            # Only lower the high side of each micro-cliff edge.
            bound_cur = np.where(clamp & (~nb_high), nb + max_dh, np.inf).astype(np.float32)
            bound_nb = np.where(clamp & nb_high, cur + max_dh, np.inf).astype(np.float32)
            np.minimum(hi[m:m + nz, m:m + nx], bound_cur, out=hi[m:m + nz, m:m + nx])
            np.minimum(
                hi[m + di:m + di + nz, m + dj:m + dj + nx],
                bound_nb,
                out=hi[m + di:m + di + nz, m + dj:m + dj + nx],
            )

        np.minimum(hm, hi[m:m + nz, m:m + nx], out=hm)

    return hm.astype(np.float32), total


# --------------------------------------------------------------------------- Phase 3.6: symmetry mirror
def _mirror_axis(a, axis):
    """Mirror one axis in place: the left/top half (plus the centre when odd) wins.

    For an even-length axis the first half is copied onto the second half; for an
    odd-length axis the centre row/column is kept and the first half is copied
    onto the second.  Works on the first two axes of a 2D/3D array.
    """
    n = a.shape[axis]
    half = n // 2
    src = [slice(None)] * a.ndim
    dst = [slice(None)] * a.ndim
    src[axis] = slice(half - 1, None, -1)                  # half-1 .. 0
    dst[axis] = slice(half + (1 if n % 2 else 0), None)    # half+1 .. n-1 (odd) or half .. n-1 (even)
    a[tuple(dst)] = a[tuple(src)]
    return a


def mirror_quadrant(arr, axes="ew"):
    """Make an array exactly symmetric by copying one quadrant across the axes.

    ``axes`` is one of ``"ew"`` (mirror the left half onto the right),
    ``"ns"`` (mirror the top half onto the bottom) or ``"ew_ns"`` (copy the
    top-left quadrant onto the other three).  For an odd axis the centre
    row/column is kept as the mirror line; for an even axis the first half is
    copied onto the second half.  The result satisfies ``out[..., i] ==
    out[..., -i - 1]`` on every mirrored axis and always has the same shape and
    dtype as the input.  3D arrays (H, W, C) mirror only the H and W axes,
    leaving the channel axis untouched.

    Returns ``(out, axes)``.
    """
    arr = np.asarray(arr)
    if arr.ndim not in (2, 3):
        raise ValueError(f"expected a 2D or 3D array, got {arr.ndim}D")
    axes = str(axes).lower()
    if axes not in ("ew", "ns", "ew_ns"):
        raise ValueError(f"axes must be 'ew', 'ns' or 'ew_ns', got {axes!r}")
    out = arr.copy()
    if "ew" in axes:
        _mirror_axis(out, 1)
    if "ns" in axes:
        _mirror_axis(out, 0)
    return out, axes


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    a = rng.integers(0, 100, (5, 7))                      # odd x odd, 2D
    b, _ = mirror_quadrant(a, "ew")
    assert b.shape == a.shape and np.array_equal(b, b[:, ::-1])
    c, _ = mirror_quadrant(a, "ns")
    assert c.shape == a.shape and np.array_equal(c, c[::-1, :])
    d, _ = mirror_quadrant(a, "ew_ns")
    assert np.array_equal(d, d[:, ::-1]) and np.array_equal(d, d[::-1, :])
    e = rng.integers(0, 100, (4, 6))                      # even x even, 2D
    f, _ = mirror_quadrant(e, "ew_ns")
    assert np.array_equal(f, f[:, ::-1]) and np.array_equal(f, f[::-1, :])
    g = rng.integers(0, 255, (4, 6, 3)).astype(np.uint8)  # 3D RGB
    h, _ = mirror_quadrant(g, "ew_ns")
    assert h.shape == g.shape and h.dtype == g.dtype
    assert np.array_equal(h, h[:, ::-1]) and np.array_equal(h, h[::-1, :])
    print("mirror_quadrant self-test passed")

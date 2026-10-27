"""Terrain brushes (editor stage B): pure functions on a heightmap array.

The heightmap is a 2D float array in elmos, row = z, column = x, one cell per SQ elmo square
(atlasforge.SQ). Every function returns a NEW array with the same shape and dtype; the input is
never modified, borders are clipped cleanly and everything is deterministic.

The legacy raise_/lower/flatten/smooth/ramp helpers below take elmo coordinates and a smooth
smoothstep weight w(d) (soft edges). The editor brushes ``apply_brush`` and ``apply_ramp`` take
heightmap *pixel* coordinates and use a hard edge (1.0 inside the footprint, 0.0 outside) so the
on-screen cursor matches the painted area exactly.
"""
import numpy as np

from . import SQ


def _weights(hm, cx, cz, radius):
    """Per-cell weight w(d) for d = elmo distance from (cx, cz): 1 at the centre, 0 for d >= radius."""
    nz, nx = hm.shape[:2]
    if not hm.size or radius <= 0:
        return np.zeros((nz, nx))
    x = np.arange(nx)[None, :] * SQ - cx
    z = np.arange(nz)[:, None] * SQ - cz
    t = np.clip(1.0 - np.hypot(x, z) / radius, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _centre(hm, cx, cz):
    """Heightmap index of the cell at elmo position (cx, cz), clamped to the array (like edits._ground)."""
    iz = min(max(int(round(cz / SQ)), 0), hm.shape[0] - 1)
    ix = min(max(int(round(cx / SQ)), 0), hm.shape[1] - 1)
    return iz, ix


def _box3(h):
    """Per-cell average of the 3x3 neighbourhood; at the array border fewer cells are averaged."""
    nz, nx = h.shape[:2]
    s = np.zeros((nz, nx))
    n = np.zeros((nz, nx))
    for dz in (-1, 0, 1):
        for dx in (-1, 0, 1):
            i0, i1 = max(0, -dz), min(nz, nz - dz)
            j0, j1 = max(0, -dx), min(nx, nx - dx)
            s[i0:i1, j0:j1] += h[i0 + dz:i1 + dz, j0 + dx:j1 + dx]
            n[i0:i1, j0:j1] += 1
    return s / n


def raise_(hm, cx, cz, radius, strength, amount=20.0):
    """Raise the terrain: hm + amount * strength * w(d). Returns a new array."""
    out = hm.astype(np.float64, copy=True)
    out += float(amount) * float(strength) * _weights(hm, cx, cz, radius)
    return out.astype(hm.dtype)


def lower(hm, cx, cz, radius, strength, amount=20.0):
    """Lower the terrain: hm - amount * strength * w(d). Returns a new array."""
    out = hm.astype(np.float64, copy=True)
    out -= float(amount) * float(strength) * _weights(hm, cx, cz, radius)
    return out.astype(hm.dtype)


def flatten(hm, cx, cz, radius, strength, target=None):
    """Pull heights toward target (default: the height at (cx, cz)): hm + strength * w(d) * (target - hm)."""
    if target is None:
        iz, ix = _centre(hm, cx, cz)
        target = float(hm[iz, ix])
    out = hm.astype(np.float64, copy=True)
    out += float(strength) * _weights(hm, cx, cz, radius) * (float(target) - out)
    return out.astype(hm.dtype)


def smooth(hm, cx, cz, radius, strength):
    """Blur toward a 3x3 box filter: hm + strength * w(d) * (box - hm). Returns a new array."""
    out = hm.astype(np.float64, copy=True)
    out += float(strength) * _weights(hm, cx, cz, radius) * (_box3(out) - out)
    return out.astype(hm.dtype)


def ramp(hm, x0, z0, x1, z1, width, strength=1.0):
    """Lay heights along A(x0,z0)->B(x1,z1) linearly from hm(A) to hm(B), in a strip of half-width
    width/2 around the line with smoothstep falloff at the edges: hm + strength * w(d) * (h_line - hm).
    d is the elmo distance to the clamped segment (A/B outside the array use the border cell height);
    degenerate segment (A == B) or width <= 0 return an unchanged copy. Returns a new array."""
    nz, nx = hm.shape[:2]
    if not hm.size or float(width) <= 0.0:
        return hm.copy()
    dx, dz = float(x1) - float(x0), float(z1) - float(z0)
    seg2 = dx * dx + dz * dz
    if seg2 == 0.0:
        return hm.copy()
    iz, ix = _centre(hm, x0, z0)
    ha = float(hm[iz, ix])
    iz, ix = _centre(hm, x1, z1)
    hb = float(hm[iz, ix])
    out = hm.astype(np.float64, copy=True)
    x = np.arange(nx)[None, :] * SQ - float(x0)
    z = np.arange(nz)[:, None] * SQ - float(z0)
    uc = np.clip((x * dx + z * dz) / seg2, 0.0, 1.0)
    d = np.hypot(x - uc * dx, z - uc * dz)
    t = np.clip(1.0 - d / (0.5 * float(width)), 0.0, 1.0)
    w = t * t * (3.0 - 2.0 * t) * float(strength)
    out += w * ((ha + uc * (hb - ha)) - out)
    return out.astype(hm.dtype)


def _mirrors(x, y, symmetry, nx, nz):
    """Mirror pixel (x, y) across the map centre like the object editor.

    Pixel indices run 0..nx-1 across and 0..nz-1 down; the centre line sits at (nx-1)/2,
    so the mirror of column c is (nx-1) - c (and likewise for rows).
    """
    pts = [(float(x), float(y))]
    if symmetry in ("ew", "ew_ns"):
        pts.append(((nx - 1) - float(x), float(y)))
    if symmetry in ("ns", "ew_ns"):
        pts.append((float(x), (nz - 1) - float(y)))
    if symmetry == "ew_ns":
        pts.append(((nx - 1) - float(x), (nz - 1) - float(y)))
    return pts


def _footprint(hm, cx, cy, radius, shape):
    """Boolean mask of the brush footprint at pixel (cx, cy) with a hard edge."""
    nz, nx = hm.shape[:2]
    x = np.arange(nx)[None, :] - float(cx)
    z = np.arange(nz)[:, None] - float(cy)
    if shape == "square":
        return (np.abs(x) <= radius) & (np.abs(z) <= radius)
    return (x * x + z * z) <= float(radius) * float(radius)


def _paint(hm, mask, mode, strength, limit):
    """Apply raise/lower/smooth to the cells selected by ``mask``; returns a new array."""
    out = hm.astype(np.float64, copy=True)
    if mode == "raise":
        painted = out[mask] + strength
        if limit is not None:
            painted = np.minimum(painted, float(limit))
        out[mask] = painted
    elif mode == "lower":
        painted = out[mask] - strength
        if limit is not None:
            painted = np.maximum(painted, float(limit))
        out[mask] = painted
    else:                                                     # smooth: average painted cells with their neighbours
        passes = max(0, min(50, int(round(strength))))
        for _ in range(passes):
            out += mask * (_box3(out) - out)
    return out.astype(hm.dtype)


def apply_brush(hm, x, y, radius, strength, mode="raise", symmetry="ew_ns", shape="circle", limit=None):
    """Apply a hard-edged terrain brush at pixel (x, y) and mirror it.

    hm       : 2D float heightmap array (row = z, column = x); the input is never modified.
    x, y     : brush centre in heightmap pixel coordinates (x = column, y = row).
    radius   : brush radius in pixels (> 0); the footprint is 1.0 inside and 0.0 outside.
    strength : mode="raise"/"lower" -> height added/removed per dab in elmos;
               mode="smooth"        -> number of 3x3 box-smoothing passes (1..50).
    mode     : "raise", "lower" or "smooth".
    symmetry : "none", "ew" (mirror across the vertical centre line), "ns" (mirror
               across the horizontal centre line) or "ew_ns" (both mirrors).
    shape    : "circle" or "square".
    limit    : optional height bound in elmos. mode="raise" never paints above it,
               mode="lower" never paints below it (only painted cells are clamped).
               Ignored for mode="smooth".

    Returns a NEW heightmap with the same shape and dtype as ``hm``.
    """
    hm = np.asarray(hm)
    if hm.ndim != 2:
        raise ValueError("hm must be a 2D array")
    if mode not in ("raise", "lower", "smooth"):
        raise ValueError(f"mode must be 'raise', 'lower' or 'smooth', got {mode!r}")
    if shape not in ("circle", "square"):
        raise ValueError(f"shape must be 'circle' or 'square', got {shape!r}")
    if symmetry not in ("none", "ew", "ns", "ew_ns"):
        raise ValueError(f"symmetry must be one of none/ew/ns/ew_ns, got {symmetry!r}")
    radius = float(radius)
    if radius <= 0:
        raise ValueError("radius must be > 0")
    strength = float(strength)

    nz, nx = hm.shape
    mask = np.zeros((nz, nx), bool)
    for cx, cy in _mirrors(x, y, symmetry, nx, nz):
        mask |= _footprint(hm, cx, cy, radius, shape)
    return _paint(hm, mask, mode, strength, limit)


def apply_ramp(hm, x1, y1, x2, y2, width, start_height, end_height, symmetry="ew_ns"):
    """Lay a straight ramp of ``width`` pixels from A(x1,y1) to B(x2,y2) and mirror it.

    Heights along the line interpolate linearly (``numpy.linspace``) from ``start_height``
    to ``end_height`` in elmos. The strip has a hard edge at half-width ``width/2``; cells
    beyond it are untouched. A degenerate segment (A == B) paints a disc of ``width``
    around the point at ``start_height``. Returns a NEW heightmap with the same shape and
    dtype as ``hm``; the input is never modified.
    """
    hm = np.asarray(hm)
    if hm.ndim != 2:
        raise ValueError("hm must be a 2D array")
    if symmetry not in ("none", "ew", "ns", "ew_ns"):
        raise ValueError(f"symmetry must be one of none/ew/ns/ew_ns, got {symmetry!r}")
    width = float(width)
    if width <= 0:
        raise ValueError("width must be > 0")

    nz, nx = hm.shape
    start_height, end_height = float(start_height), float(end_height)
    half = 0.5 * width
    out = hm.astype(np.float64, copy=True)
    segments = zip(_mirrors(x1, y1, symmetry, nx, nz), _mirrors(x2, y2, symmetry, nx, nz))
    for (ax, ay), (bx, by) in segments:
        dx, dz = bx - ax, by - ay
        x = np.arange(nx)[None, :] - ax
        z = np.arange(nz)[:, None] - ay
        if dx == 0.0 and dz == 0.0:                          # degenerate: a disc at A
            uc = np.zeros((nz, nx))
            d = np.hypot(x, z)
            heights = np.full((nz, nx), start_height)
        else:
            seg2 = dx * dx + dz * dz
            uc = np.clip((x * dx + z * dz) / seg2, 0.0, 1.0)
            d = np.hypot(x - uc * dx, z - uc * dz)
            steps = max(int(np.ceil(np.hypot(dx, dz))), 1) + 1
            profile = np.linspace(start_height, end_height, steps)
            heights = profile[np.clip(np.round(uc * (steps - 1)).astype(np.intp), 0, steps - 1)]
        strip = d <= half
        out[strip] = heights[strip]
    return out.astype(hm.dtype)


def apply_brush_line(hm, x1, y1, x2, y2, radius, strength, mode="raise", symmetry="ew_ns",
                     shape="circle", limit=None):
    """Apply a hard-edged brush along the straight segment A(x1,y1)->B(x2,y2) and mirror it.

    Same contract as :func:`apply_brush`, except the brush is stamped at evenly spaced
    samples along the segment (one dab every ``radius`` pixels so the footprint stays
    continuous) instead of at a single point. A degenerate segment (A == B) paints a
    single dab. Returns a NEW heightmap with the same shape and dtype as ``hm``; the
    input is never modified.
    """
    hm = np.asarray(hm)
    if hm.ndim != 2:
        raise ValueError("hm must be a 2D array")
    if mode not in ("raise", "lower", "smooth"):
        raise ValueError(f"mode must be 'raise', 'lower' or 'smooth', got {mode!r}")
    if shape not in ("circle", "square"):
        raise ValueError(f"shape must be 'circle' or 'square', got {shape!r}")
    if symmetry not in ("none", "ew", "ns", "ew_ns"):
        raise ValueError(f"symmetry must be one of none/ew/ns/ew_ns, got {symmetry!r}")
    radius = float(radius)
    if radius <= 0:
        raise ValueError("radius must be > 0")
    strength = float(strength)

    nz, nx = hm.shape
    mask = np.zeros((nz, nx), bool)
    step = max(0.5 * radius, 0.5)
    segments = zip(_mirrors(x1, y1, symmetry, nx, nz), _mirrors(x2, y2, symmetry, nx, nz))
    for (ax, ay), (bx, by) in segments:
        length = float(np.hypot(bx - ax, by - ay))
        steps = max(2, int(np.ceil(length / step)) + 1) if length > 0.0 else 1
        for t in np.linspace(0.0, 1.0, steps):
            mask |= _footprint(hm, ax + t * (bx - ax), ay + t * (by - ay), radius, shape)
    return _paint(hm, mask, mode, strength, limit)


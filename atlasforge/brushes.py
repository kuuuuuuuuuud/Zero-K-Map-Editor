"""Terrain brushes (editor stage B): pure functions on a heightmap array.

The heightmap is a 2D float array in elmos, row = z, column = x, one cell per SQ elmo square
(atlasforge.SQ). All parameters are in elmos: cx/cz address the brush centre, radius its reach,
strength scales the effect from 0 (no-op) to 1. Every function returns a NEW array with the same
shape and dtype; the input is never modified. The weight w(d) falls off smoothly from 1 at the
centre to 0 for d >= radius (smoothstep), so brush edges are soft, and cells beyond the array are
simply absent - borders are clipped cleanly. Deterministic: no randomness.
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


def apply_brush(hm, x, y, radius, strength, mode, symmetry="ew_ns"):
    """Apply a smooth circular brush (gaussian falloff) at pixel (x, y) and mirror it.

    hm       : 2D float heightmap array (row = z, column = x); the input is never modified.
    x, y     : brush centre in heightmap pixel coordinates (x = column, y = row).
    radius   : brush radius in pixels (> 0).
    strength : height to add (mode="raise") or subtract (mode="lower"), in elmos.
    mode     : "raise" or "lower".
    symmetry : "none", "ew" (mirror across the vertical centre line), "ns" (mirror
               across the horizontal centre line) or "ew_ns" (both mirrors).

    Returns a NEW heightmap with the same shape and dtype as ``hm``.
    """
    hm = np.asarray(hm)
    if hm.ndim != 2:
        raise ValueError("hm must be a 2D array")
    if mode not in ("raise", "lower"):
        raise ValueError(f"mode must be 'raise' or 'lower', got {mode!r}")
    if symmetry not in ("none", "ew", "ns", "ew_ns"):
        raise ValueError(f"symmetry must be one of none/ew/ns/ew_ns, got {symmetry!r}")
    if radius <= 0:
        raise ValueError("radius must be > 0")

    nz, nx = hm.shape
    out = hm.astype(np.float64, copy=True)
    sign = 1.0 if mode == "raise" else -1.0
    strength = float(strength)

    # Pixel indices run 0..nx-1 across and 0..nz-1 down; the map centre line sits at
    # (nx-1)/2, so the mirror of column c is (nx-1) - c (and likewise for rows).
    centres = [(float(x), float(y))]
    if symmetry in ("ew", "ew_ns"):
        centres.append(((nx - 1) - float(x), float(y)))
    if symmetry in ("ns", "ew_ns"):
        centres.append((float(x), (nz - 1) - float(y)))
    if symmetry == "ew_ns":
        centres.append(((nx - 1) - float(x), (nz - 1) - float(y)))

    sigma = float(radius) / 3.0
    r = int(np.ceil(radius)) + 1
    for cx, cy in centres:
        x0 = max(0, int(np.floor(cx - r)))
        x1 = min(nx, int(np.ceil(cx + r)) + 1)
        y0 = max(0, int(np.floor(cy - r)))
        y1 = min(nz, int(np.ceil(cy + r)) + 1)
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float64)
        d2 = (xx - cx) ** 2 + (yy - cy) ** 2
        w = np.exp(-0.5 * d2 / (sigma * sigma))
        w *= d2 <= float(radius) * float(radius)   # clip the tail cleanly at the rim
        out[y0:y1, x0:x1] += sign * strength * w
    return out.astype(hm.dtype)


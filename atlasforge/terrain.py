"""Terrain building blocks for designed maps. All units are elmos; heightmap grid spacing SQ = 8.

Principles:
  - Plateaus are composed with a (soft) max(), their edges fall off at a chosen angle; pits use min().
    Top edges are rounded and toes blended so the game shows no hard creases.
  - Roads/ramps/gates clamp the terrain into a cone around a height profile:
      core (|lateral| < half width): exactly the profile height
      beside it: terrain is limited to [profile - d*tan(down), profile + d*tan(up)]
    so ramps always join plateaus without gaps or steps.
  - move_slope() reproduces how the Recoil engine tests slopes for movement classes.
"""
import math
import numpy as np
from scipy import ndimage

from . import SQ
from .noise import smoothstep


def grid(n):
    """Elmo coordinates (xx, zz) of an n x n heightmap."""
    zz, xx = np.mgrid[0:n, 0:n].astype(np.float32) * SQ
    return xx, zz


def tan(deg):
    return math.tan(math.radians(deg))


# ----------------------------------------------------------------------------- soft operators
def smax(a, b, k):
    """Polynomial soft maximum (k = blend width in height units)."""
    if np.isscalar(k) and k <= 0:
        return np.maximum(a, b)
    hh = np.clip(0.5 + 0.5 * (a - b) / k, 0, 1)
    return b + (a - b) * hh + k * hh * (1 - hh)


def smin(a, b, k):
    return -smax(-a, -b, k)


def soft_relu(x, r):
    """max(x, 0) with a quadratic rounding over width r (C1 continuous)."""
    if r <= 0:
        return np.maximum(x, 0)
    return np.where(x <= 0, 0, np.where(x >= r, x - r * 0.5, x * x / (2 * r)))


# ----------------------------------------------------------------------------- shapes
def plateau(h, sdf, top, side_deg=60, noise=None, amp=0.0, round_=24.0, toe=10.0):
    """Raise a plateau where sdf < 0. top: number or array.
    round_: rounding of the top edge (elmos), toe: soft blend at the foot (height units).
    Both avoid hard creases; the flank angle stays the same."""
    d = sdf if noise is None else sdf + amp * noise
    prof = top - soft_relu(d, round_) * tan(side_deg)
    h[...] = smax(h, prof, toe) if toe > 0 else np.maximum(h, prof)
    return h


def pit(h, sdf, bottom, side_deg=60, noise=None, amp=0.0, round_=24.0, toe=10.0):
    """Cut a pit/trench where sdf < 0 (min composition), edges rounded like plateau()."""
    d = sdf if noise is None else sdf + amp * noise
    prof = bottom + soft_relu(d, round_) * tan(side_deg)
    h[...] = smin(h, prof, toe) if toe > 0 else np.minimum(h, prof)
    return h


def box_sdf(X, Z, cx, cz, hx, hz):
    dx = np.abs(X - cx) - hx
    dz = np.abs(Z - cz) - hz
    return np.hypot(np.maximum(dx, 0), np.maximum(dz, 0)) + np.minimum(np.maximum(dx, dz), 0)


def ring_sdf(X, Z, cx, cz, R, half, gates=(), gate_hw=150):
    """Ring wall (sdf < 0 = wall) with gaps. gates: angles in degrees (0 = +x/east, 90 = +z/south).
    A gap leaves the natural terrain untouched: no road strip, just steep wall ends."""
    dx, dz = X - cx, Z - cz
    sdf = np.abs(np.hypot(dx, dz) - R) - half
    for g in gates:
        ux, uz = math.cos(math.radians(g)), math.sin(math.radians(g))
        lat = np.abs(-uz * dx + ux * dz)
        front = dx * ux + dz * uz > 0
        sdf = np.where(front, np.maximum(sdf, gate_hw - lat), sdf)
    return sdf


def ellipse_sdf(X, Z, cx, cz, rx, rz):
    """Approximate true distance to an ellipse (Quilez): k0 * (k0 - 1) / k1."""
    px, pz = (X - cx), (Z - cz)
    k0 = np.hypot(px / rx, pz / rz)
    k1 = np.hypot(px / (rx * rx), pz / (rz * rz))
    return k0 * (k0 - 1) / np.maximum(k1, 1e-9)


# ----------------------------------------------------------------------------- roads and ramps
def road_polyline(h, pts, prof, hw, down_deg=40, up_deg=40, influence=None, edge_round=None, soft=None,
                  blend=None, end_fade=None):
    """Road along a densely sampled polyline.
    pts: (N, 2) elmo coordinates (x, z); prof: height per point; hw: half width of the flat core.
    Sub-pixel accurate: nearest point via distance transform, then projection onto the local tangent
    (continuous arc length) and linear interpolation of the profile, so there are no raster steps.
    edge_round: rounding width (elmos) between core and flank.
    soft: rounding (height) where the flank meets the terrain.
    blend: width (elmos) over which the terrain is eased towards the road height: small height
      differences become flat shoulders, large ones (walls, cliffs) stay steep because of the cone.
    end_fade: beyond the two ends the road fades into the terrain over this distance (elmos) instead of
      ending in a round cone cap (which leaves a fan of radial streaks on slopes).
    Returns the distance field to the road (elmos, 1e9 outside the influence area)."""
    pts = np.asarray(pts, np.float64)
    prof = np.asarray(prof, np.float64)
    n0, n1 = h.shape
    N = len(pts)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    sarr = np.concatenate([[0], np.cumsum(seg)])
    total = sarr[-1]
    mask = np.ones(h.shape, bool)
    idx = np.zeros(h.shape, np.int32)
    ii = np.clip(np.round(pts[:, 1] / SQ).astype(int), 0, n0 - 1)
    jj = np.clip(np.round(pts[:, 0] / SQ).astype(int), 0, n1 - 1)
    mask[ii, jj] = False
    idx[ii, jj] = np.arange(N)
    lim = (influence if influence is not None else 4000) + 4 * SQ
    dist0, (ni, nj) = ndimage.distance_transform_edt(mask, return_indices=True)
    act = dist0 * SQ < lim
    k0 = idx[ni[act], nj[act]]
    step = max(1, int(round(24 / max(np.median(seg), 1e-3))))       # local tangent over about +-24 elmos
    ka = np.clip(k0 - step, 0, N - 1); kb = np.clip(k0 + step, 0, N - 1)
    a = pts[ka]; b = pts[kb]
    u = b - a
    ul = np.linalg.norm(u, axis=1, keepdims=True); u /= np.maximum(ul, 1e-6)
    zz, xx = np.nonzero(act)
    P = np.stack([xx * SQ, zz * SQ], 1).astype(np.float64)
    rel = P - a
    t = sarr[ka] + (rel * u).sum(1)
    lat = np.abs(rel[:, 0] * u[:, 1] - rel[:, 1] * u[:, 0])
    tc = np.clip(t, 0, total)
    over = np.abs(t - tc)                       # beyond the ends: round cap
    d = np.hypot(lat, over)
    p = np.interp(tc, sarr, prof)
    er = hw * 0.35 if edge_round is None else edge_round
    e = soft_relu(d - hw, er)
    lo = p - e * tan(down_deg)
    hi = p + e * tan(up_deg)
    hv = h[act].astype(np.float64)
    bl = max(hw * 0.6, 120.0) if not blend else blend
    tb = np.clip(e / bl, 0, 1)
    wb = tb * tb * tb * (tb * (tb * 6 - 15) + 10)           # smootherstep (C2)
    hb = p + (hv - p) * wb                                  # soft easing first ...
    k = (abs(prof.max() - prof.min()) * 0.06 + 8) if soft is None else soft
    # softness grows from 0 at the core edge (exact profile there, no seam) and never exceeds the cone
    # distance (terrain at road height stays untouched)
    kk = k * np.clip(e / max(er, 1.0), 0, 1)
    k_lo = np.minimum(kk, e * tan(down_deg)) + 1e-6
    k_hi = np.minimum(kk, e * tan(up_deg)) + 1e-6
    newv = smin(smax(hb, lo, k_lo), hi, k_hi)                # ... then the cone for large differences
    if influence is not None:
        tt = np.clip((d - influence * 0.7) / (influence * 0.3), 0, 1)
        w = 1 - tt * tt * (3 - 2 * tt)
        newv = hv + (newv - hv) * w
    if end_fade:
        tf = np.clip(over / end_fade, 0, 1)
        newv = hv + (newv - hv) * (1 - tf * tf * tf * (tf * (tf * 6 - 15) + 10))
    h[act] = newv.astype(h.dtype)
    out = np.full(h.shape, 1e9, np.float32)
    out[act] = d
    return out


def smooth_profile(s, L, h0, h1, blend):
    """Ramp over 0..L, C1 continuous: slope grows linearly over [0, blend] and fades over [L-blend, L].
    Exactly h0 for s <= 0 and h1 for s >= L (never overshoots)."""
    blend = min(blend, L * 0.49)
    if blend <= 0:
        return h0 + (h1 - h0) * np.clip(s / L, 0, 1)
    b = blend
    m = 1.0 / (L - b)
    x = np.clip(s, 0, L)
    f = np.where(x < b, m * x * x / (2 * b),
        np.where(x > L - b, 1 - m * (L - x) ** 2 / (2 * b), m * (x - b / 2)))
    return h0 + (h1 - h0) * f


def road(h, p0, p1, hw, h0, h1, down_deg=40, up_deg=40, ease=True, ext=0.0, influence=None,
         edge_round=None, soft=None, blend=None):
    """Straight ramp/road from p0 (height h0) to p1 (height h1). ext: extension at both ends at constant
    height. ease: round the long profile at both ends (C1)."""
    p0 = np.asarray(p0, np.float64); p1 = np.asarray(p1, np.float64)
    L = float(np.linalg.norm(p1 - p0))
    u = (p1 - p0) / L
    n = max(2, int((L + 2 * ext) / 2))
    s = np.linspace(-ext, L + ext, n)
    pts = p0[None, :] + s[:, None] * u[None, :]
    pblend = min(L * 0.25, 200.0) if (ease and h0 != h1) else 0.0
    prof = smooth_profile(s, L, h0, h1, pblend)
    return road_polyline(h, pts, prof, hw, down_deg, up_deg, influence, edge_round, soft, blend)


def max_slope_along(h, p0, p1):
    p0 = np.asarray(p0, np.float32); p1 = np.asarray(p1, np.float32)
    L = float(np.linalg.norm(p1 - p0)); n = int(L / 4)
    s = np.linspace(0, L, n)
    pts = p0[None, :] + s[:, None] * ((p1 - p0) / L)[None, :]
    v = ndimage.map_coordinates(h, [pts[:, 1] / SQ, pts[:, 0] / SQ], order=1)
    return float(np.degrees(np.arctan(np.abs(np.diff(v)) / (L / n))).max())


# ----------------------------------------------------------------------------- slopes and flattening
def slope_deg(hm):
    """Plain geometric slope in degrees."""
    gz, gx = np.gradient(hm, SQ)
    return np.degrees(np.arctan(np.sqrt(gx * gx + gz * gz)))


def move_slope(hm):
    """Slope as the engine checks it for movement classes, expressed in 'movedef degrees'.
    Recoil averages face normals over 16x16 elmo cells (2x2 squares) and compares 1 - ny with
    1 - cos(1.5 * maxSlope). Returns arccos(ny) / 1.5 in degrees, directly comparable with the movedef
    maxSlope (tanks/hovers 18, bots/amphibians 36). Same grid as hm."""
    h = hm.astype(np.float64)
    h00, h10, h01, h11 = h[:-1, :-1], h[:-1, 1:], h[1:, :-1], h[1:, 1:]
    dx = ((h10 - h00) + (h11 - h01)) / (2 * SQ)
    dz = ((h01 - h00) + (h11 - h10)) / (2 * SQ)
    ny = 1.0 / np.sqrt(1 + dx * dx + dz * dz)
    m, n = ny.shape
    m2, n2 = m // 2 * 2, n // 2 * 2
    half = ny[:m2, :n2].reshape(m2 // 2, 2, n2 // 2, 2).mean(axis=(1, 3))
    deg = np.degrees(np.arccos(np.clip(half, -1, 1))) / 1.5
    full = np.repeat(np.repeat(deg, 2, 0), 2, 1)
    out = np.empty(hm.shape, np.float32)
    out[:full.shape[0], :full.shape[1]] = full
    out[full.shape[0]:, :] = out[full.shape[0] - 1:full.shape[0], :]
    out[:, full.shape[1]:] = out[:, full.shape[1] - 1:full.shape[1]]
    return out


def discs_mask(shape, discs):
    """Bool grid (heightmap resolution) that is True inside any disc [(x, z, radius)] (elmos).
    Only touches each disc's bounding box, so it is fast for many small discs."""
    out = np.zeros(shape, bool)
    for x, z, r in discs:
        i0, i1 = max(0, int((z - r) / SQ)), min(shape[0], int((z + r) / SQ) + 2)
        j0, j1 = max(0, int((x - r) / SQ)), min(shape[1], int((x + r) / SQ) + 2)
        if i1 <= i0 or j1 <= j0:
            continue
        ii, jj = np.mgrid[i0:i1, j0:j1]
        out[i0:i1, j0:j1] |= (ii * SQ - z) ** 2 + (jj * SQ - x) ** 2 < r * r
    return out


def flatten_disc(hm, x, z, r_in, r_out, target=None):
    """Flatten a disc (elmo coordinates) to a target height (median of the core if not given)."""
    j0, i0 = x / SQ, z / SQ
    ro = r_out / SQ
    a, b = int(max(0, i0 - ro - 1)), int(min(hm.shape[0], i0 + ro + 2))
    c, d = int(max(0, j0 - ro - 1)), int(min(hm.shape[1], j0 + ro + 2))
    ii, jj = np.mgrid[a:b, c:d]
    dist = np.sqrt((ii - i0) ** 2 + (jj - j0) ** 2) * SQ
    if target is None:
        core = dist <= r_in
        target = float(np.median(hm[a:b, c:d][core])) if core.any() else float(hm[int(i0), int(j0)])
    wgt = 1 - smoothstep(r_in, r_out, dist)
    hm[a:b, c:d] = hm[a:b, c:d] * (1 - wgt) + target * wgt
    return target

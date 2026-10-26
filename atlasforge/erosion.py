"""Terrain erosion: water carves gullies and valleys, loose material slides down to its resting angle.

Works on a half-resolution copy (fast, the effect is coarser than one heightmap square anyway) and adds
the change back to the full heightmap. Designed parts of a map are protected: start areas, metal spots,
geovents, chokes, carved ramps and steep designed walls, so templates keep working and the check report
stays valid.
"""
import numpy as np
from scipy import ndimage

from . import SQ

_NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
_DIST = np.array([np.hypot(a, b) for a, b in _NB])


def _shift(a, dz, dx):
    """Value of the neighbour (z+dz, x+dx) at every cell, edges repeated."""
    p = np.pad(a, 1, mode="edge")
    return p[1 + dz:1 + dz + a.shape[0], 1 + dx:1 + dx + a.shape[1]]


def _drainage(h, rounds):
    """Approximate drainage area (cells) with multiple-flow-direction routing, `rounds` passes."""
    drops = np.stack([np.maximum(h - _shift(h, dz, dx), 0) / d for (dz, dx), d in zip(_NB, _DIST)])
    tot = drops.sum(0)
    frac = np.where(tot > 0, drops / np.maximum(tot, 1e-9), 0)          # share of my water to neighbour k
    area = np.ones_like(h)
    for _ in range(rounds):
        inflow = np.zeros_like(h)
        for k, (dz, dx) in enumerate(_NB):
            # water arriving from neighbour (z-dz, x-dx), which sends share k towards me
            inflow += _shift(area * frac[k], -dz, -dx)
        area = 1.0 + inflow
    return area


def _slope(h, cell):
    gz, gx = np.gradient(h, cell)
    return np.hypot(gx, gz)


def _thermal(h, talus, cell, iters, rate=0.2):
    """Material above the talus slope slides to lower neighbours."""
    lim = talus * cell
    for _ in range(iters):
        delta = np.zeros_like(h)
        for (dz, dx), d in zip(_NB, _DIST):
            diff = h - _shift(h, dz, dx) - lim * d
            move = np.where(diff > 0, diff * rate / 8, 0)
            delta -= move
            delta += _shift(move, -dz, -dx)
        h = h + delta
    return h


def _droplets(h, n_drops, rng, steps=48, inertia=0.08, cap_k=5.0, min_slope=0.02, erode_k=0.35,
              deposit_k=0.25, evaporate=0.025, gravity=6.0, batch=60000, max_step=0.08):
    """Hydraulic erosion with many simulated rain droplets at once (heights in cell units, in place).
    Each droplet runs downhill, picks up material where it speeds up and drops it where it slows down."""
    nz, nx = h.shape
    flat = h.reshape(-1)
    done = 0
    while done < n_drops:
        m = min(batch, n_drops - done)
        done += m
        px = rng.uniform(0, nx - 1.001, m); pz = rng.uniform(0, nz - 1.001, m)
        dx = np.zeros(m); dz = np.zeros(m)
        speed = np.ones(m); water = np.ones(m); sed = np.zeros(m)
        alive = np.ones(m, bool)
        for _ in range(steps):
            ix = np.clip(px.astype(np.int64), 0, nx - 2); iz = np.clip(pz.astype(np.int64), 0, nz - 2)
            fx = px - ix; fz = pz - iz
            i00 = iz * nx + ix
            h00, h10, h01, h11 = flat[i00], flat[i00 + 1], flat[i00 + nx], flat[i00 + nx + 1]
            height = h00 * (1 - fx) * (1 - fz) + h10 * fx * (1 - fz) + h01 * (1 - fx) * fz + h11 * fx * fz
            gx = (h10 - h00) * (1 - fz) + (h11 - h01) * fz
            gz = (h01 - h00) * (1 - fx) + (h11 - h10) * fx
            dx = dx * inertia - gx * (1 - inertia)
            dz = dz * inertia - gz * (1 - inertia)
            ln = np.hypot(dx, dz)
            alive &= ln > 1e-9
            ln = np.where(ln > 1e-9, ln, 1)
            dx /= ln; dz /= ln
            nxp = px + dx; nzp = pz + dz
            alive &= (nxp >= 0) & (nxp < nx - 1.001) & (nzp >= 0) & (nzp < nz - 1.001)
            jx = np.clip(nxp.astype(np.int64), 0, nx - 2); jz = np.clip(nzp.astype(np.int64), 0, nz - 2)
            gx2 = nxp - jx; gz2 = nzp - jz
            j00 = jz * nx + jx
            nh = (flat[j00] * (1 - gx2) * (1 - gz2) + flat[j00 + 1] * gx2 * (1 - gz2)
                  + flat[j00 + nx] * (1 - gx2) * gz2 + flat[j00 + nx + 1] * gx2 * gz2)
            dh = nh - height
            cap = np.maximum(-dh, min_slope) * speed * water * cap_k
            depositing = (sed > cap) | (dh > 0)
            amt_dep = np.where(dh > 0, np.minimum(dh, sed), (sed - cap) * deposit_k)
            amt_ero = np.minimum((cap - sed) * erode_k, -dh)
            change = np.clip(np.where(depositing, amt_dep, -np.maximum(amt_ero, 0)), -max_step, max_step) * alive
            sed = sed - change
            for idx, wgt in ((i00, (1 - fx) * (1 - fz)), (i00 + 1, fx * (1 - fz)),
                             (i00 + nx, (1 - fx) * fz), (i00 + nx + 1, fx * fz)):
                np.add.at(flat, idx, change * wgt)
            speed = np.minimum(np.sqrt(np.maximum(speed ** 2 - dh * gravity, 0.0)), 4.0)
            water *= 1 - evaporate
            px, pz = np.where(alive, nxp, px), np.where(alive, nzp, pz)
            if not alive.any():
                break
    return h


def erode(hm, strength=0.5, protect=None, log=print, seed=0):
    """Return an eroded copy of the heightmap (elmos). strength: 0 = off, 1 = strong, >1 extreme.
    protect: bool grid (heightmap resolution) that must not change."""
    if strength <= 0:
        return hm
    h0 = np.asarray(hm, np.float64)
    small = ndimage.zoom(h0, 0.5, order=1)
    cell = SQ * h0.shape[0] / small.shape[0]
    h = small / cell                                            # heights in cell units for the droplets
    rng = np.random.default_rng(seed)
    drops = int(small.size * 0.3 * strength)
    _droplets(h, drops, rng)
    raw = h * cell - small
    change = (ndimage.gaussian_filter(np.minimum(raw, 0), 0.8)          # cuts stay crisp
              + ndimage.gaussian_filter(np.maximum(raw, 0), 2.2))       # deposits spread into smooth fans
    delta = ndimage.zoom(change, np.array(h0.shape) / np.array(small.shape), order=1)
    delta = delta[: h0.shape[0], : h0.shape[1]]
    if delta.shape != h0.shape:
        delta = np.pad(delta, [(0, h0.shape[0] - delta.shape[0]), (0, h0.shape[1] - delta.shape[1])], mode="edge")
    if protect is not None:
        keep = ndimage.gaussian_filter((~protect).astype(np.float64), 4)    # soft edge around protected areas
        delta = delta * np.clip(keep * 1.6 - 0.3, 0, 1)
    return (h0 + delta).astype(np.float32)


def symmetric_like(original, delta, sym=None):
    """Make a change field follow every mirror symmetry the original heightmap has.
    sym: a rotation symmetry (free-for-all) is applied directly (rotated grids cannot be detected)."""
    if sym is not None and hasattr(sym, "symmetric"):
        return sym.symmetric(delta).astype(np.float32)
    imgs = [delta]
    for f in (lambda a: a[:, ::-1], lambda a: a[::-1, :], lambda a: a[::-1, ::-1]):
        if np.abs(original - f(original)).max() < 0.5:
            imgs.append(f(delta))
    return np.mean(imgs, axis=0)

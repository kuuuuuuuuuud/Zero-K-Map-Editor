"""General resource settings applied after a template: number of metal spots and geothermal vents.

Every change keeps the map fair: spots are added and removed as whole symmetry orbits (one spot plus all
its mirror images), so every side gets the same. Base spots near a start point are never removed.
New spots go on flat, reachable ground, as far as possible from existing spots, bases and the map edge.
"""
import math

import numpy as np
from scipy import ndimage

from . import SQ
from .decor import symmetry_ops
from .terrain import discs_mask, flatten_disc, slope_deg

BASE_RADIUS = 900          # spots this close to a start point belong to the base and are never removed
ORBIT_TOL = 40             # elmos: two points closer than this are the same mirror image


def parts(d):
    """How many symmetric parts a design has (2 = two sides, 4 = quarters, N = players on a free-for-all
    map, 1 = not symmetric). d: Design (or a bare heightmap for mirror-only maps)."""
    if isinstance(d, np.ndarray):
        return max(1, len(symmetry_ops(d)))
    return max(1, len(symmetry_ops(d.hm, d.sym)))


def _orbits(points, ops):
    """Group points (x, z) into symmetry orbits. -> list of index lists."""
    left = list(range(len(points)))
    out = []
    while left:
        i = left.pop(0)
        x, z = points[i]
        grp = [i]
        for ox, oz in (op(x, z) for op in ops[1:]):
            for j in list(left):
                if math.hypot(points[j][0] - ox, points[j][1] - oz) < ORBIT_TOL:
                    grp.append(j)
                    left.remove(j)
                    break
        out.append(grp)
    return out


def _is_base(d, x, z):
    return any(math.hypot(x - p[0], z - p[1]) < BASE_RADIUS for p in d.starts)


def _side_of(d, x, z):
    best, side = 1e18, 0
    for k, team in enumerate(d.teams):
        for p in team:
            dd = math.hypot(x - p[0], z - p[1])
            if dd < best:
                best, side = dd, k
    return side


def _reach_mask(d):
    """Cells a builder of side 0 can reach (tanks on land maps, amphibians on naval maps)."""
    from .checks import cell, unit_masks
    masks = unit_masks(d.hm)
    cls = "amphibians" if d.movement_profile == "naval" else "tanks"
    lab, _ = ndimage.label(masks[cls])
    ids = {lab[cell(p)] for p in d.starts} - {0}
    return np.isin(lab, list(ids)) if ids else np.zeros(d.hm.shape, bool)


def _candidates(d, margin_frac=0.07):
    """Bool grid of cells where a new spot may go."""
    hm = d.hm
    n0, n1 = hm.shape
    ok = _reach_mask(d)
    flat = ndimage.maximum_filter(slope_deg(hm), size=int(2 * 90 / SQ) + 1) < 14
    ok &= flat
    if d.movement_profile == "naval":
        ok &= (hm > 6) | (hm < -40)        # dry land or deep enough water for ships and amphibians
    else:
        ok &= hm > 6
    for extra in (d.keep_clear, d.blocked, d.hazard):
        if extra is not None:
            ok &= ~ndimage.binary_dilation(extra, iterations=6)
    for _, gm in d.gates or []:
        ok &= ~ndimage.binary_dilation(gm, iterations=4)
    m = int(margin_frac * n1)
    ok[:m] = ok[-m:] = False
    ok[:, :m] = ok[:, -m:] = False
    ok &= ~discs_mask(hm.shape, [(p[0], p[1], BASE_RADIUS * 0.75) for p in d.starts])
    return ok


def _add(d, kind, n_orbits, rng):
    """Add n_orbits new orbits of metal spots (kind "mex") or geos (kind "geo"). -> number added."""
    hm = d.hm
    ops = symmetry_ops(hm, d.sym)
    W = (hm.shape[1] - 1) * SQ
    cand = _candidates(d)
    ii, jj = np.nonzero(cand[::4, ::4])
    pts = np.stack([jj * 4 * SQ, ii * 4 * SQ], 1).astype(np.float64)
    if not len(pts):
        return 0
    min_pair = 520.0                                  # mirror images of one spot must be this far apart
    good = []
    for x, z in pts:
        orb = [op(x, z) for op in ops]
        if all(math.hypot(a[0] - b[0], a[1] - b[1]) >= min_pair or (a == b) for a in orb for b in orb if a is not b):
            if len({(round(a[0]), round(a[1])) for a in orb}) == len(orb):
                good.append((x, z))
    if not good:
        return 0
    pts = np.array(good)
    taken = [(m["x"], m["z"]) for m in d.mexes] + [(g[0], g[1]) for g in d.geos]
    starts = [(p[0], p[1]) for p in d.starts]
    added = 0
    for _ in range(n_orbits):
        def dist(src):
            if not src:
                return np.full(len(pts), 1e9)
            s = np.array(src, np.float64)
            return np.sqrt(((pts[:, None, :] - s[None, :, :]) ** 2).sum(-1)).min(1)
        score = np.minimum(dist(taken), dist(starts) - 350)
        if kind == "geo":
            score = np.minimum(score, dist([(g[0], g[1]) for g in d.geos]) * 0.6)
        if score.max() < (260 if kind == "mex" else 380):
            break
        top = np.argsort(-score)[:6]
        x, z = pts[rng.choice(top)]
        orb = [op(float(x), float(z)) for op in ops]
        if kind == "mex":
            value = _new_value(d, x, z)
            for ox, oz in orb:
                flatten_disc(hm, ox, oz, 45, 100)
                d.mexes.append(dict(x=float(ox), z=float(oz), metal=value, side=_side_of(d, ox, oz)))
        else:
            for ox, oz in orb:
                flatten_disc(hm, ox, oz, 55, 110)
                d.geos.append((float(ox), float(oz)))
        taken += orb
        added += 1
    return added


def _new_value(d, x, z):
    """Metal of a new spot: like the template's expansion spots, a bit richer further from home."""
    exp = [m["metal"] for m in d.mexes if not m.get("fixed") and not _is_base(d, m["x"], m["z"])]
    base = float(np.median(exp)) if exp else 2.0
    W = (d.hm.shape[1] - 1) * SQ
    near = min(math.hypot(x - p[0], z - p[1]) for p in d.starts)
    return round(min(base * 1.25, base * (0.9 + 0.25 * near / (W / 2))), 2)


def _remove_mex(d, n_orbits):
    """Remove n_orbits expansion orbits, the most crowded ones first. -> number removed."""
    ops = symmetry_ops(d.hm, d.sym)
    removed = 0
    for _ in range(n_orbits):
        pts = [(m["x"], m["z"]) for m in d.mexes]
        orbs = [g for g in _orbits(pts, ops)
                if not any(d.mexes[i].get("fixed") or _is_base(d, *pts[i]) for i in g)]
        if not orbs:
            break
        arr = np.array(pts)

        def crowd(g):
            i = g[0]
            dd = np.hypot(arr[:, 0] - arr[i, 0], arr[:, 1] - arr[i, 1])
            dd[g] = 1e9
            return dd.min()
        g = min(orbs, key=crowd)
        d.mexes = [m for k, m in enumerate(d.mexes) if k not in g]
        removed += 1
    return removed


def _remove_geo(d, n_orbits):
    ops = symmetry_ops(d.hm, d.sym)
    removed = 0
    for _ in range(n_orbits):
        orbs = _orbits([(g[0], g[1]) for g in d.geos], ops)
        if not orbs:
            break
        # drop the orbit closest to the bases (the far ones are worth fighting over)
        g = min(orbs, key=lambda o: min(math.hypot(d.geos[o[0]][0] - p[0], d.geos[o[0]][1] - p[1]) for p in d.starts))
        d.geos = [x for k, x in enumerate(d.geos) if k not in g]
        removed += 1
    return removed


def set_counts(d, mex_count=0, geo_count="default", seed=0):
    """Change the number of metal spots / geos per symmetric part. 0 or "default" = keep the template's.
    Spots are added and removed as whole mirror sets (orbits); a spot on a mirror axis counts for a part
    of each side. Notes for the check report are appended to d.notes. Returns the word for a part."""
    rng = np.random.default_rng(seed + 4242)
    k = parts(d)
    per = "per player" if hasattr(d.sym, "ops") else "per side" if k == 2 else ("per quarter" if k == 4 else ("on the map" if k == 1 else f"per part ({k})"))
    if mex_count:
        while len(d.mexes) / k > mex_count + 0.01 and _remove_mex(d, 1):
            pass
        if len(d.mexes) / k < mex_count - 0.01:
            want = math.ceil(mex_count - len(d.mexes) / k - 0.01)
            if _add(d, "mex", want, rng) < want:
                d.notes.append(f"Only room for {len(d.mexes) / k:.0f} metal spots {per} "
                               f"(asked for {mex_count}); the rest of the map is too steep, wet or blocked")
        base = sum(1 for m in d.mexes if m.get("fixed") or _is_base(d, m["x"], m["z"])) / k
        if len(d.mexes) / k > mex_count + 0.01 and base > mex_count:
            d.notes.append(f"{base:.0f} metal spots {per} belong to the bases and stay")
    if geo_count not in ("default", None, ""):
        geo_count = int(geo_count)
        while len(d.geos) / k > geo_count + 0.01 and _remove_geo(d, 1):
            pass
        if len(d.geos) / k < geo_count - 0.01:
            want = math.ceil(geo_count - len(d.geos) / k - 0.01)
            if _add(d, "geo", want, rng) < want:
                d.notes.append(f"Only room for {len(d.geos) / k:.0f} geothermal vents {per} (asked for {geo_count})")
    return per


WIND = {"calm": (0, 5), "low": (2, 12), "medium": (5, 20), "high": (10, 28), "storm": (18, 35)}

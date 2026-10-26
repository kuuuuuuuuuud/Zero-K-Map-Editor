"""Random tree placement (Zero-K feature types treetype0..15)."""
import numpy as np

from . import SQ
from .noise import fbm, norm01
from .terrain import slope_deg


def place_trees(hm, sym, mexes, geos, starts, biome, rng, water_h, keep_clear=None):
    """Symmetric forest patches. keep_clear: optional bool grid (heightmap resolution) without trees,
    e.g. carved ramps. Returns [(type 0..15, x, y, z, rotation)]."""
    if not biome["trees"]:
        return []
    nz, nx = hm.shape
    dens = norm01(fbm(hm.shape, rng, base=nx / 64 * 1.5, octaves=4))
    dens = 0.5 * (dens + sym.mirror_grid(dens))
    sl = slope_deg(hm)
    trees = []
    target = int(nx * nz / 64 * 0.5 * biome["tree_density"])
    W, H = sym.W, sym.H
    blockers = [(m["x"], m["z"], 120) for m in mexes] + [(g[0], g[1], 150) for g in geos] + \
               [(s[0], s[1], 700) for s in starts]
    cell = lambda x, z: (min(nz - 1, int(z / SQ)), min(nx - 1, int(x / SQ)))
    tries = 0
    while len(trees) < target and tries < target * 30:
        tries += 1
        x, z = rng.uniform(40, W - 40), rng.uniform(40, H - 40)
        if sym.side(x, z) >= 0:
            continue
        i, j = cell(x, z)
        if dens[i, j] < 0.62 or sl[i, j] > 20 or hm[i, j] < water_h + 6:
            continue
        copies = sym.orbit(x, z)[1:] if hasattr(sym, "orbit") else [sym.mirror(x, z)]
        copies = [(cx, cz) for cx, cz in copies if 0 <= cx < W and 0 <= cz < H]
        if keep_clear is not None and (keep_clear[i, j] or any(keep_clear[cell(cx, cz)] for cx, cz in copies)):
            continue
        if rng.random() > (dens[i, j] - 0.6) * 3:
            continue
        if any((x - bx) ** 2 + (z - bz) ** 2 < br * br for bx, bz, br in blockers):
            continue
        t = int(rng.integers(0, 16))
        rot = float(rng.uniform(0, 65535))
        trees.append((t, x, float(hm[i, j]), z, rot))
        for cx, cz in copies:
            trees.append((t, cx, float(hm[cell(cx, cz)]), cz, rot))
    return trees


def grass_map(hm, biome, rng, water_h=0.0, keep_clear=None, paint=None, mexes=(), geos=()):
    """Engine grass (SMF vegetation map): uint8 grid at 1/4 heightmap resolution (32 elmo cells), 255 = grass.
    None when the biome has no grass. Grass is only decoration (no effect on movement or sight)."""
    g = biome.get("grass") or {}
    dens = float(g.get("density", 0)) * float(biome.get("grass_mul", 1.0))
    if dens <= 0:
        return None
    nz, nx = (hm.shape[0] - 1) // 4, (hm.shape[1] - 1) // 4
    h = hm[:-1:4, :-1:4][:nz, :nx]
    sl = slope_deg(hm)[:-1:4, :-1:4][:nz, :nx]
    patches = norm01(fbm((nz, nx), rng, base=max(4, nx / 24), octaves=4))
    ok = patches > 1 - min(0.95, 0.65 * dens)
    ok &= sl < 18
    ok &= h > water_h + 6
    ok &= h / 340.0 < biome.get("peak_level", 1.0) - 0.06                    # no grass in the snow
    def coarse(a):
        return np.asarray(a)[:-1:4, :-1:4][:nz, :nx] if a is not None else None
    if keep_clear is not None:
        ok &= ~coarse(keep_clear)
    for k in ("lava", "scorch", "concrete", "molten", "path", "ice"):
        if paint and paint.get(k) is not None:
            ok &= coarse(paint[k]) < 0.3
    jj, ii = np.meshgrid(np.arange(nx) * 32 + 16, np.arange(nz) * 32 + 16)
    for x, z, r in [(m["x"], m["z"], 60) for m in mexes] + [(p[0], p[1], 100) for p in geos]:
        ok &= (jj - x) ** 2 + (ii - z) ** 2 > r * r
    return np.where(ok, 255, 0).astype(np.uint8)

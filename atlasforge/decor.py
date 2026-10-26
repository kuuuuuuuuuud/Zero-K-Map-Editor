"""Map decoration that players can reclaim: rock clusters (own 3D models, crystals on alien worlds) and
battlefield wrecks of Zero-K units. Placed symmetrically (same metal for every side), away from bases,
metal spots, chokes and ramps."""
import math

import numpy as np
from scipy import ndimage

from . import SQ
from .models import feature_pack
from .terrain import slope_deg

# Zero-K unit wrecks: (feature name, metal of the wreck = 40 % of the unit cost, footprint radius)
WRECKS_SMALL = [("cloakraid_dead", 26, 30), ("shieldraid_dead", 30, 30), ("vehraid_dead", 52, 34),
                ("hoverraid_dead", 32, 34), ("cloakskirm_dead", 36, 30), ("vehsupport_dead", 58, 36)]
WRECKS_MEDIUM = [("cloakriot_dead", 84, 40), ("shieldriot_dead", 100, 40), ("spiderriot_dead", 96, 40),
                 ("vehassault_dead", 100, 44), ("jumpskirm_dead", 96, 40), ("tankraid_dead", 68, 44),
                 ("hoverriot_dead", 160, 48), ("tankriot_dead", 200, 52)]
WRECKS_LARGE = [("tankassault_dead", 340, 60), ("jumpassault_dead", 240, 56), ("tankarty_dead", 280, 58)]
WRECKS_GIANT = [("striderdante_dead", 1400, 90), ("striderscorpion_dead", 1200, 90)]


def symmetry_ops(hm, sym=None):
    """Mirror operations (on points) under which the heightmap is symmetric.
    sym: the design's symmetry; a rotation symmetry (free-for-all) gives its rotations directly,
    because rotated grids are only symmetric up to interpolation and cannot be detected exactly."""
    if sym is not None and hasattr(sym, "ops"):
        return sym.ops()
    W = (hm.shape[1] - 1) * SQ
    H = (hm.shape[0] - 1) * SQ
    ops = [lambda x, z: (x, z)]
    if np.abs(hm - hm[:, ::-1]).max() < 0.5:
        ops.append(lambda x, z: (W - x, z))
    if np.abs(hm - hm[::-1, :]).max() < 0.5:
        ops.append(lambda x, z: (x, H - z))
    if np.abs(hm - hm[::-1, ::-1]).max() < 0.5:
        ops.append(lambda x, z: (W - x, H - z))
    return ops


def _orbit(ops, x, z):
    return [op(x, z) for op in ops]


def _canonical(ops, x, z):
    """True if (x, z) is the representative of its symmetry orbit (so every orbit is placed once)."""
    return min(_orbit(ops, x, z), key=lambda p: (round(p[1], 3), round(p[0], 3))) == (x, z) or len(ops) == 1


def _free_mask(d, margin_start=750, margin_mex=170, margin_geo=180):
    from .terrain import discs_mask
    hm = d.hm
    bad = hm < 6                                                  # no decoration in water or lava
    bad |= discs_mask(hm.shape, [(p[0], p[1], margin_start) for p in d.starts]
                      + [(m["x"], m["z"], margin_mex) for m in d.mexes] + [(g[0], g[1], margin_geo) for g in d.geos])
    for _, gm in d.gates or []:
        bad |= gm
    for extra in (d.keep_clear, d.blocked, d.hazard):
        if extra is not None:
            bad |= extra
    return ~ndimage.binary_dilation(bad, iterations=2)


def _accept(pts, x, z, r):
    return all((x - px) ** 2 + (z - pz) ** 2 > (r + pr) ** 2 for px, pz, pr in pts)


def place(d, rocks=0.5, wrecks=0.3, seed=0, biome_name=""):
    """Add rocks and wrecks to a design (features, extra files). Returns reclaim metal
    (rocks, wrecks, symmetric copies): metal per symmetric part of the map and how many parts there are."""
    if rocks <= 0 and wrecks <= 0:
        return 0.0, 0.0, 1
    rng = np.random.default_rng(seed + 777)
    hm = d.hm
    W = (hm.shape[1] - 1) * SQ
    H = (hm.shape[0] - 1) * SQ
    ops = symmetry_ops(hm, d.sym)
    sides = max(1, len(ops))
    free = _free_mask(d)
    sl = slope_deg(hm)
    cell = lambda x, z: (min(hm.shape[0] - 1, max(0, int(z / SQ))), min(hm.shape[1] - 1, max(0, int(x / SQ))))
    placed = []                                                   # (x, z, radius) of everything placed
    feats = []
    metal_rocks = metal_wrecks = 0.0

    def ok(x, z, r, max_slope):
        if not (r < x < W - r and r < z < H - r):
            return False
        i, j = cell(x, z)
        if not free[i, j] or sl[i, j] > max_slope:
            return False
        return all(_accept(placed, ox, oz, r) and free[cell(ox, oz)] for ox, oz in _orbit(ops, x, z))

    def put(name, x, z, r, rot):
        for ox, oz in _orbit(ops, x, z):
            feats.append((name, float(ox), float(oz), float(rot)))
            placed.append((ox, oz, r))

    area = W * H / 1e6                                            # in km^2 of elmos
    if rocks > 0:
        files, kinds = feature_pack(biome_name, d.biome, np.random.default_rng(seed + 778))
        rock_kinds = [k for k in kinds.values() if k.family == "rock"]
        crystal_kinds = [k for k in kinds.values() if k.family == "crystal"]
        by_size = sorted(rock_kinds, key=lambda k: k.radius)
        # cluster centres prefer the foot of slopes and hillsides
        pref = np.clip(ndimage.gaussian_filter((sl > 22).astype(np.float32), 6) * 3, 0, 1) * 0.7 + 0.3
        n_clusters = int(round(1.1 * rocks * area / sides))           # clusters per symmetric part
        tries = 0
        used = False
        while n_clusters > 0 and tries < n_clusters * 60:
            tries += 1
            cx, cz = rng.uniform(0, W), rng.uniform(0, H)
            if not _canonical(ops, cx, cz) or rng.random() > pref[cell(cx, cz)]:
                continue
            if not ok(cx, cz, 60, 32):
                continue
            n_clusters -= 1
            crystal = bool(crystal_kinds) and rng.random() < 0.35
            for k in range(int(rng.integers(2, 7))):
                if crystal:
                    kind = crystal_kinds[min(len(crystal_kinds) - 1, int(rng.integers(0, len(crystal_kinds))))]
                else:
                    w = np.array([0.38, 0.38, 0.27, 0.27, 0.1, 0.1, 0.035, 0.035])[:len(by_size)]
                    kind = by_size[int(rng.choice(len(by_size), p=w / w.sum()))]
                a, rr = rng.uniform(0, 2 * math.pi), rng.uniform(0, 170)
                x, z = cx + rr * math.cos(a), cz + rr * math.sin(a)
                if _canonical(ops, x, z) or len(ops) == 1:
                    if ok(x, z, kind.radius, 30):
                        put(kind.name, x, z, kind.radius, rng.uniform(0, 65535))
                        metal_rocks += kind.metal
                        used = True
        if used:
            d.extra_files.update(files)
    if wrecks > 0:
        bases = [t[0] for t in d.teams if t]
        n_clusters = int(round(0.18 * wrecks * area / sides))
        tries = 0
        while n_clusters > 0 and tries < n_clusters * 200:
            tries += 1
            cx, cz = rng.uniform(0, W), rng.uniform(0, H)
            if not _canonical(ops, cx, cz):
                continue
            near = sorted(bases, key=lambda b: (cx - b[0]) ** 2 + (cz - b[1]) ** 2)[:2]
            d0, d1 = (math.hypot(cx - b[0], cz - b[1]) for b in near)
            D = math.hypot(near[1][0] - near[0][0], near[1][1] - near[0][1])
            if abs(d0 - d1) > 0.45 * D:                            # battle zone between the two nearest bases
                continue
            if not ok(cx, cz, 80, 14):
                continue
            n_clusters -= 1
            big = rng.random()
            pool = WRECKS_GIANT if big < 0.06 else WRECKS_LARGE if big < 0.3 else WRECKS_MEDIUM
            members = [pool[int(rng.integers(len(pool)))]] + [
                (WRECKS_SMALL + WRECKS_MEDIUM)[int(rng.integers(len(WRECKS_SMALL) + len(WRECKS_MEDIUM)))]
                for _ in range(int(rng.integers(1, 4)))]
            for k, (name, metal, r) in enumerate(members):
                a, rr = rng.uniform(0, 2 * math.pi), 0 if k == 0 else rng.uniform(r + 30, 220)
                x, z = cx + rr * math.cos(a), cz + rr * math.sin(a)
                if ok(x, z, r, 16):
                    put(name, x, z, r, rng.uniform(0, 65535))
                    metal_wrecks += metal
    d.features = list(d.features) + feats
    if feats:
        tb = np.zeros(hm.shape, bool) if d.tree_block is None else d.tree_block.copy()
        for x, z, r in placed:                                    # no trees growing through rocks and wrecks
            i, j = cell(x, z)
            rc = int(r / SQ) + 2
            tb[max(0, i - rc):i + rc + 1, max(0, j - rc):j + rc + 1] = True
        d.tree_block = tb
    return metal_rocks, metal_wrecks, sides

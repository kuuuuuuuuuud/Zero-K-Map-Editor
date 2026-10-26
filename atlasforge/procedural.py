"""Procedural skirmish maps: noise terrain in five styles, symmetric resources and automatic ramps that
guarantee tanks can reach the enemy base and every metal spot."""
import math

import numpy as np
from scipy import ndimage

from . import SQ
from .archive import build_archive
from .biomes import BIOMES
from .config import ForgeConfig
from .noise import fbm, norm01, ridged, smoothstep, terrace
from .symmetry import Symmetry
from .terrain import flatten_disc, move_slope, road_polyline, slope_deg

STYLES = ("hills", "plateaus", "canyon", "islands", "crater")
LAYOUTS = ("diag", "ns", "ew")
TANK_SLOPE = 15.0     # ZK tank maxSlope is 18 movedef degrees; keep a margin
TANK_DEPTH = 20.0     # max. water depth for tanks


def make_terrain(nx, nz, style, rng):
    """Height in elmos (water level = 0)."""
    shape = (nz + 1, nx + 1)
    units = min(nx, nz) / 64.0
    macro = norm01(fbm(shape, rng, base=units / 4 + 1.6, octaves=6, gain=0.5))
    detail = fbm(shape, rng, base=units * 3, octaves=4, gain=0.55)
    if style == "hills":
        rid = ridged(shape, rng, base=units / 3.5 + 1.0)
        mount = smoothstep(0.72, 0.95, rid) * smoothstep(0.35, 0.7, macro)
        h = macro * 190 - 25 + mount * 210 + detail * 10
    elif style == "plateaus":
        t = terrace(norm01(macro * 0.8 + 0.2 * norm01(fbm(shape, rng, base=units, octaves=4))), 4,
                    sharp=0.07, rng=rng, units=units)
        h = t * 300 - 20 + detail * 7
    elif style == "canyon":
        riv = np.abs(fbm(shape, rng, base=units / 3 + 0.9, octaves=5))
        riv = ndimage.gaussian_filter(riv, 2.0)
        valley = 1 - smoothstep(0.03, 0.09, riv)            # 1 = river bed
        bank = 1 - smoothstep(0.07, 0.2, riv)
        hi = terrace(macro, 2, sharp=0.1, rng=rng, units=units)
        h = 45 + hi * 160 - bank * 70 - valley * 60 + detail * 5 * smoothstep(0.1, 0.3, riv)
    elif style == "islands":
        h = norm01(macro * 0.8 + 0.2 * norm01(fbm(shape, rng, base=units, octaves=4)))
        e = h - 0.45
        h = np.where(e > 0, e * 210 + 25 * smoothstep(0.02, 0.2, e), e * 300) + \
            detail * 4 * smoothstep(0.0, 0.05, np.abs(e))
    elif style == "crater":
        h = macro * 120 + detail * 10
        zz, xx = np.mgrid[0:shape[0], 0:shape[1]].astype(np.float32)
        ncr = int(rng.integers(int(units * 1.5), int(units * 2.5)))
        for k in range(ncr):
            cx, cz = rng.uniform(0, shape[1]), rng.uniform(0, shape[0])
            r = (rng.uniform(0.05, 0.12) if k < ncr // 3 else rng.uniform(0.015, 0.04)) * min(shape)
            d = np.sqrt((xx - cx) ** 2 + (zz - cz) ** 2) / r
            depth = rng.uniform(50, 110)
            h += -depth * np.clip(1 - d ** 2, 0, 1) + 0.45 * depth * np.exp(-((d - 1.0) / 0.2) ** 2)
        h += 20
    else:
        raise ValueError(f"unknown style {style!r}, expected one of {STYLES}")
    return h.astype(np.float32)


class _Carver:
    """Cuts ramps until bases and metal spots are reachable for tanks."""

    def __init__(self, hm, water_ok):
        self.water_ok = water_ok
        self.mask = np.zeros(hm.shape, bool)          # carved corridors (kept free of trees)

    def passable(self, hm):
        p = (move_slope(hm) < TANK_SLOPE) & (hm > -TANK_DEPTH)
        if self.water_ok:
            p |= hm < 0
        return p

    def route(self, hm, p0, p1):
        from skimage.graph import route_through_array
        ds = 2
        small = hm[::ds, ::ds]
        sl = slope_deg(hm)[::ds, ::ds]
        cost = 1.0 + (sl / 10.0) ** 3 + (0.0 if self.water_ok else 40.0) * (small < -TANK_DEPTH)
        if self.water_ok:
            cost = np.where(small < 0, 1.0, cost)
        a = (min(small.shape[0] - 1, int(p0[1] / SQ / ds)), min(small.shape[1] - 1, int(p0[0] / SQ / ds)))
        b = (min(small.shape[0] - 1, int(p1[1] / SQ / ds)), min(small.shape[1] - 1, int(p1[0] / SQ / ds)))
        path, _ = route_through_array(cost, a, b, fully_connected=True, geometric=True)
        path = np.array(path, np.float32) * ds
        seg = np.sqrt((np.diff(path, axis=0) ** 2).sum(1))
        t = np.concatenate([[0], np.cumsum(seg)])
        n = max(2, int(t[-1]))
        ts = np.linspace(0, t[-1], n)
        pi = np.interp(ts, t, path[:, 0]); pj = np.interp(ts, t, path[:, 1])
        pi = ndimage.gaussian_filter1d(pi, 4, mode="nearest"); pj = ndimage.gaussian_filter1d(pj, 4, mode="nearest")
        prof = ndimage.map_coordinates(hm, [pi, pj], order=1)
        if not self.water_ok:
            prof = np.maximum(prof, -TANK_DEPTH * 0.4)
        maxgrad = math.tan(math.radians(TANK_SLOPE * 0.65)) * SQ
        for _ in range(200):
            if np.abs(np.diff(prof)).max() <= maxgrad:
                break
            prof = ndimage.gaussian_filter1d(prof, 3, mode="nearest")
        return pi, pj, prof

    def stamp(self, hm, pi, pj, prof, hw=90):
        """Ramp along (pi, pj) [heightmap indices]: flat core, 35 degree flanks, no steps."""
        if self.water_ok:
            keep = prof > -5
            pi, pj, prof = pi[keep], pj[keep], prof[keep]
            if len(pi) < 2:
                return
        pts = np.stack([pj * SQ, pi * SQ], 1).astype(np.float64)
        prof = np.asarray(prof, np.float64)
        if len(pts) > 8:                       # smooth the pixel path and resample densely
            sig = min(6.0, len(pts) / 6)
            pts = np.stack([ndimage.gaussian_filter1d(pts[:, 0], sig, mode="nearest"),
                            ndimage.gaussian_filter1d(pts[:, 1], sig, mode="nearest")], 1)
            prof = ndimage.gaussian_filter1d(prof, sig, mode="nearest")
            sl = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
            sn = np.linspace(0, sl[-1], max(2, int(sl[-1] / 2)))
            pts = np.stack([np.interp(sn, sl, pts[:, 0]), np.interp(sn, sl, pts[:, 1])], 1)
            prof = np.interp(sn, sl, prof)
        before = hm.copy()
        d = road_polyline(hm, pts, prof, hw, down_deg=35, up_deg=35, influence=hw + 1200, end_fade=hw * 2.5)
        # tight bends leave radial streaks and creases (the nearest road point jumps): smooth the change the
        # ramp made, not the terrain itself, so the natural detail around it stays sharp
        hm[:] = before + ndimage.gaussian_filter(hm - before, 2.5)
        self.mask |= d < hw + 40

    def ensure(self, hm, sym, starts, mexes, log, max_iter=25):
        """Returns indices of team-0 mexes that stay unreachable."""
        tried = {}
        targets = []
        for it in range(max_iter + 1):
            lab, _ = ndimage.label(self.passable(hm))

            def L(p):
                i, j = int(p[1] / SQ), int(p[0] / SQ)
                win = lab[max(0, i - 3):i + 4, max(0, j - 3):j + 4]
                v = win[win > 0]
                return np.bincount(v).argmax() if v.size else 0
            base_lab = L(starts[0])
            targets = []
            if L(starts[1]) != base_lab or base_lab == 0:
                targets.append(("start", starts[1]))
            for k, m in enumerate(mexes):
                if m["side"] == 0 and L((m["x"], m["z"])) != base_lab:
                    targets.append((k, (m["x"], m["z"])))
            if not targets:
                log(f"  connectivity ok ({it} ramps)")
                return []
            if it == max_iter:
                break
            key, tgt = min(targets, key=lambda t: tried.get(t[0], 0))     # least tried target first
            if tried.get(key, 0) >= 3:
                break
            tried[key] = tried.get(key, 0) + 1
            pi, pj, prof = self.route(hm, starts[0], tgt)
            self.stamp(hm, pi, pj, prof)
            mx = np.array([sym.mirror(j * SQ, i * SQ) for i, j in zip(pi, pj)])
            self.stamp(hm, mx[:, 1] / SQ, mx[:, 0] / SQ, prof)
        if any(k == "start" for k, _ in targets):
            log("  warning: bases are not connected for tanks")
        return [k for k, _ in targets if k != "start"]


def place_resources(hm, sym, starts, units, rng, log, mex_per_side=None):
    """Symmetric metal spots (3 at each base, rest by Poisson sampling, richer towards the centre)
    and geovents."""
    W, H = sym.W, sym.H
    sl = slope_deg(ndimage.gaussian_filter(hm, 2))
    if mex_per_side is None:
        mex_per_side = int(round(0.11 * units * units + 3))
    mexes = []

    def ok(x, z, mind=330, minmirror=500):
        if x < 160 or z < 160 or x > W - 160 or z > H - 160:
            return False
        for m in mexes:
            if (m["x"] - x) ** 2 + (m["z"] - z) ** 2 < mind ** 2:
                return False
        mx, mz = sym.mirror(x, z)
        return (mx - x) ** 2 + (mz - z) ** 2 >= minmirror ** 2

    def add(x, z, metal):
        mexes.append(dict(x=float(x), z=float(z), metal=metal, side=0))
        mx, mz = sym.mirror(x, z)
        mexes.append(dict(x=float(mx), z=float(mz), metal=metal, side=1))

    sx, sz = starts[0]
    cx, cz = W / 2, H / 2
    ang0 = math.atan2(cz - sz, cx - sx)
    for da in (-1.6, 0.0, 1.6):                     # base mexes
        for _ in range(40):
            a = ang0 + math.pi + da + rng.uniform(-0.35, 0.35)
            r = rng.uniform(230, 330)
            x, z = sx + r * math.cos(a), sz + r * math.sin(a)
            x = min(max(x, 170), W - 170); z = min(max(z, 170), H - 170)
            if ok(x, z, mind=200):
                add(x, z, 2.0)
                break
    cand = 0
    side_r = math.hypot(W, H)
    while len(mexes) < 2 * mex_per_side and cand < 20000:
        cand += 1
        x, z = rng.uniform(160, W - 160), rng.uniform(160, H - 160)
        if sym.side(x, z) >= 0:
            continue
        i, j = int(z / SQ), int(x / SQ)
        if sl[i, j] > 10 or hm[i, j] < 2:
            continue
        if math.hypot(x - sx, z - sz) < 550:
            continue
        if not ok(x, z):
            continue
        dc = abs(sym.side(x, z)) / (0.5 * side_r)       # closer to the centre = richer
        metal = round(float(np.clip(2.6 - 1.4 * dc + rng.uniform(-0.2, 0.2), 1.5, 3.0)), 1)
        add(x, z, metal)
    log(f"  {len(mexes)} metal spots")

    geos = []                                         # 1 per side (2 from 16x16)
    ngeo = 1 if units < 16 else 2
    for _ in range(4000):
        if len(geos) >= 2 * ngeo:
            break
        x, z = rng.uniform(300, W - 300), rng.uniform(300, H - 300)
        s = sym.side(x, z)
        if s >= -250 or s < -0.35 * side_r:
            continue
        i, j = int(z / SQ), int(x / SQ)
        if sl[i, j] > 8 or hm[i, j] < 5:
            continue
        if math.hypot(x - sx, z - sz) < 900:
            continue
        if any(math.hypot(x - m["x"], z - m["z"]) < 260 for m in mexes):
            continue
        if any(math.hypot(x - g[0], z - g[1]) < 1200 for g in geos):
            continue
        geos.append((x, z)); geos.append(sym.mirror(x, z))
    return mexes, geos


def design(size=(12, 12), seed=1, biome="temperate", style="hills", layout="diag", relief=None,
           mex_per_side=None, log=print):
    """Procedural skirmish design (heightmap, resources, carved ramps). size: Spring map units."""
    from .design import Design
    if biome not in BIOMES:
        raise ValueError(f"unknown biome {biome!r}, expected one of {sorted(BIOMES)}")
    if layout not in LAYOUTS:
        raise ValueError(f"unknown layout {layout!r}, expected one of {LAYOUTS}")
    ux, uz = size
    if any(v % 2 or v < 4 or v > 32 for v in size):
        raise ValueError("size: even values between 4 and 32")
    rng = np.random.default_rng(seed)
    nx, nz = ux * 64, uz * 64
    W, H = nx * SQ, nz * SQ
    sym = Symmetry(layout, W, H)

    hm = make_terrain(nx, nz, style, rng)
    carver = _Carver(hm, water_ok=(style == "islands"))
    if relief:
        hm *= relief
    hm = sym.symmetrize(hm, band=0.06 * min(W, H)).astype(np.float32)
    for _ in range(2):            # widen very steep edges a little (real ZK cliffs are 40-90 elmos wide)
        w_ = smoothstep(40, 70, slope_deg(hm))
        hm = hm * (1 - w_) + ndimage.gaussian_filter(hm, 1.6) * w_

    starts = sym.starts()
    flatten_disc(hm, starts[0][0], starts[0][1], 380, 750)          # raise above water and flatten bases
    tgt = max(float(hm[int(starts[0][1] / SQ), int(starts[0][0] / SQ)]), 45.0)
    for (x, z) in starts:
        flatten_disc(hm, x, z, 380, 760, target=tgt)

    mexes, geos = place_resources(hm, sym, starts, min(ux, uz), rng, log, mex_per_side)
    for m in mexes:
        flatten_disc(hm, m["x"], m["z"], 48, 110)
    for g in geos:
        flatten_disc(hm, g[0], g[1], 60, 130)

    bad = carver.ensure(hm, sym, starts, mexes, log)
    if bad:
        drop = set()
        for k in bad:
            drop.add(k); drop.add(k + 1)          # the mirrored mex always follows directly
        mexes = [m for i, m in enumerate(mexes) if i not in drop]
        log(f"  removed {len(bad)} unreachable mex pairs -> {len(mexes)} metal spots")
    for m in mexes:                               # flatten mexes again after carving
        flatten_disc(hm, m["x"], m["z"], 40, 90)
    hm = 0.5 * (hm + sym.mirror_grid(hm))         # exact final symmetry
    hm = ndimage.gaussian_filter(hm, 0.6).astype(np.float32)
    desc = f"{ux}x{uz} {biome} {style}, 1v1 to teams. Procedurally generated (seed {seed})."
    title = f"{biome.capitalize()} {style.capitalize()} {seed}"
    return Design(hm=hm, sym=sym, starts=starts, teams=[[starts[0]], [starts[1]]], mexes=mexes, geos=geos,
                  biome=BIOMES[biome], title=title, description=desc, keep_clear=carver.mask, seed=seed,
                  values=dict(biome=biome, style=style, layout=layout), rng_state=rng.bit_generator.state)


def generate(title, size=(12, 12), seed=1, biome="temperate", style="hills", layout="diag", relief=None,
             outdir=".", config=None, version=1, log=print, preview=True, mex_per_side=None, name=None):
    """Build a procedural skirmish map. Map name = config.map_name(title, version) unless `name` is given.
    size: Spring map units (even, 4..32). Returns the info dict of build_archive()."""
    cfg = config or ForgeConfig()
    name = name or cfg.map_name(title, version)
    log(f"[{name}] {size[0]}x{size[1]} {biome}/{style}/{layout} seed={seed}")
    d = design(size, seed, biome, style, layout, relief, mex_per_side, log)
    return build_archive(name, d.hm, d.sym, d.starts, d.mexes, d.geos, d.biome, d.build_rng(), outdir,
                         cfg.describe(d.description), config=cfg, log=log, preview=preview,
                         keep_clear=d.keep_clear, extra=dict(seed=d.seed, **d.values))

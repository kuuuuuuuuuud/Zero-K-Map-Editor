"""Texture rendering: diffuse colour per texel (biome palette, slope rock, shore, paint layers, decals),
light emission for lava, splat distribution, detail normals and cached detail materials."""
import os
import zlib

import numpy as np
from scipy import ndimage

from . import SQ, TEX_PER_SQ
from .biomes import GROUND_MAT
from .config import cache_dir
from .formats import bmp_bytes, dds_bytes, png_bytes
from .materials import GENERATORS
from .noise import periodic_noise, smoothstep, value_noise

PAINT_LAYERS = ("ice", "scorch", "lava", "concrete", "molten", "path")
CRACK_RES = 2      # samples per heightmap square for the lava crack field
MAT_VERSION = 1


def build_texture_fields(hm):
    """Per-square fields the renderer interpolates: height, slope, coarse/fine occlusion, normal."""
    gz, gx = np.gradient(hm, SQ)
    sl = np.degrees(np.arctan(np.sqrt(gx * gx + gz * gz)))
    n = np.stack([-gx, np.ones_like(gx), -gz], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    ao = np.clip((hm - ndimage.gaussian_filter(hm, 14)) / 45.0, -1, 1)      # coarse hollows/domes
    cav = hm - ndimage.gaussian_filter(hm, 1.5)                               # fine edges/gullies
    # scree: loose rock gathers at the foot of cliffs (gentle ground just below steep ground)
    cliff = ndimage.gaussian_filter((sl > 38).astype(np.float32), 3.0)       # only real cliffs, not gullies
    below = np.clip((ndimage.maximum_filter(hm, 11) - hm - 25.0) / 50.0, 0, 1)
    foot = np.clip((cliff - 0.12) * 2.6, 0, 1) * (1 - smoothstep(18, 32, sl)) * below
    F = dict(sl=sl.astype(np.float32), n=n.astype(np.float32), ao=ao.astype(np.float32),
             cav=cav.astype(np.float32))
    F["stack"] = np.dstack([hm.astype(np.float32), F["sl"], F["ao"], F["cav"], F["n"],
                            foot.astype(np.float32)]).astype(np.float32)
    return F


class NoiseBank:
    def __init__(self, rng):
        self.F = periodic_noise(512, rng, 0.35)    # grain
        self.M = periodic_noise(512, rng, 1.0)     # medium patches
        self.L = periodic_noise(512, rng, 1.25)    # large areas
        self.R = periodic_noise(512, rng, 0.8)     # rock

    @staticmethod
    def sample(p, r0, r1, Wpx, div):
        P = p.shape[0]
        pad = div if div > 1 else 0          # include the border -> no seams between strips
        ri = ((np.arange(r0 - pad, r1 + pad) // div) % P)[:, None]
        ci = ((np.arange(Wpx) // div) % P)[None, :]
        out = p[ri, ci].astype(np.float32)
        if div > 1:                          # smooth interpolation instead of steps
            out = ndimage.uniform_filter(out, size=div, mode="wrap")[pad:pad + (r1 - r0)]
        return out


def bilerp(a, ys, xs):
    """Separable bilinear sampling on a regular grid (like map_coordinates order=1, mode=nearest).
    a: (H, W) or (H, W, K); ys: (R,), xs: (C,) index coordinates."""
    H, W = a.shape[:2]
    ys = np.clip(np.asarray(ys, np.float32), 0, H - 1); xs = np.clip(np.asarray(xs, np.float32), 0, W - 1)
    i0 = np.minimum(ys.astype(np.int32), H - 2); fy = ys - i0
    j0 = np.minimum(xs.astype(np.int32), W - 2); fx = xs - j0
    ext = (slice(None),) + (None,) * (a.ndim - 1)
    r = a[i0] * (1 - fy)[ext] + a[i0 + 1] * fy[ext]
    ext2 = (None, slice(None)) + (None,) * (a.ndim - 2)
    return (r[:, j0] * (1 - fx)[ext2] + r[:, j0 + 1] * fx[ext2]).astype(np.float32)


def mix(a, b, t):
    return a + (b - a) * (t[..., None] if np.ndim(t) else t)


def crack_field(n, rng, res=CRACK_RES):
    """Voronoi plates of a lava crust, in elmos: channel 0 = distance to the edge of large plates
    (~230 elmos), 1 = small plates (~80 elmos), 2 = brightness per plate (-1..1). Slightly warped."""
    from scipy.spatial import cKDTree
    m = (n - 1) * res + 1
    step = SQ / res
    zz, xx = np.mgrid[0:m, 0:m].astype(np.float32) * step
    wx = ndimage.zoom(value_noise((n, n), n / 40, rng), res, order=1)[:m, :m] * 45
    wz = ndimage.zoom(value_noise((n, n), n / 40, rng), res, order=1)[:m, :m] * 45
    P = np.stack([(xx + wx).ravel(), (zz + wz).ravel()], 1)
    W_ = (n - 1) * SQ
    out = np.zeros((m, m, 3), np.float32)
    for ch, cell in ((0, 230.0), (1, 80.0)):
        k = int(W_ / cell) + 2
        gx, gz = np.meshgrid(np.arange(-1, k), np.arange(-1, k))
        seeds = np.stack([(gx + rng.uniform(0.1, 0.9, gx.shape)) * cell,
                          (gz + rng.uniform(0.1, 0.9, gz.shape)) * cell], -1).reshape(-1, 2)
        d, i = cKDTree(seeds).query(P, k=2, workers=-1)
        out[..., ch] = ((d[:, 1] - d[:, 0]) * 0.5).reshape(m, m)
        if ch == 0:
            out[..., 2] = rng.uniform(-1, 1, len(seeds))[i[:, 0]].reshape(m, m)
    return out


def render_rgb(F, r0, r1, Wpx, biome, water_h, NB, decals, emis_out=None):
    """Diffuse texture rows r0..r1 (texels). emis_out: optional (rows, Wpx, 4) float array for lava glow."""
    rows = np.arange(r0, r1, dtype=np.float32)
    cols = np.arange(Wpx, dtype=np.float32)
    ys, xs1 = (rows + 0.5) / TEX_PER_SQ, (cols + 0.5) / TEX_PER_SQ
    xx = np.broadcast_to(xs1[None, :], (len(rows), Wpx))
    st = bilerp(F["stack"], ys, xs1)
    h, s, ao, cav, nx_, ny, nz_, foot = [st[..., k] for k in range(8)]
    nF = NB.sample(NB.F, r0, r1, Wpx, 1)
    nM = NB.sample(NB.M, r0, r1, Wpx, 4)
    nL = NB.sample(NB.L, r0, r1, Wpx, 16)
    nR = NB.sample(NB.R, r0, r1, Wpx, 2)
    C = {k: np.array(biome[k], np.float32) for k in ("bed", "shore", "low", "mid", "high", "rock", "cliff", "peak", "patch")}
    tl = np.clip((h - water_h) / 340.0, 0, 1.2)        # absolute height scale -> snow only on real mountains
    tn = tl + 0.10 * nL + 0.04 * nM
    # ground
    col = mix(np.broadcast_to(C["low"], h.shape + (3,)).copy(), C["mid"], smoothstep(0.18, 0.5, tn))
    col = mix(col, C["high"], smoothstep(0.5, 0.85, tn))
    pt = smoothstep(0.35, 1.1, 0.65 * nL + 0.35 * nM + 0.15 * nF)
    col = mix(col, C["patch"], pt * biome.get("patch_amt", 0.6))
    # second, opposite area variation (richer/darker) and a slight hue shift
    pt2 = smoothstep(0.3, 1.2, -0.7 * nL + 0.3 * nM)
    col = mix(col, col * np.array([0.82, 0.9, 0.8], np.float32), pt2 * 0.55)
    col *= (1 + 0.06 * nL[..., None] * np.array([1.0, 0.4, -0.6], np.float32))
    col *= (1 + 0.35 * biome.get("grain", 0.09) * nF + 0.05 * nM)[..., None]
    # peaks
    snow = smoothstep(biome["peak_level"] - 0.04, biome["peak_level"] + 0.04, tn + 0.03 * nF)
    snow *= 1 - smoothstep(26, 40, s + 6 * nM)                  # steep faces stay rock
    snowc = C["peak"] * (1 + 0.03 * nF + 0.05 * nM - 0.06 * np.clip(-cav / 4.0, 0, 1))[..., None]
    snowc = mix(snowc, snowc * np.array([0.86, 0.9, 1.0], np.float32), np.clip(-ao, 0, 1) * 0.8)  # blue shade in hollows
    poke = smoothstep(0.9, 1.5, nR + 0.6 * nM + 0.4 * np.clip(cav / 4.0, 0, 1)) * 0.75     # rocks poke through
    snowc = mix(snowc, C["rock"] * (1 + 0.15 * nR)[..., None], poke)
    col = mix(col, snowc, snow)
    # shore and underwater (not on void maps: below the edge is empty space)
    void = bool(biome.get("void"))
    sh = 1 - smoothstep(water_h + 4, water_h + 14 + 6 * nL, h)
    if void:
        sh = sh * 0
    shore = C["shore"] * (1 + 0.05 * nF + 0.05 * nM)[..., None]
    col = mix(col, shore, sh)
    wet = (1 - smoothstep(water_h + 0.5, water_h + 4 + 1.5 * nM, h)) * smoothstep(water_h - 2, water_h + 0.5, h)
    if void:
        wet = wet * 0
    col = mix(col, shore * 0.72, wet * 0.8)                                       # wet sand at the water line
    foam = np.exp(-((h - water_h - 0.6) / 0.9) ** 2) * (0.5 + 0.5 * smoothstep(-0.5, 1.0, nF))
    foam *= smoothstep(1.0, 4.0, s) * (1 - smoothstep(15, 30, s))                  # only where the shore has a slope
    if void:
        foam = foam * 0
    col = mix(col, np.array([235, 236, 230], np.float32), foam * 0.25)
    uw = 1 - smoothstep(water_h - 40, water_h + 0.5, h)
    depth = np.clip((water_h - h) / 60.0, 0, 1)
    bed = mix(C["bed"] * (1 + 0.08 * nM)[..., None], C["shore"] * 0.8, (1 - smoothstep(0.0, 0.35, depth)) * 0.6)
    bed = bed * (1 - 0.35 * depth)[..., None]                                     # deeper = darker
    if void:
        bed = np.broadcast_to(C["bed"], h.shape + (3,))
    col = mix(col, bed, uw)
    # rock by slope
    sn = s + 5 * nM + 2 * nF
    # scree (loose rock) at the foot of cliffs, before the rock itself
    scree = mix(np.broadcast_to(C["rock"], h.shape + (3,)).copy(), C["shore"], 0.25)
    scree *= (1 + 0.22 * nF + 0.08 * nR)[..., None]
    col = mix(col, scree, np.clip(foot * (0.75 + 0.35 * nM), 0, 0.85))
    bands = np.sin(h * 0.42 + nR * 1.1 + 0.6 * nM)                               # sediment layers along the height
    strata = 0.5 + 0.5 * bands
    rock = mix(np.broadcast_to(C["rock"], h.shape + (3,)).copy(), C["cliff"], strata * 0.5)
    rock *= (1 + 0.12 * nR + 0.04 * nF + 0.06 * (1 - smoothstep(0.0, 0.25, np.abs(bands))))[..., None]
    rim = np.clip(cav / 5.0, 0, 1)                                               # weathered light edges
    crev = np.clip(-cav / 5.0, 0, 1)                                             # dark cracks and gullies
    rock = mix(rock, rock * 1.22 + 12, rim * 0.6)
    rock = mix(rock, rock * 0.55, crev * 0.7)
    col = mix(col, rock, smoothstep(19, 28, sn))
    cl = C["cliff"] * (1 + 0.14 * nR + 0.04 * nF)[..., None]
    cl = mix(cl, cl * 1.25 + 10, rim * 0.5)
    cl = mix(cl, cl * 0.6, crev * 0.6)
    col = mix(col, cl, smoothstep(32, 44, sn) * 0.75)
    # biome extras: moss on rock (jungle, swamp), muddy puddles (swamp), steel plates (industrial)
    if biome.get("moss", 0) > 0:
        mo = smoothstep(0.1, 0.9, ny - 0.55 + 0.3 * nM + 0.2 * np.clip(-cav / 4.0, 0, 1))
        mo *= smoothstep(14, 24, sn) * (1 - smoothstep(48, 60, sn)) * biome["moss"]
        col = mix(col, C["low"] * (0.85 + 0.2 * nF)[..., None], mo)
    if biome.get("puddles", 0) > 0:
        pd = smoothstep(0.35, 0.7, 0.6 * nM + 0.4 * nL + 0.15 * nF) * (1 - smoothstep(3, 7, s))
        pd *= (1 - smoothstep(water_h + 40, water_h + 120, h)) * biome["puddles"]
        mud = C["patch"] * 0.62 * (1 + 0.08 * nF)[..., None]
        col = mix(col, mud, np.clip(pd * 1.4, 0, 1) * 0.75)
        sheen = smoothstep(0.75, 0.95, 0.6 * nM + 0.4 * nL + 0.1 * nF) * pd
        col = mix(col, mud * 0.7 + np.array([18, 22, 24], np.float32), np.clip(sheen * 1.5, 0, 0.8))
    if biome.get("plates", 0) > 0:
        zz_ = ys[:, None] * SQ
        xx_ = xx * SQ
        zone = smoothstep(0.15, 0.45, 0.7 * nL + 0.3 * nM) * (1 - smoothstep(4, 9, s)) * biome["plates"]
        zone *= smoothstep(water_h + 6, water_h + 14, h)
        P = 96.0                                                      # plate size (elmos)
        joint = np.maximum(smoothstep(P / 2 - 3.0, P / 2 - 1.2, np.abs((xx_ % P) - P / 2)),
                           smoothstep(P / 2 - 3.0, P / 2 - 1.2, np.abs((zz_ % P) - P / 2)))
        px_, pz_ = np.floor(xx_ / P), np.floor(zz_ / P)
        tone = (np.sin(px_ * 12.9898 + pz_ * 78.233) * 43758.5453) % 1.0       # brightness per plate
        bx_, bz_ = (xx_ % P), (zz_ % P)
        bolt = sum(1 - smoothstep(0.8, 1.8, np.hypot(bx_ - cx_, bz_ - cz_))
                   for cx_ in (7.0, P - 7.0) for cz_ in (7.0, P - 7.0))
        steel = np.array([122, 126, 130], np.float32) * (0.84 + 0.24 * tone + 0.05 * nF + 0.06 * nM)[..., None]
        steel = steel * (1 - 0.45 * joint + 0.25 * bolt)[..., None]
        rust = smoothstep(0.5, 1.3, nM + 0.5 * nF + 0.3 * joint) * 0.6
        steel = mix(steel, np.array([118, 72, 42], np.float32) * (1 + 0.12 * nF)[..., None], rust)
        col = mix(col, steel, zone)
    # paint layers (designed areas): glacier ice, scorch marks (flood line), lava crust, concrete, open lava
    if "paint" in F:
        pl = bilerp(F["paint"], ys, xs1)
        ice, scorch, lava, conc, molten, path = (pl[..., k] for k in range(6))
        if path.max() > 0:      # driven paths on ramps and fords: compacted, lighter ground with ruts
            pc = mix(np.broadcast_to(C["patch"], h.shape + (3,)).copy(), C["shore"], 0.45)
            pc *= (1 + 0.06 * nF + 0.08 * nM - 0.08 * np.clip(-cav / 3.0, 0, 1))[..., None]
            col = mix(col, pc, np.clip(path * (0.75 + 0.2 * nM), 0, 0.85) * (1 - smoothstep(24, 34, s)))
        if conc.max() > 0:      # concrete (dam wall): light grey, 32 elmo joint grid, light stains
            zz_ = ys[:, None] * SQ
            xx_ = xx * SQ
            joint = np.maximum(1 - smoothstep(0.0, 0.9, np.abs((xx_ % 32.0) - 16) - 15),
                               1 - smoothstep(0.0, 0.9, np.abs((zz_ % 32.0) - 16) - 15))
            cc = np.array([168, 166, 160], np.float32) * (1 + 0.05 * nF + 0.07 * nM - 0.12 * joint)[..., None]
            cc = mix(cc, cc * 0.78, np.clip(smoothstep(0.5, 1.5, nM) * 0.6, 0, 1))
            col = mix(col, cc, conc)
        if ice.max() > 0:
            icec = np.array([206, 222, 236], np.float32) * (1 + 0.05 * nF + 0.06 * nM)[..., None]
            blue = np.array([96, 132, 176], np.float32) * (1 + 0.1 * nR)[..., None]
            icec = mix(icec, blue, np.clip(smoothstep(20, 50, s + 6 * nR) + np.clip(-cav / 6.0, 0, 1) * 0.8, 0, 1))
            col = mix(col, icec, ice)
        if scorch.max() > 0:
            sc = np.array([58, 44, 38], np.float32) * (1 + 0.12 * nF + 0.1 * nM)[..., None]
            ember = (1 - smoothstep(0.0, 0.05, np.abs(nM + 0.25 * nF))) * 0.35
            sc = mix(sc, np.array([150, 70, 30], np.float32), ember)
            col = mix(col, sc, scorch * 0.85)
        if lava.max() > 0:
            cf = bilerp(F["crack"], ys * CRACK_RES, xs1 * CRACK_RES)          # distance to plate edge (elmos)
            e1, e2 = cf[..., 0], cf[..., 1]
            crust = np.array([46, 32, 27], np.float32) * (1 + 0.16 * nF + 0.10 * nR + 0.12 * cf[..., 2])[..., None]
            c1 = 1 - smoothstep(2.5, 8.0, e1 + 1.5 * nF)                        # large plates
            c2 = (1 - smoothstep(1.0, 3.5, e2 + 0.8 * nF)) * 0.65                # fine cracks
            halo = (1 - smoothstep(6.0, 28.0, e1)) * 0.28                        # warm glow beside cracks
            glow = np.clip(np.maximum(np.maximum(c1, c2), halo) * (1 - 0.45 * smoothstep(35, 60, s)), 0, 1) * lava
            hot = mix(np.broadcast_to(np.array([235, 92, 18], np.float32), h.shape + (3,)).copy(),
                      np.array([255, 190, 70], np.float32), smoothstep(0.6, 1.0, glow))
            col = mix(col, crust, lava)
            col = mix(col, hot, glow * 0.9)
            if molten.max() > 0:      # open lava (crater lake): bright, only small dark crust plates
                mg = np.clip(1 - 0.75 * smoothstep(9.0, 30.0, e2 * 2.2 + 6 * nM), 0.25, 1) * molten
                mc = mix(np.broadcast_to(np.array([200, 55, 8], np.float32), h.shape + (3,)).copy(),
                         np.array([255, 200, 80], np.float32), smoothstep(0.4, 1.0, mg + 0.15 * nF))
                col = mix(col, mc, molten)
                glow = np.maximum(glow, mg)
                hot = mix(hot, mc, molten)
            if emis_out is not None:
                emis_out[...] = np.concatenate([hot * glow[..., None] * 0.85, (glow * 0.75 * 255)[..., None]], -1)
    # shading: fine edges, hollows, light
    col *= (1 + np.clip(cav / 7.0, -0.35, 0.22))[..., None]
    col *= (1 + 0.14 * ao)[..., None]
    L = np.array(biome.get("sundir", (-0.4, 0.75, -0.5)), np.float64); L /= np.linalg.norm(L)
    lam = nx_ * L[0] + ny * L[1] + nz_ * L[2]
    col *= (0.84 + 0.22 * np.clip(lam, 0, 1))[..., None]
    # decals (mex plates, geovent cracks)
    for (dx, dz, kind) in decals:
        R = 70
        if dz + R < r0 or dz - R > r1:
            continue
        a0, a1 = int(max(r0, dz - R)), int(min(r1, dz + R))
        b0, b1 = int(max(0, dx - R)), int(min(Wpx, dx + R))
        if a1 <= a0 or b1 <= b0:
            continue
        ii, jj = np.mgrid[a0:a1, b0:b1].astype(np.float32)
        d = np.sqrt((ii + 0.5 - dz) ** 2 + (jj + 0.5 - dx) ** 2)
        ang = np.arctan2(ii + 0.5 - dz, jj + 0.5 - dx)
        sub = col[a0 - r0:a1 - r0, b0:b1]
        f = nF[a0 - r0:a1 - r0, b0:b1]; m = nM[a0 - r0:a1 - r0, b0:b1]
        if kind == "mex":
            sc_ = (1 - smoothstep(20, 46, d + 6 * m)) * 0.45
            sub[:] = mix(sub, sub * 0.55, sc_)
            disc = 1 - smoothstep(18, 23, d + 1.5 * f)
            plate = np.array([78, 82, 90], np.float32) * (1 + 0.12 * f + 0.1 * np.sin(ang * 8))[..., None]
            sub[:] = mix(sub, plate, disc * 0.9)
            ring = np.exp(-((d - 21) / 1.8) ** 2)
            sub[:] = mix(sub, np.array([175, 182, 192], np.float32), ring * 0.55)
            specks = (f > 1.5) & (d < 42) & (d > 23)
            sub[specks] = sub[specks] * 0.5 + np.array([140, 145, 155], np.float32) * 0.5
        else:
            cr = np.abs(np.sin(ang * 3.5 + m * 2.5 + d * 0.04))
            crack = (1 - smoothstep(0.0, 0.12, cr)) * (1 - smoothstep(15, 55, d + 8 * m))
            sub[:] = mix(sub, sub * 0.6, (1 - smoothstep(10, 50, d + 6 * m)) * 0.6)
            sub[:] = mix(sub, np.array([28, 22, 20], np.float32), np.clip(crack + (1 - smoothstep(6, 14, d)), 0, 1))
            glow = 1 - smoothstep(0, 7, d)
            sub[:] = mix(sub, np.array([200, 110, 40], np.float32), glow * 0.6)
    return np.clip(col, 0, 255).astype(np.uint8)


# ----------------------------------------------------------------------------- splat, detail normals
def splat_weights(hm, TF, mexes, geos, rng, res):
    """RGBA weights (rock, pebbles, ground, shore) at res x res per heightmap square."""
    nz, nx = hm.shape[0] - 1, hm.shape[1] - 1
    H, Wd = nz * res, nx * res
    ys = (np.arange(H, dtype=np.float32) + 0.5) / res; xs = (np.arange(Wd, dtype=np.float32) + 0.5) / res
    st = bilerp(TF["stack"][..., :3], ys, xs)
    h, s, ao = st[..., 0], st[..., 1], st[..., 2]
    n1 = value_noise((H, Wd), max(nx, nz) / 24, rng)
    n2 = value_noise((H, Wd), max(nx, nz) / 6, rng)
    rock = smoothstep(21, 33, s + 4 * n1)
    shore = (1 - smoothstep(4, 22 + 6 * n2, h)) * (1 - rock)
    peb = smoothstep(0.35, 0.9, 0.6 * n1 + 0.5 * n2) * 0.7 + smoothstep(9, 16, s) * 0.5
    peb += np.clip(-ao, 0, 1) * 0.4
    R = 110
    for m in list(mexes) + [dict(x=g[0], z=g[1]) for g in geos]:
        a0 = max(0, int((m["z"] - R) / SQ * res)); a1 = min(H, int((m["z"] + R) / SQ * res) + 2)
        b0 = max(0, int((m["x"] - R) / SQ * res)); b1 = min(Wd, int((m["x"] + R) / SQ * res) + 2)
        if a1 <= a0 or b1 <= b0:
            continue
        d = np.hypot(xs[None, b0:b1] * SQ - m["x"], ys[a0:a1, None] * SQ - m["z"])
        peb[a0:a1, b0:b1] += (1 - smoothstep(30, 110, d)) * 0.9
    peb = np.clip(peb, 0, 1) * (1 - rock) * (1 - shore)
    ground = np.clip(1 - rock - peb - shore, 0, 1)
    tot = rock + peb + ground + shore + 1e-6
    w = np.stack([rock, peb, ground, shore], -1) / tot[..., None]
    return np.clip(w * 255 + 0.5, 0, 255).astype(np.uint8)


def detail_normal_map(hm, TF, rng, res):
    """Tangent-space detail normals (rock relief, ground ripples) with res pixels per square."""
    nz, nx = hm.shape[0] - 1, hm.shape[1] - 1
    H, Wd = nz * res, nx * res
    out = np.empty((H, Wd, 3), np.uint8)
    pn_a = periodic_noise(1024, rng, 0.9)
    pn_b = periodic_noise(1024, rng, 0.45)
    strip = 1024
    for r0 in range(0, H, strip):
        r1 = min(H, r0 + strip + 2)
        st = bilerp(TF["stack"][..., :2], (np.arange(r0, r1, dtype=np.float32) + 0.5) / res,
                    (np.arange(Wd, dtype=np.float32) + 0.5) / res)
        h, s = st[..., 0], st[..., 1]
        ri = (np.arange(r0, r1) % 1024)[:, None]; ci = (np.arange(Wd) % 1024)[None, :]
        rockm = smoothstep(14, 30, s)
        strata = np.sin(h * 0.45 + pn_a[ri, ci] * 1.5)
        dh = rockm * (2.2 * strata + 1.4 * pn_a[ri, ci] + 0.6 * pn_b[ri, ci]) + (1 - rockm) * 0.35 * pn_b[ri, ci]
        gx = np.gradient(dh, axis=1); gy = np.gradient(dh, axis=0)
        nrm = np.stack([-gx, gy, np.ones_like(gx)], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        rows = min(strip, H - r0)
        out[r0:r0 + rows] = np.clip((nrm[:rows] * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8)
    return out


def cached_material(kind, gen):
    """Detail materials do not depend on the map: generate once and cache the PNG bytes."""
    folder = cache_dir()
    p = os.path.join(folder, f"mat_{kind}_v{MAT_VERSION}.png")
    if os.path.exists(p):
        with open(p, "rb") as f:
            return f.read()
    os.makedirs(folder, exist_ok=True)
    seed = zlib.crc32(kind.encode()) & 0xFFFF
    data = png_bytes(gen(np.random.default_rng(seed)))
    with open(p + ".tmp", "wb") as f:
        f.write(data)
    os.replace(p + ".tmp", p)
    return data


def material_files(hm, TF, biome, mexes, geos, rng, log=print):
    """Files under maps/: DNTS materials, splat distribution, detail normals."""
    nz, nx = hm.shape[0] - 1, hm.shape[1] - 1
    log("  materials (DNTS, splat, detail normals)")
    kind = GROUND_MAT.get(biome.get("name", ""), biome.get("ground", "grass"))
    files = {
        "dnts_rock.png": cached_material("rock", GENERATORS["rock"]),
        "dnts_pebbles.png": cached_material("pebbles", GENERATORS["pebbles"]),
        "dnts_ground.png": cached_material(kind, GENERATORS[kind]),
        "dnts_shore.png": cached_material("shore", GENERATORS["shore"]),
        "splat_dummy.png": png_bytes(np.full((8, 8, 3), 128, np.uint8)),
        "splat_distribution.png": png_bytes(splat_weights(hm, TF, mexes, geos, rng, 2)),
    }
    res = 4 if max(nx, nz) <= 1024 else 2
    # Recoil flips DDS vertically on load (CBitmap::Load, flipDDS), so store it upside down; for a normal
    # map this also reverses the row direction -> invert the G channel (dh/drow).
    dn = detail_normal_map(hm, TF, rng, res)[::-1].copy()
    dn[..., 1] = 255 - dn[..., 1]
    files["detail_normals.dds"] = dds_bytes(dn, "DXT1")
    return files


def detail_bmp(rng):
    n = periodic_noise(256, rng, 0.8)
    img = np.clip(127 + 22 * n, 0, 255).astype(np.uint8)
    return bmp_bytes(np.stack([img] * 3, -1))

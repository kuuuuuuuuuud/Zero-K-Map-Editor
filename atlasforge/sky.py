"""Procedural sky per biome: an equirectangular panorama (2:1) the engine turns into a sky box.

Recoil loads `atmosphere.skyBox` from maps/ and converts a 2D image into a cube map
(rts/Rendering/Env/SkyBox.cpp, EquiRectConverterFS.glsl): column u = atan2(z, x) / 2pi + 0.5,
row v = acos(y) / pi, top row = straight up. World axes: x east, y up, z south.
The horizon matches the map's fog colour, so distant terrain fades into the sky without a seam.
"""
import io
import math

import numpy as np
from PIL import Image
from scipy import ndimage

from .noise import fbm, smoothstep

SUN_PRESETS = {                     # name: (azimuth deg from east towards south, elevation deg, sun colour multiplier)
    "morning": (-20.0, 22.0, (1.0, 0.88, 0.74)),
    "noon": (90.0, 68.0, (1.0, 1.0, 1.0)),
    "afternoon": (140.0, 40.0, (1.0, 0.96, 0.88)),
    "evening": (195.0, 13.0, (1.0, 0.7, 0.48)),
}
DEFAULT_SUNDIR = (-0.4, 0.75, -0.5)


def sun_vector(azimuth_deg, elevation_deg):
    """Direction towards the sun (x east, y up, z south), normalised."""
    a, e = math.radians(azimuth_deg), math.radians(elevation_deg)
    return (math.cos(e) * math.cos(a), math.sin(e), math.cos(e) * math.sin(a))


def normalise(v):
    v = np.asarray(v, np.float64)
    return tuple(float(x) for x in v / (np.linalg.norm(v) + 1e-9))


def panorama(biome, sundir=None, seed=1, width=2048):
    """-> RGB uint8 image (width x width/2)."""
    W, H = width, width // 2
    rng = np.random.default_rng(seed + 9100)
    sx, sy, sz = normalise(sundir or biome.get("sundir", DEFAULT_SUNDIR))
    u = (np.arange(W) + 0.5) / W
    v = (np.arange(H) + 0.5) / H
    phi = (u - 0.5) * 2 * math.pi
    theta = v * math.pi
    x = np.sin(theta)[:, None] * np.cos(phi)[None, :]
    y = np.broadcast_to(np.cos(theta)[:, None], (H, W))
    z = np.sin(theta)[:, None] * np.sin(phi)[None, :]

    sky = np.array(biome["sky"], np.float64)
    fog = np.array(biome["fog"], np.float64)
    sun = np.array(biome["sun"], np.float64)
    zenith = np.clip(sky * biome.get("zenith_mul", 0.78), 0, 1)
    horizon = np.clip(0.55 * fog + 0.45 * sky, 0, 1)
    t = np.clip(y, 0, 1) ** 0.55                                     # 0 at the horizon, 1 straight up
    col = horizon[None, None] * (1 - t[..., None]) + zenith[None, None] * t[..., None]
    below = np.clip(-y, 0, 1) ** 0.6                                 # under the horizon: haze getting darker
    col = col * (1 - below[..., None]) + (fog * 0.62)[None, None] * below[..., None]

    # sun glow and disc
    cosang = np.clip(x * sx + y * sy + z * sz, -1, 1)
    ang = np.degrees(np.arccos(cosang))
    glow = 0.5 * np.exp(-ang / 18.0) + 0.25 * np.exp(-ang / 55.0) * (1 - np.clip(y, 0, 1)) * 0.8
    disc = 1 - smoothstep(1.4, 2.4, ang)
    col = col + (sun * biome.get("sun_glow", 1.0))[None, None] * glow[..., None]
    col = col * (1 - disc[..., None]) + (np.minimum(1.0, sun * 1.1) * 0.5 + 0.5)[None, None] * disc[..., None]

    # clouds on a flat layer high above the map: noise sampled through the dome
    cover = biome.get("clouds", 0.5)
    if cover > 0:
        n = 1024
        f = fbm((n, n), rng, base=6, octaves=6)
        f = (f - f.mean()) / (f.std() + 1e-6)
        detail = fbm((n, n), rng, base=24, octaves=4)
        f = f + 0.35 * (detail - detail.mean()) / (detail.std() + 1e-6)
        up = np.clip(y, 0.02, 1)
        px, pz = x / (up + 0.15), z / (up + 0.15)                 # plane projection, wraps smoothly
        ix = ((px / 3.2 + 0.5) % 1.0) * (n - 1)
        iz = ((pz / 3.2 + 0.5) % 1.0) * (n - 1)
        c = ndimage.map_coordinates(f, [iz.ravel(), ix.ravel()], order=1, mode="wrap").reshape(H, W)
        thr = 1.1 - 1.6 * cover
        dens = smoothstep(thr, thr + 0.9, c)
        lit = 0.8 + 0.2 * np.clip(cosang, 0, 1)
        ccol_top = np.array(biome.get("cloud", (1.0, 1.0, 1.0)), np.float64)
        ccol = ccol_top[None, None] * lit[..., None] * (0.8 + 0.2 * sun)[None, None]
        shade = smoothstep(0.3, 1.8, c - thr)                        # thick parts a little darker
        ccol = ccol * (1 - 0.2 * shade[..., None])
        far = 1 - smoothstep(0.03, 0.35, y)                          # distant clouds sink into the haze
        ccol = ccol * (1 - far[..., None] * 0.7) + horizon[None, None] * far[..., None] * 0.7
        a = (dens * biome.get("cloud_alpha", 0.85) * smoothstep(0.0, 0.06, y))[..., None]
        col = col * (1 - a) + ccol * a

    # space (void maps): no horizon haze, nebula clouds and stars all around, also below
    if biome.get("space"):
        n = 512
        f1 = fbm((n, n), rng, base=4, octaves=6); f2 = fbm((n, n), rng, base=7, octaves=5)
        def sph(f):                                        # noise on the sphere: three planar maps blended
            P = lambda u_, v_: ndimage.map_coordinates(f, [((u_ * 0.5 + 0.5) * (n - 1)).ravel(),
                                                           ((v_ * 0.5 + 0.5) * (n - 1)).ravel()], order=1).reshape(H, W)
            wx, wy, wz = np.abs(x) ** 4, np.abs(y) ** 4, np.abs(z) ** 4
            s_ = wx + wy + wz + 1e-9
            return (P(y, z) * wx + P(x, z) * wy + P(y, x) * wz) / s_
        neb = sph(f1); neb2 = sph(f2)
        neb = (neb - neb.mean()) / (neb.std() + 1e-6); neb2 = (neb2 - neb2.mean()) / (neb2.std() + 1e-6)
        band = np.exp(-((0.6 * x + 0.3 * y - 0.74 * z) / 0.45) ** 2)            # a galaxy band across the sky
        dens = np.clip(smoothstep(0.2, 2.0, neb + 0.8 * band) * (0.35 + 0.65 * band), 0, 1)
        c1 = np.array(biome.get("nebula", (0.42, 0.22, 0.55)), np.float64)
        c2 = np.array(biome.get("nebula2", (0.12, 0.3, 0.55)), np.float64)
        ncol = c1[None, None] * (1 - smoothstep(-1, 1, neb2)[..., None]) + c2[None, None] * smoothstep(-1, 1, neb2)[..., None]
        base = np.array(biome["sky"], np.float64)[None, None] * np.ones((H, W, 1))
        col = base + ncol * dens[..., None] * 0.85
        col = col + (sun * biome.get("sun_glow", 0.5))[None, None] * glow[..., None] * 0.6
        col = col * (1 - disc[..., None]) + np.ones(3)[None, None] * disc[..., None]
        k = int(W * H * 0.004)
        si, sj = rng.integers(0, H, k), rng.integers(0, W, k)
        b = rng.uniform(0.25, 1.0, k) ** 2
        col[si, sj] = np.maximum(col[si, sj], b[:, None] * np.array([1.0, 0.97, 0.92]))
        return (np.clip(col, 0, 1) * 255 + 0.5).astype(np.uint8)

    # stars on dark skies (moon)
    if biome.get("stars", 0) > 0:
        k = int(W * H * 0.0012 * biome["stars"])
        si, sj = rng.integers(0, H, k), rng.integers(0, W, k)
        keep = y[si, sj] > 0.04
        b = rng.uniform(0.35, 1.0, k)[keep]
        col[si[keep], sj[keep]] = np.maximum(col[si[keep], sj[keep]], b[:, None])

    return (np.clip(col, 0, 1) * 255 + 0.5).astype(np.uint8)


def sky_jpg(biome, sundir=None, seed=1, width=2048):
    buf = io.BytesIO()
    Image.fromarray(panorama(biome, sundir, seed, width)).save(buf, "JPEG", quality=88, optimize=True)
    return buf.getvalue()

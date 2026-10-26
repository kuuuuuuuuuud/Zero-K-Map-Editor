"""Procedural detail materials for Spring/Recoil "DNTS" textures (detail normal in RGB, diffuse in alpha),
as used by modern Zero-K maps (splatDetailNormalTex1..4). All materials are tileable."""
import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw


def pnoise(n, rng, falloff=1.0, lo=0.0):
    """Periodic 1/f noise, normalised to std 1."""
    w = rng.standard_normal((n, n))
    f = np.fft.fftfreq(n)
    fx, fy = np.meshgrid(f, f)
    r = np.sqrt(fx * fx + fy * fy)
    r[0, 0] = 1
    spec = np.fft.fft2(w) / r ** falloff
    if lo > 0:
        spec *= (r > lo)
    spec[0, 0] = 0
    o = np.real(np.fft.ifft2(spec))
    return ((o - o.mean()) / (o.std() + 1e-9)).astype(np.float32)


def voronoi(n, rng, cells):
    """Periodic Voronoi: F1, F2 (pixels) and cell id (KD tree with periodic boundary)."""
    from scipy.spatial import cKDTree
    pts = rng.uniform(0, n, (cells, 2))
    tree = cKDTree(pts, boxsize=n)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)
    q = np.stack([yy.ravel(), xx.ravel()], 1)
    d, i = tree.query(q, k=2, workers=-1)
    f1 = d[:, 0].reshape(n, n).astype(np.float32)
    f2 = d[:, 1].reshape(n, n).astype(np.float32)
    return f1, f2, i[:, 0].reshape(n, n).astype(np.int32)


def wrap_grad(h):
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    return gx, gy


def height_to_normal_rgb(h, strength):
    gx, gy = wrap_grad(h * strength)
    n = np.stack([-gx, gy, np.ones_like(gx)], -1)     # R = -dh/dx, G = +dh/drow (OpenGL, v up)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return np.clip((n * 0.5 + 0.5) * 255 + 0.5, 0, 255).astype(np.uint8)


def norm01(a):
    lo, hi = np.percentile(a, 1), np.percentile(a, 99)
    return np.clip((a - lo) / (hi - lo + 1e-9), 0, 1)


def dnts(height, diffuse, strength):
    """height: relief (0..1), diffuse: brightness modulation (-1..1) -> RGBA uint8."""
    rgb = height_to_normal_rgb(height, strength)
    a = np.clip(128 + 70 * diffuse, 0, 255).astype(np.uint8)
    return np.dstack([rgb, a])


def mat_rock(rng, n=1024):
    f1, f2, _ = voronoi(n, rng, 110)
    cracks = np.clip((f2 - f1) / 7.0, 0, 1)                  # 0 on cracks
    yy0, xx0 = np.mgrid[0:n, 0:n].astype(np.float32)
    wy, wx = pnoise(n, rng, 1.5) * 14, pnoise(n, rng, 1.5) * 14
    cracks = ndimage.map_coordinates(cracks, [yy0 + wy, xx0 + wx], order=1, mode="grid-wrap")
    cracks = np.maximum(cracks, np.clip(norm01(pnoise(n, rng, 1.1)) * 1.6 - 0.5, 0, 1))  # hide some cracks
    big = pnoise(n, rng, 1.4)
    mid = pnoise(n, rng, 1.0)
    fine = pnoise(n, rng, 0.5)
    yy = np.mgrid[0:n, 0:n][0].astype(np.float32)
    strata = np.sin(2 * np.pi * (yy / n * 9 + 0.15 * big)) * 0.5 + 0.5   # periodic (9 bands)
    h = 0.45 * norm01(big) + 0.25 * norm01(mid) + 0.12 * strata + 0.08 * norm01(fine)
    h = h * (0.55 + 0.45 * cracks)
    diff = 0.55 * (norm01(big) - 0.5) + 0.35 * (cracks - 1) + 0.15 * fine * 0.3 + 0.2 * (strata - 0.5)
    return dnts(h, diff, 9.0)


def mat_pebbles(rng, n=1024):
    f1a, f2a, ida = voronoi(n, rng, 260)
    f1b, f2b, idb = voronoi(n, rng, 900)
    ra = rng.uniform(0.6, 1.0, 260)[ida]
    stones_a = np.sqrt(np.clip(1 - (f1a / (np.minimum(f2a, 40) * 0.75 * ra + 1e-6)) ** 2, 0, 1))
    stones_b = np.sqrt(np.clip(1 - (f1b / (np.minimum(f2b, 22) * 0.7 + 1e-6)) ** 2, 0, 1))
    dirt = pnoise(n, rng, 0.9)
    h = 0.6 * stones_a + 0.3 * stones_b + 0.08 * norm01(dirt)
    tone = rng.uniform(-0.6, 0.6, 260)[ida]
    diff = 0.35 * tone * (stones_a > 0.05) + 0.25 * (stones_a + stones_b * 0.5 - 0.6) + 0.15 * dirt * 0.3
    return dnts(h, diff, 6.0)


def mat_grass(rng, n=1024, blades=26000):
    img = Image.new("F", (n * 3, n * 3), 0.0)
    d = ImageDraw.Draw(img)
    L = rng.uniform(6, 22, blades)
    ang = rng.normal(-np.pi / 2, 0.6, blades)
    xs = rng.uniform(0, n, blades) + n
    ys = rng.uniform(0, n, blades) + n
    val = rng.uniform(0.4, 1.0, blades)
    for x, y, l, a, v in zip(xs, ys, L, ang, val):
        d.line([(x, y), (x + l * np.cos(a), y + l * np.sin(a))], fill=float(v), width=2)
    big = np.asarray(img, np.float32)
    h = np.zeros((n, n), np.float32)                          # fold periodically
    for oy in range(3):
        for ox in range(3):
            h = np.maximum(h, big[oy * n:(oy + 1) * n, ox * n:(ox + 1) * n])
    h = ndimage.gaussian_filter(h, 0.7, mode="wrap")
    clump = pnoise(n, rng, 1.2)
    h = h * (0.75 + 0.25 * norm01(clump))
    diff = 0.6 * (h - 0.35) + 0.3 * clump * 0.3
    return dnts(h, diff, 5.0)


def mat_sand(rng, n=1024, snow=False):
    warp = pnoise(n, rng, 1.6)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    k = 14 if not snow else 5
    rip = np.sin(2 * np.pi * (yy / n * k + xx / n * 3 + 0.35 * warp)) * 0.5 + 0.5
    rip = rip ** (1.6 if not snow else 1.0)
    grain = pnoise(n, rng, 0.25)
    soft = pnoise(n, rng, 1.3)
    if snow:
        h = 0.5 * norm01(soft) + 0.15 * rip + 0.05 * norm01(grain)
        diff = 0.25 * (norm01(soft) - 0.5) + 0.12 * grain * 0.3
        return dnts(h, diff, 4.0)
    h = 0.45 * rip + 0.25 * norm01(soft) + 0.06 * norm01(grain)
    diff = 0.25 * (rip - 0.5) + 0.2 * grain * 0.3 + 0.15 * soft * 0.3
    return dnts(h, diff, 5.0)


GENERATORS = {"rock": mat_rock, "pebbles": mat_pebbles, "shore": mat_sand, "grass": mat_grass,
              "sand": mat_sand, "snow": lambda r: mat_sand(r, snow=True)}

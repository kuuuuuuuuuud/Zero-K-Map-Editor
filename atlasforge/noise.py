"""Noise and small math helpers."""
import numpy as np
from scipy import ndimage


def _bspline_weights(pos, n):
    """Dense (len(pos), n) matrix of cubic B-spline weights for sample positions inside [1, n - 3]."""
    i0 = np.floor(pos).astype(np.int64)
    t = (pos - i0).astype(np.float64)
    w = np.stack([(1 - t) ** 3 / 6, (3 * t ** 3 - 6 * t ** 2 + 4) / 6, (-3 * t ** 3 + 3 * t ** 2 + 3 * t + 1) / 6,
                  t ** 3 / 6], 1)
    m = np.zeros((len(pos), n))
    rows = np.arange(len(pos))
    for k in range(4):
        np.add.at(m, (rows, np.clip(i0 - 1 + k, 0, n - 1)), w[:, k])
    return m


def value_noise(shape, cells, rng):
    """Smooth noise (cubic interpolation) with about `cells` cells across the shorter axis.
    Same result as ndimage.map_coordinates(order=3) on the sample grid, computed separably (much faster)."""
    h, w = shape
    gh = int(cells * h / min(h, w)) + 4
    gw = int(cells * w / min(h, w)) + 4
    g = rng.standard_normal((gh, gw)).astype(np.float32)
    ys = np.linspace(1, gh - 3, h, dtype=np.float32).astype(np.float64)
    xs = np.linspace(1, gw - 3, w, dtype=np.float32).astype(np.float64)
    c = ndimage.spline_filter(g.astype(np.float64), order=3, mode="reflect")
    return (_bspline_weights(ys, gh) @ c @ _bspline_weights(xs, gw).T).astype(np.float32)


def fbm(shape, rng, base=3.0, octaves=6, gain=0.5, lac=2.0):
    """Fractal sum of value noise."""
    out = np.zeros(shape, np.float32)
    amp, f, tot = 1.0, base, 0.0
    for _ in range(octaves):
        out += amp * value_noise(shape, f, rng)
        tot += amp
        amp *= gain
        f *= lac
    return out / tot


def periodic_noise(n, rng, falloff=1.0):
    """Tileable 1/f noise via FFT (texture detail), normalised to std 1."""
    wn = rng.standard_normal((n, n))
    f = np.fft.fftfreq(n)
    fx, fy = np.meshgrid(f, f)
    r = np.sqrt(fx * fx + fy * fy)
    r[0, 0] = 1
    spec = np.fft.fft2(wn) / (r ** falloff)
    spec[0, 0] = 0
    out = np.real(np.fft.ifft2(spec))
    out = (out - out.mean()) / (out.std() + 1e-9)
    return out.astype(np.float32)


def norm01(a):
    lo, hi = np.percentile(a, 0.5), np.percentile(a, 99.5)
    return np.clip((a - lo) / (hi - lo + 1e-9), 0, 1)


def smoothstep(e0, e1, x):
    """Hermite step from e0 to e1. Requires e0 < e1 (use 1 - smoothstep(lo, hi, x) for a falling edge)."""
    t = np.clip((x - e0) / np.maximum(np.asarray(e1, np.float32) - e0, 1e-4), 0, 1)
    return t * t * (3 - 2 * t)


def ridged(shape, rng, base, octaves=5):
    n = 1 - np.abs(fbm(shape, rng, base=base, octaves=octaves, gain=0.5))
    return norm01(n)


def terrace(h, levels, sharp=0.16, rng=None, units=8):
    """Terraces with steep edges. h in [0,1]."""
    t = h * levels
    fl = np.floor(t)
    fr = t - fl
    warp = 0.0
    if rng is not None:
        warp = 0.1 * fbm(h.shape, rng, base=units * 1.2, octaves=3)
    step = smoothstep(0.5 - sharp + warp, 0.5 + sharp + warp, fr)
    return (fl + step) / levels

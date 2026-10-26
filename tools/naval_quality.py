"""Quantify underwater join curvature with matched 40-60-cell reference samples."""
import numpy as np
from scipy import ndimage

from atlasforge import SQ


def inspect_design(tid, seed=1, values=None):
    """Capture component geometry without changing template output or registry."""
    import importlib
    from unittest.mock import patch
    from atlasforge import forge
    from atlasforge.terrain import soft_relu
    module = importlib.import_module('atlasforge.templates.' + tid)
    shapes = []
    if hasattr(module, 'islands'):
        original = module.islands
        def capture(h, edge, v, fields, *args, **kwargs):
            fields = list(fields)
            shapes.extend(fields)
            return original(h, edge, v, fields, *args, **kwargs)
        target = 'islands'
    else:
        original = module.plateau
        def capture(h, sdf, top, **kwargs):
            d = sdf + kwargs.get('amp', 0) * kwargs.get('noise', 0)
            p = top - soft_relu(d, kwargs.get('round_', 24)) * np.tan(np.radians(kwargs.get('side_deg', 60)))
            shapes.append(-p / np.tan(np.radians(14)))
            return original(h, sdf, top, **kwargs)
        target = 'plateau'
    with patch.object(module, target, capture):
        design = forge.make(tid, {'erosion': 0, **(values or {})}, seed=seed, log=lambda *a: None)
    return design, shapes, joins(design, shapes, profile_fields=tid == 'coastal_front')


def curvature(h, mask, nx, nz, excluded=None):
    """Mean absolute one-cell second difference across a candidate join.

    Compare the same cross-section 40 through 60 samples to either side. Use
    submerged reference triples only, with at least six reference triples per
    join sample; a nearby dry beach cannot be used as an underwater reference.
    Exclude construction pads in both populations so their deliberately flattened
    edges do not bias either population.
    """
    zz, xx = np.nonzero(mask)
    if not len(xx):
        return dict(candidates=0, samples=0, join=None, reference=None, ratio=None)
    nx = np.broadcast_to(nx, h.shape)[zz, xx]
    nz = np.broadcast_to(nz, h.shape)[zz, xx]
    excluded = np.zeros(h.shape, bool) if excluded is None else excluded

    def sample(t):
        x, z = xx + nx * t, zz + nz * t
        inside = (x >= 1) & (z >= 1) & (x < h.shape[1] - 2) & (z < h.shape[0] - 2)
        y = ndimage.map_coordinates(h, [z, x], order=1, mode='nearest')
        blocked = ndimage.map_coordinates(excluded.astype(np.uint8), [z, x], order=0, mode='nearest')
        return y, inside & (y < -30) & ~blocked.astype(bool)

    def second(t):
        a, va = sample(t-1); b, vb = sample(t); c, vc = sample(t+1)
        return abs(a-2*b+c), va & vb & vc

    join, valid = second(0)
    reference_sum = np.zeros(len(xx), np.float64)
    reference_count = np.zeros(len(xx), np.int32)
    for sign in (-1, 1):
        for distance in range(40, 61, 4):
            v, ok = second(distance * sign)
            reference_sum += np.where(ok, v, 0)
            reference_count += ok
    valid &= reference_count >= 6
    if not valid.any():
        return dict(candidates=len(xx), samples=0, join=None, reference=None, ratio=None)
    a = float(join[valid].mean())
    b = float((reference_sum[valid] / reference_count[valid]).mean())
    peak = np.flatnonzero(valid)[np.argmax(join[valid])]
    return dict(candidates=len(xx), samples=int(valid.sum()), join=a, reference=b,
                ratio=a / max(b, 1e-8), peak_cell=[int(xx[peak]), int(zz[peak])])


def joins(design, shapes=(), profile_fields=False):
    """Measure symmetry axis and nearest-shore boundaries before geographic smoothing."""
    h = design.hm
    zz, xx = np.mgrid[:h.shape[0], :h.shape[1]].astype(np.float32)
    excluded = np.zeros(h.shape, bool)
    for m in design.mexes:
        excluded |= np.hypot(xx * SQ - m['x'], zz * SQ - m['z']) < 120
    for x, z in design.geos:
        excluded |= np.hypot(xx * SQ - x, zz * SQ - z) < 130
    for x, z in design.starts:
        excluded |= np.hypot(xx * SQ - x, zz * SQ - z) < 700
    seam = (abs(xx - (h.shape[1]-1)/2) <= 2) & (h < -30)
    result = {'seam': curvature(h, seam, 1, 0, excluded)}
    if len(shapes) >= 2:
        # Use the unsmoothed component geometry to locate joins independently of
        # the final heightmap: a bad result cannot hide its own contact line.
        first = np.full(h.shape, np.inf, np.float32)
        second = first.copy()
        g1x = np.zeros(h.shape, np.float32); g1z = g1x.copy()
        g2x = g1x.copy(); g2z = g1x.copy()
        for shape in shapes:
            for s in (shape,) if np.array_equal(shape, shape[:, ::-1]) else (shape, shape[:, ::-1]):
                dz, dx = np.gradient(s)
                near = s < first
                runner = ~near & (s < second)
                second = np.where(near, first, np.minimum(second, s))
                g2x = np.where(near, g1x, np.where(runner, dx, g2x))
                g2z = np.where(near, g1z, np.where(runner, dz, g2z))
                first = np.minimum(first, s)
                g1x = np.where(near, dx, g1x); g1z = np.where(near, dz, g1z)
        nx, nz = g1x-g2x, g1z-g2z
        norm = np.hypot(nx, nz)
        nx /= np.maximum(norm, 1e-6); nz /= np.maximum(norm, 1e-6)
        # Ignore geometric bisectors where both shore profiles are already below
        # the original sea floor: those are not flank collisions and would dilute
        # the measurement with large, naturally smooth stretches of open ocean.
        depth = design.values['depth']
        angle = 14 if profile_fields else design.values['beach_slope']
        limit = (depth + (48 if profile_fields else 148)) / np.tan(np.radians(angle))
        contact = (second-first < 32) & (first > 0) & (first < limit) & (norm > 0.1) & (h < -30)
        result['flank_contacts'] = curvature(h, contact, nx, nz, excluded)
    return result

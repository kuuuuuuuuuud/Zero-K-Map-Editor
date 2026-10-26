"""Procedural twin-plateau map (Phase 3.7): AI texture only.

The heightmap is drawn by hand in the top-left quadrant and made exactly E-W
and N-S symmetric with :func:`atlasforge.ai.postprocess.mirror_quadrant`.  Two
flat fortress plateaus sit on the short (west/east) edges and drop down a ramp
into a shared central lowland with four low corner mounds around an open centre
crossing, so tanks can always travel west<->east.

This module owns the terrain and the symmetric resource layout.  The texture is
supplied separately (an AI image or a solid biome fallback) by the ``ai plateau``
pipeline; the procedural renderer is bypassed.
"""

import numpy as np

from ..ai.postprocess import mirror_quadrant
from ..symmetry import mirror_pairs

PLATEAU_H = 260.0     # fortress plateau height (elmos)
LOWLAND_H = 90.0      # central lowland height (elmos)
MOUND_H = 145.0       # corner-mound peak (elmos)

PLATEAU_END = 2304.0  # west plateau -> ramp boundary (elmos, x axis)
RAMP_END = 2816.0     # ramp -> lowland boundary (elmos, x axis)

# west-side metal spots: 1 centre-line opening spot + 3 N-S pairs, 7 per side.
_WEST_MEXES = (
    (1300.0, None, 2.5),   # centre opening spot (z = H/2 at call time)
    (1300.0, 780.0, 2.0),  # base pair
    (2000.0, 900.0, 2.0),  # mid-plateau pair
    (3300.0, 700.0, 2.0),  # field pair
)

# west-side geovents: 2 N-S pairs in the central lowland, 4 per side.
_WEST_GEOS = (
    (3050.0, 900.0),
    (3850.0, 800.0),
)


def _quadrant(ux, uz, seed):
    """Build the top-left quadrant heightmap: rows 0..nz//2, cols 0..nx//2."""
    nx, nz = ux * 64, uz * 64
    jj, ii = np.mgrid[0:nz // 2 + 1, 0:nx // 2 + 1].astype(np.float32)
    x = jj * 8.0
    z = ii * 8.0
    hm = np.full_like(x, LOWLAND_H)

    # 1. west fortress plateau.
    hm[x <= PLATEAU_END] = PLATEAU_H

    # 2. west ramp: plateau -> lowland.
    ramp = (x > PLATEAU_END) & (x < RAMP_END)
    t = (x - PLATEAU_END) / (RAMP_END - PLATEAU_END)
    hm[ramp] = PLATEAU_H + (LOWLAND_H - PLATEAU_H) * t[ramp]

    # 3/4. central lowland corner mound (peaks off the z centre line so the
    # centre crossing stays open after the E-W and N-S mirrors).
    mound_cx = 3584.0
    mound_cz = uz * 128.0                       # z centre of the top half (elmos)
    d = np.hypot((x - mound_cx) / 320.0, (z - mound_cz) / 300.0)
    hm += (MOUND_H - LOWLAND_H) * np.exp(-(d * d)).astype(np.float32)

    # 5. gentle deterministic detail (symmetric because only the quadrant is drawn).
    from ..noise import fbm
    rng = np.random.default_rng(seed)
    n = fbm(hm.shape, rng, base=24.0, octaves=4).astype(np.float32)
    n = (n - n.mean()) / (n.std() + 1e-6)
    hm += np.where(x <= PLATEAU_END, 4.0, 8.0) * n

    return hm.astype(np.float32)


def plateau_heightmap(ux, uz, seed=1, log=print):
    """Return a float32 elmos heightmap (nz+1, nx+1) for a ``ux x uz`` plateau map.

    The map is exactly E-W and N-S symmetric (``mirror_quadrant``, top-left
    quadrant wins).  ``ux`` and ``uz`` must be even and in 4..32.
    """
    ux, uz = int(ux), int(uz)
    if ux % 2 or uz % 2:
        raise ValueError(f"map size must be even, got {ux}x{uz} (e.g. use 16x4)")
    if not (4 <= ux <= 32 and 4 <= uz <= 32):
        raise ValueError("size: even values between 4 and 32")

    nx, nz = ux * 64, uz * 64
    hm = np.zeros((nz + 1, nx + 1), np.float32)
    hm[:nz // 2 + 1, :nx // 2 + 1] = _quadrant(ux, uz, seed)
    hm, _ = mirror_quadrant(hm, "ew_ns")
    log(f"  plateau heightmap: {ux}x{uz} units, {hm.shape[1]}x{hm.shape[0]} squares, "
        f"min {float(hm.min()):.1f} max {float(hm.max()):.1f} elmo")
    return hm


def plateau_mexes(sym):
    """7 metal spots per side (3 opening + 4 field), mirrored E-W and N-S."""
    H = sym.H
    west = [
        (x, H / 2.0 if z is None else float(z), metal)
        for x, z, metal in _WEST_MEXES
    ]
    west += [(x, H - z, metal) for x, z, metal in _WEST_MEXES if z is not None]
    return mirror_pairs(west, sym)


def plateau_geos(sym):
    """4 geovents per side in the central lowland (N-S symmetric)."""
    H = sym.H
    west = []
    for x, z in _WEST_GEOS:
        west.append((float(x), float(z)))
        west.append((float(x), H - float(z)))
    out = []
    for x, z in west:
        out.append((float(x), float(z)))
        mx, mz = sym.mirror(x, z)
        out.append((float(mx), float(mz)))
    return out


if __name__ == "__main__":
    hm = plateau_heightmap(16, 4, seed=1)
    assert np.array_equal(hm, hm[:, ::-1]), "E-W symmetry broken"
    assert np.array_equal(hm, hm[::-1, :]), "N-S symmetry broken"
    from ..symmetry import Symmetry
    from .. import SQ
    sym = Symmetry("ew", 16 * 64 * SQ, 4 * 64 * SQ)
    mexes = plateau_mexes(sym)
    geos = plateau_geos(sym)
    assert len(mexes) == 14, f"expected 14 mexes, got {len(mexes)}"
    assert len(geos) == 8, f"expected 8 geos, got {len(geos)}"
    print("custom_plateau self-test passed (14 mexes, 8 geos, symmetric)")

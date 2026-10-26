"""Two-team map symmetry."""
import math
import numpy as np

from .noise import smoothstep


class Symmetry:
    """layout: 'diag' (NW vs SE, 180 degree rotation), 'ns' or 'ew' (mirror)."""

    def __init__(self, layout, W, H):
        self.layout, self.W, self.H = layout, W, H   # W, H in elmos

    def mirror(self, x, z):
        if self.layout == "ew":
            return self.W - x, z
        if self.layout == "ns":
            return x, self.H - z
        return self.W - x, self.H - z

    def side(self, x, z):
        """Signed distance to the dividing line (< 0 = team 0)."""
        cx, cz = self.W / 2, self.H / 2
        if self.layout == "ew":
            return x - cx
        if self.layout == "ns":
            return z - cz
        return ((x - cx) * self.H / self.W + (z - cz)) / math.sqrt(2)

    def mirror_grid(self, a):
        if self.layout == "ew":
            return a[:, ::-1]
        if self.layout == "ns":
            return a[::-1, :]
        return a[::-1, ::-1]

    def symmetrize(self, a, band):
        """Blend a grid with its mirror image across the dividing line (soft band in elmos)."""
        h, w = a.shape
        zz, xx = np.meshgrid(np.linspace(0, self.H, h), np.linspace(0, self.W, w), indexing="ij")
        s = self.side(xx, zz)
        wgt = smoothstep(-band, band, s)            # w(mirror p) = 1 - w(p)
        from scipy import ndimage                   # coarse shapes averaged, fine detail keeps its strength
        low = ndimage.gaussian_filter(np.asarray(a, np.float64), 10.0)
        high = a - low
        k = np.sqrt((1 - wgt) ** 2 + wgt ** 2)
        return (1 - wgt) * low + wgt * self.mirror_grid(low) + ((1 - wgt) * high + wgt * self.mirror_grid(high)) / k

    def starts(self):
        W, H = self.W, self.H
        if self.layout == "ew":
            return [(0.11 * W, 0.5 * H), (0.89 * W, 0.5 * H)]
        if self.layout == "ns":
            return [(0.5 * W, 0.11 * H), (0.5 * W, 0.89 * H)]
        return [(0.14 * W, 0.14 * H), (0.86 * W, 0.86 * H)]


def mirror_point(h):
    """Make a square heightmap exactly 180-degree symmetric: lower half = rotated upper half."""
    n = h.shape[0]
    c = n // 2
    h[c + 1:, :] = h[:c][::-1, ::-1][: n - c - 1]
    h[c, c + 1:] = h[c, :c][::-1][: n - c - 1]
    return h


def mirror_east_west(h):
    """Make a heightmap exactly mirror symmetric across the vertical centre line (west half wins)."""
    n = h.shape[1]
    half = n // 2
    h[:, half + 1:] = h[:, :half][:, ::-1][:, : n - half - 1]
    return h


def mirror_pairs(points, sym):
    """Mex list [(x, z, metal)] for team 0 -> both sides via symmetry."""
    out = []
    for x, z, v in points:
        out.append(dict(x=float(x), z=float(z), metal=v, side=0))
        mx, mz = sym.mirror(x, z)
        out.append(dict(x=float(mx), z=float(mz), metal=v, side=1))
    return out


def _mirror_image(a, mode):
    return {"ew": a[:, ::-1], "ns": a[::-1, :], "point": a[::-1, ::-1]}[mode]


def seam_blend(a, mode, band=56, split_sigma=10.0):
    """Make a noise field symmetric without a seam.

    A hard mirror copy leaves a crease along the dividing line: the terrain on both sides runs into the
    line at different angles and the noise pattern flips. This blends the field with its mirror image in
    a band around the line (band in grid cells on each side): coarse shapes are averaged, fine detail is
    blended with variance compensation so the band does not turn flat. The result is exactly symmetric
    (the team-0 side keeps its own noise outside the band, the other side gets the mirror image).

    mode: "ew" (mirror across the vertical centre line), "ns" (horizontal line), "point" (180 degree
    rotation, seam along the centre row, matching mirror_point), "d4" (both lines)."""
    if mode == "d4":
        return seam_blend(seam_blend(a, "ew", band, split_sigma), "ns", band, split_sigma)
    a = np.asarray(a, np.float64)
    from scipy import ndimage
    nz, nx = a.shape
    if mode == "ew":
        d = (np.arange(nx) - (nx - 1) / 2.0)[None, :]
    else:
        d = (np.arange(nz) - (nz - 1) / 2.0)[:, None]
    w = smoothstep(-band, band, d)                  # weight of the mirror image; w(mirror) = 1 - w
    low = ndimage.gaussian_filter(a, split_sigma)
    high = a - low
    lowm, highm = _mirror_image(low, mode), _mirror_image(high, mode)
    k = np.sqrt((1 - w) ** 2 + w ** 2)               # keeps the strength of the fine detail
    return (1 - w) * low + w * lowm + ((1 - w) * high + w * highm) / k


# ----------------------------------------------------------------------------- free-for-all (rotation)
PLAYER_COLORS = [(60, 255, 60), (255, 70, 70), (90, 160, 255), (255, 220, 60), (200, 110, 255),
                 (60, 230, 230), (255, 150, 40), (240, 240, 240)]


class RotSymmetry:
    """N-fold rotation about the map centre, for free-for-all maps with N players.

    Player k owns the sector centred on angle a0 + k * 360/N degrees (angles in the x/z plane, 0 = east,
    90 = south because z grows downwards). Every player gets the same terrain, metal and features, rotated.
    Works on square maps; the corners outside the inscribed circle are not symmetric, so templates fill them
    with ground nobody can use (e.g. a mountain rim)."""

    def __init__(self, n, W, H=None, a0=-90.0):
        self.n, self.W, self.H = int(n), float(W), float(H if H is not None else W)
        self.a0 = math.radians(a0)
        self.layout = f"rot{self.n}"
        self.cx, self.cz = self.W / 2, self.H / 2

    # points
    def rotate(self, x, z, k):
        a = 2 * math.pi * k / self.n
        dx, dz = x - self.cx, z - self.cz
        return (self.cx + dx * math.cos(a) - dz * math.sin(a), self.cz + dx * math.sin(a) + dz * math.cos(a))

    def orbit(self, x, z):
        return [self.rotate(x, z, k) for k in range(self.n)]

    def ops(self):
        return [lambda x, z, k=k: self.rotate(x, z, k) for k in range(self.n)]

    def angle(self, k):
        """Centre angle (radians) of player k's sector."""
        return self.a0 + 2 * math.pi * k / self.n

    def polar(self, r, a_deg, k=0):
        """Point at radius r and angle a_deg (degrees, relative to the centre line of sector k)."""
        a = self.angle(k) + math.radians(a_deg)
        return (self.cx + r * math.cos(a), self.cz + r * math.sin(a))

    def sector(self, x, z):
        """Index of the player sector a point lies in."""
        a = math.atan2(z - self.cz, x - self.cx) - self.a0 + math.pi / self.n
        return int(math.floor(a / (2 * math.pi / self.n))) % self.n

    def side(self, x, z):
        """< 0 inside player 0's sector (the one that is copied to everybody)."""
        return -1.0 if self.sector(x, z) == 0 else 1.0

    def mirror(self, x, z):
        """The same spot in the next player's sector (for code written for two sides)."""
        return self.rotate(x, z, 1)

    # grids
    def _coords(self, shape, k):
        """Sample coordinates (rows, cols) of the grid rotated by k sectors."""
        nz, nx = shape
        sx, sz = (nx - 1) / self.W, (nz - 1) / self.H
        t = -2 * math.pi * k / self.n
        x = (np.arange(nx, dtype=np.float32) / sx - self.cx)[None, :]
        z = (np.arange(nz, dtype=np.float32) / sz - self.cz)[:, None]
        X = self.cx + x * math.cos(t) - z * math.sin(t)
        Z = self.cz + x * math.sin(t) + z * math.cos(t)
        return np.stack([Z * sz, X * sx]).astype(np.float32)

    def rotate_grid(self, a, k, order=1):
        """Grid rotated by k sectors: out(p) = a(rotation^-k p)."""
        from scipy import ndimage
        return ndimage.map_coordinates(np.asarray(a, np.float32), self._coords(a.shape, k), order=order,
                                       mode="nearest", prefilter=False)

    def mirror_grid(self, a):
        """Rotation-averaged grid (used where two-side code averages a grid with its mirror image)."""
        return self.symmetric(a)

    def symmetric(self, a, keep_detail=False, corr=12.0):
        """Average of all N rotations: exactly fair for every player.
        keep_detail: noise fields keep their strength (averaging N independent copies would flatten them);
        corr = rough correlation length in cells (near the centre the copies overlap, no boost there)."""
        return self.symmetric_many([a], keep_detail, corr)[0]

    def symmetric_many(self, fields, keep_detail=False, corr=12.0):
        """symmetric() for several grids of the same shape (the rotation is computed once per sector)."""
        from scipy import ndimage
        fields = [np.asarray(f, np.float32) for f in fields]
        sums = [f.astype(np.float64) for f in fields]
        for k in range(1, self.n):
            c = self._coords(fields[0].shape, k)
            for i, f in enumerate(fields):
                sums[i] += ndimage.map_coordinates(f, c, order=1, mode="nearest", prefilter=False)
        out = [s_ / self.n for s_ in sums]
        if keep_detail:
            nz, nx = fields[0].shape
            zz, xx = np.ogrid[0:nz, 0:nx]
            r = np.hypot(xx - (nx - 1) / 2, zz - (nz - 1) / 2)
            boost = 1 + (math.sqrt(self.n) - 1) * smoothstep(0, corr * 2, r)
            out = [o.mean() + (o - o.mean()) * boost for o in out]
        return out

    def starts(self, radius):
        return [self.polar(radius, 0, k) for k in range(self.n)]


def rot_fields(sym, *fields):
    """Noise fields made rotationally symmetric (RotSymmetry) without losing their strength."""
    out = tuple(f.astype(np.float32) for f in sym.symmetric_many(fields, keep_detail=True))
    return out if len(out) > 1 else out[0]


def rotate_points(points, sym):
    """Mex list [(x, z, metal)] for player 0 -> every player (side = player index)."""
    out = []
    for x, z, v in points:
        for k in range(sym.n):
            rx, rz = sym.rotate(x, z, k)
            out.append(dict(x=float(rx), z=float(rz), metal=v, side=k))
    return out


# --------------------------------------------------------------------------- editor orbits


def orbit(sym, x, z):
    """Unified orbit of a point for Symmetry or RotSymmetry.

    Index 0 is always the original point; coordinates are floats."""
    if isinstance(sym, RotSymmetry):
        return [(float(px), float(pz)) for px, pz in sym.orbit(x, z)]
    mx, mz = sym.mirror(x, z)
    return [(float(x), float(z)), (float(mx), float(mz))]


def match_orbit(sym, ref, other, tol=24.0):
    """Snap the orbit of a user-edited point onto existing objects.

    ref=(x,z); other=list[(x,z)]. For each point of orbit(ref) in orbit order returns the index of
    the closest object within tol elmos (euclidean), else None; an object is assigned to at most one
    orbit point (greedy by distance, deterministic on ties)."""
    pts = orbit(sym, ref[0], ref[1])
    cands = []
    for pi, (px, pz) in enumerate(pts):
        for oi, (ox, oz) in enumerate(other):
            d = math.hypot(px - ox, pz - oz)
            if d <= tol:
                cands.append((d, pi, oi))
    cands.sort()
    out = [None] * len(pts)
    used = set()
    for _, pi, oi in cands:
        if out[pi] is None and oi not in used:
            out[pi] = oi
            used.add(oi)
    return out


def orbit_degenerate(sym, x, z, min_dist=8.0):
    """True when two points of the orbit are closer than min_dist (center / mirror line)."""
    pts = orbit(sym, x, z)
    for i in range(len(pts)):
        xi, zi = pts[i]
        for j in range(i + 1, len(pts)):
            if math.hypot(xi - pts[j][0], zi - pts[j][1]) < min_dist:
                return True
    return False

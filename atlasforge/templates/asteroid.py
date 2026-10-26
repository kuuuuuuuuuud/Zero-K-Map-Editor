"""Asteroid: a cratered rock floating in space (in the style of the Zero-K map Apophis).

A single round landmass with an irregular edge that drops into the void, a high ring around a lower
central basin, craters everywhere, rough flanks near the edge, low gravity and a starry sky.
Every player gets an identical sector (rotation about the centre), 2 to 4 players.
"""
import math

import numpy as np

from .. import SQ
from ..biomes import BIOMES
from ..checks import connected, unit_masks
from ..design import Design
from ..noise import fbm, ridged, smoothstep
from ..symmetry import PLAYER_COLORS, RotSymmetry, rot_fields, rotate_points
from ..terrain import grid, plateau
from .base import Param, Template
from .common import biome_param, ffa_boxes, flatten_all, size_param

H0 = 260.0              # height of the basin floor (elmos above the void)
VOID = -400.0           # height of the void around the asteroid


class Asteroid(Template):
    id = "asteroid"
    title = "Asteroid"
    modes = ("1v1", "team", "ffa")
    tags = ("land",)
    players = "2 to 4 players"
    description = ("A cratered asteroid floating in space: a high ring of rock around a lower central basin, "
                   "rough flanks and a steep edge that drops into the void - units and buildings down there are "
                   "destroyed. Low gravity, a starry sky. Every player gets an identical sector.")
    infos = {
        "players": "Number of start positions. Each one gets an identical sector of the asteroid, rotated "
                   "around the centre. 2 = one against one (or two teams); 3 or 4 = free-for-all, or teams "
                   "sharing the boxes. More players need a bigger asteroid (16x16 for 2-3, 20x20 for 4).",
        "centre": "The middle of the asteroid. basin: a lower crater basin inside the high ring, like the "
                  "map Apophis - whoever holds the ring looks down into it. mesa: a raised plateau in the "
                  "middle with gentle ramps, high ground for whoever takes it. flat: no ring, an even surface.",
        "relief": "Height of the ring (and the mesa) above the basin floor, in elmos. Higher relief means "
                  "longer climbs, more cover behind the ring and better views from it. The ramps stay gentle "
                  "enough for tanks.",
        "craters": "How many impact craters cover the surface. Craters are bowls with a raised rim: they "
                   "give cover and break up long firing lines, but their steep inner walls slow vehicles. "
                   "0 = smooth rock, 2 = heavily cratered.",
        "roughness": "How broken the flanks near the edge are: rough ridges and boulders where the "
                     "asteroid curves away. Rough flanks are hard to drive through and make the outer ring a "
                     "place for bots and spiders. 0 = smooth.",
        "edge": "How irregular the outline of the asteroid is. 0 = almost a circle; higher values give bays "
                "and headlands along the edge. The shape is the same for every player.",
        "gravity": "Gravity of the map (Zero-K's normal value is 120). Low gravity lets jumping units and "
                   "ballistic weapons fly further and makes wrecks and debris float - the asteroid feel. "
                   "Very low values change how artillery and bombers play.",
    }
    params = (
        size_param((12, 14, 16, 18, 20, 22), 16, adv_smallest=10),
        biome_param("asteroid"),
        Param("players", "Players", "int", 2, min=2, max=4, step=1, adv_max=6,
              help="Start positions, each with an identical sector"),
        Param("centre", "Centre", "choice", "basin", choices=("basin", "mesa", "flat"),
              help="basin: low crater inside a high ring; mesa: raised plateau; flat: even surface"),
        Param("relief", "Relief", "int", 360, min=200, max=520, step=20, adv_min=0, adv_max=1200,
              help="Height of the ring above the basin, in elmos"),
        Param("craters", "Craters", "float", 1.0, min=0.0, max=2.0, step=0.1, adv_max=4.0,
              help="Number of impact craters"),
        Param("roughness", "Rough flanks", "float", 0.7, min=0.0, max=1.5, step=0.1, adv_max=3.0,
              help="Broken ground near the edge"),
        Param("edge", "Irregular edge", "float", 0.6, min=0.0, max=1.2, step=0.1, adv_max=2.0,
              help="0 = round, higher = bays and headlands"),
        Param("gravity", "Gravity", "int", 80, min=50, max=120, step=5, adv_min=20, adv_max=200,
              help="Zero-K normal: 120"),
    )

    def make(self, v, seed, log=print):
        N = int(v["players"])
        n = v["size"] * 64 + 1
        W = (n - 1) * SQ
        C = W / 2
        sym = RotSymmetry(N, W)
        rng = np.random.default_rng(seed)
        xx, zz = grid(n)
        r = np.hypot(xx - C, zz - C)
        ang = np.arctan2(zz - C, xx - C)
        rel = ang - sym.a0

        # outline: harmonics that repeat N times around the asteroid (identical for every player)
        R0 = 0.425 * W
        wob = np.zeros_like(r)
        for k, amp in ((1, 0.06), (2, 0.035), (3, 0.02), (5, 0.012)):
            wob += amp * np.cos(k * N * rel + rng.uniform(0, 2 * math.pi))
        low = fbm((n, n), rng, base=5, octaves=6); low = (low - low.mean()) / (low.std() + 1e-6)
        rough = ridged((n, n), rng, base=9) ** 2.2
        en = fbm((n, n), rng, base=20, octaves=4)
        low, rough, en = rot_fields(sym, low, rough, en)
        en = en / (np.abs(en).max() + 1e-6)
        r_edge = R0 * (1 + v["edge"] * wob)

        # surface: basin, ring and mesa as smooth functions of the radius
        Hr = float(v["relief"])
        Rb = 0.29 * W                                              # start points on the ring
        # ramps wide enough for tanks: a smoothstep is 1.5x steeper than its average, keep it below ~22 degrees
        ramp = max(0.13 * W, 3.8 * Hr)
        ring = smoothstep(0.24 * W - ramp, 0.24 * W, r)
        if v["centre"] == "basin":
            top = H0 + Hr * ring
        elif v["centre"] == "mesa":
            top = H0 + Hr * ring + 0.85 * Hr * (1 - smoothstep(0.07 * W, 0.07 * W + 0.9 * ramp, r))
        else:
            top = H0 + 0.5 * Hr + 0 * r
        top = top + 18 * low
        starts = sym.starts(Rb)
        near = np.min([np.hypot(xx - x, zz - z) for x, z in starts], axis=0)
        flank = smoothstep(r_edge - 0.14 * W, r_edge - 0.03 * W, r) * smoothstep(650, 1300, near)
        top = top + v["roughness"] * 110 * rough * flank
        h = np.full(r.shape, VOID, np.float32)
        plateau(h, r - r_edge, top, side_deg=58, noise=en, amp=70, round_=160, toe=12)

        # resources for player 0 (fractions of the half sector, + = towards player 1)
        def pol(rr, frac):
            return sym.polar(rr, frac * 180.0 / N, 0)
        sx, sz = starts[0]
        a = sym.angle(0)
        ux, uz, tx, tz = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
        west = [(sx - 240 * ux + 230 * tx, sz - 240 * uz + 230 * tz, 2.0),
                (sx - 240 * ux - 230 * tx, sz - 240 * uz - 230 * tz, 2.0),
                (sx + 260 * ux, sz + 260 * uz, 2.0)]
        exp = [(pol(Rb, 0.6), 2.2), (pol(Rb, -0.6), 2.2),                   # along the ring
               (pol(0.37 * W, 0.3), 2.2), (pol(0.37 * W, -0.3), 2.2),       # outer flank
               (pol(0.2 * W, 0.0), 2.5),                                     # ring edge above the basin
               (pol(0.13 * W, 0.45), 2.8), (pol(0.13 * W, -0.45), 2.8)]     # in the basin
        if v["size"] >= 18:
            exp += [(pol(0.25 * W, 0.35), 2.4), (pol(0.25 * W, -0.35), 2.4)]
        for (x, z), val in exp:
            if all(math.hypot(x - px, z - pz) > 300 for px, pz, _ in west):
                west.append((x, z, val))
        rc = max(0.045 * W, 330 * N / (2 * math.pi))
        west.append((*pol(rc, 0.0), 3.2))
        # craters, placed in player 0's sector and copied to everybody
        craters = []
        count = int(round(v["craters"] * 16 * (W / 8192.0) ** 2 / N * 2))
        tries = 0
        while len(craters) < count and tries < count * 60:
            tries += 1
            R = float(np.exp(rng.uniform(math.log(70), math.log(430 * W / 8192.0))))
            cr = 0.4 * W * math.sqrt(rng.uniform(0.02, 1.0))                # even over the area
            ca = rng.uniform(-180.0 / N, 180.0 / N)
            cx, cz = sym.polar(cr, ca, 0)
            if math.hypot(cx - starts[0][0], cz - starts[0][1]) < 650 + R:     # keep the bases clear
                continue
            if cr + R > R0 * (1 - 0.1 * v["edge"]) - 120:
                continue
            orbit = sym.orbit(cx, cz)
            if N > 1 and math.hypot(orbit[1][0] - cx, orbit[1][1] - cz) < 2.2 * R:  # would overlap its copy
                continue
            if any(math.hypot(cx - x, cz - z) < 0.8 * (R + q) for x, z, q in craters):
                continue
            if any(math.hypot(px - ox, pz - oz) < R * 1.4 + 160
                   for px, pz, _ in west for ox, oz in sym.orbit(cx, cz)):          # metal spots stay clear
                continue
            craters.append((cx, cz, R))
        for cx, cz, R in craters:
            depth = 0.2 * R
            for ox, oz in sym.orbit(cx, cz):
                _crater(h, ox, oz, R, depth)

        mexes = rotate_points(west, sym)
        for m in mexes:
            bx, bz = sym.rotate(sx, sz, m["side"])
            if math.hypot(m["x"] - bx, m["z"] - bz) < 600:
                m["fixed"] = True
        geos = [sym.rotate(*pol(0.24 * W, 0.62), k) for k in range(N)]
        flatten_all(h, starts, mexes, geos, start_r=(330, 650))
        h = h.astype(np.float32)

        void = h < 0
        edge_band = r > r_edge - 160
        tanks = unit_masks(h)["tanks"] & ~void
        reach = all(connected(tanks, starts[0], s) for s in starts[1:])
        centre_ok = connected(tanks, starts[0], (C, C))
        notes = [f"Craters: {len(craters) * N}", f"Tanks reach the centre: {'yes' if centre_ok else 'NO'}"]
        biome = dict(BIOMES[v["biome"]])
        biome["void"] = True                       # space below the edge on every biome
        biome["gravity"] = int(v["gravity"])
        biome["tidal"] = 0
        biome["water_damage"] = 2000               # anything that goes down into the void is destroyed
        cols = [PLAYER_COLORS[k % len(PLAYER_COLORS)] for k in range(N)]
        desc = (f"Asteroid: a cratered rock in space with a {v['centre']} centre, {N} identical sectors, "
                f"gravity {int(v['gravity'])}.")
        return Design(hm=h, sym=sym, starts=starts, teams=[[s] for s in starts], mexes=mexes, geos=geos,
                      biome=biome, title="Asteroid", description=desc,
                      startboxes=ffa_boxes(sym, starts, Rb - 650, min(Rb + 650, 0.4 * W)),
                      blocked=void, keep_clear=void | edge_band, tree_block=void | edge_band,
                      notes=notes, notes_ok=reach and centre_ok, start_colors=cols,
                      side_labels=("your base", "every other base"))


def _crater(h, cx, cz, R, depth):
    """Bowl with a raised rim, added to the ground (not to the void)."""
    ro = R * 1.7
    i0, i1 = max(0, int((cz - ro) / SQ)), min(h.shape[0], int((cz + ro) / SQ) + 2)
    j0, j1 = max(0, int((cx - ro) / SQ)), min(h.shape[1], int((cx + ro) / SQ) + 2)
    if i1 <= i0 or j1 <= j0:
        return
    ii, jj = np.mgrid[i0:i1, j0:j1]
    d = np.hypot(jj * SQ - cx, ii * SQ - cz) / R
    bowl = -depth * np.clip(1 - d ** 2, 0, 1) ** 1.2
    rim = 0.32 * depth * np.exp(-((d - 1.0) / 0.28) ** 2)
    sub = h[i0:i1, j0:j1]
    land = sub > 0
    sub[land] = sub[land] + (bowl + rim)[land]

"""FFA Ring: free-for-all for 3 to 8 players in a ring of identical sectors around a rich centre."""
import math

import numpy as np

from .. import SQ
from ..biomes import BIOMES
from ..checks import connected, unit_masks
from ..design import Design
from ..noise import fbm, ridged, smoothstep
from ..symmetry import PLAYER_COLORS, RotSymmetry, rot_fields, rotate_points
from ..terrain import grid, pit, plateau
from .base import Param, Template
from .common import H_LOW, biome_param, ffa_boxes, flatten_all, size_param

RIDGE_HALF = 110.0          # half width of a ridge top (elmos)


class FFARing(Template):
    id = "ffa_ring"
    title = "FFA Ring"
    modes = ("ffa",)
    tags = ("land", "chokes")
    players = "3 to 8 players, free-for-all"
    description = ("Free-for-all: every player gets an identical sector of a round battlefield. Rock ridges "
                   "separate neighbours, with a pass between each pair; the richest metal waits in the "
                   "centre, where all players meet. A mountain rim closes the map.")
    infos = {
        "players": "Number of players. Each player gets one start box and an identical sector of the map, "
                   "rotated around the centre, so nobody has a better position. Zero-K gives every player "
                   "their own team; with fewer players than boxes some boxes stay empty. More players need "
                   "a bigger map: about 16x16 for 3-4 players, 20x20 for 5-6 and 24x24 for 7-8.",
        "dividers": "What separates neighbouring players. ridges: a rock ridge between each pair of sectors "
                    "with one pass in it, so neighbours meet at the pass or in the centre and early raids "
                    "take a known path. open: no ridges, every sector is open to both neighbours - more "
                    "chaotic games with fights everywhere.",
        "ridge_height": "Height of the ridges between the sectors in elmos above the ground. Tanks, hovers "
                        "and bots can only cross at the passes; spiders climb over. Higher ridges block more "
                        "line of sight and direct fire between neighbours. Only used with ridges.",
        "pass_width": "Width of the pass through each ridge in elmos. Narrow passes are easy to hold with a "
                      "few defences, so players can turtle against one neighbour; wide passes keep the "
                      "pressure on. Only used with ridges.",
        "centre": "The rich middle that every player can reach. hill: a low hill with gentle ramps on all "
                  "sides, high ground for whoever holds it. crater: a shallow bowl, so units inside are "
                  "easy to shell from the rim. flat: open ground.",
    }
    params = (
        size_param((16, 18, 20, 22, 24, 26, 28), 20, adv_smallest=10),
        biome_param("temperate"),
        Param("players", "Players", "int", 5, min=3, max=8, step=1, adv_min=2, adv_max=12,
              help="One start box and one identical sector per player"),
        Param("dividers", "Between neighbours", "choice", "ridges", choices=("ridges", "open"),
              help="ridges: rock ridges with a pass between neighbours; open: no ridges"),
        Param("ridge_height", "Ridge height", "int", 320, min=200, max=480, step=10, adv_min=60, adv_max=1200,
              help="Elmos above the ground"),
        Param("pass_width", "Pass width", "int", 600, min=380, max=900, step=20, adv_min=160, adv_max=2000,
              help="Usable width of the pass in each ridge, in elmos"),
        Param("centre", "Centre", "choice", "hill", choices=("hill", "crater", "flat"),
              help="Rich centre on a low hill, in a shallow crater or flat"),
    )

    def make(self, v, seed, log=print):
        N = int(v["players"])
        n = v["size"] * 64 + 1
        W = (n - 1) * SQ
        C = W / 2
        sym = RotSymmetry(N, W)
        rng = np.random.default_rng(seed)
        xx, zz = grid(n)
        dx, dz = xx - C, zz - C
        r = np.hypot(dx, dz)
        ang = np.arctan2(dz, dx)
        sec = 2 * math.pi / N
        rel = (ang - sym.a0 + sec / 2) % sec - sec / 2          # angle inside the own sector, 0 = base line

        Rp = 0.465 * W                                          # playable radius, mountain rim outside
        Rb = (0.31 if N <= 4 else 0.33) * W                    # start points
        Rc = 0.16 * W                                           # open ring around the centre
        starts = sym.starts(Rb)

        # noise, made rotationally symmetric before anything is built on it
        low = fbm((n, n), rng, base=5, octaves=6); low = (low - low.mean()) / (low.std() + 1e-6)
        hills = ridged((n, n), rng, base=7) ** 2.6
        en = fbm((n, n), rng, base=22, octaves=3)
        low, hills, en = rot_fields(sym, low, hills, en)
        en = en / (np.abs(en).max() + 1e-6)
        near = np.min([np.hypot(xx - x, zz - z) for x, z in starts], axis=0)
        calm = smoothstep(800, 1700, near) * smoothstep(Rc * 0.6, Rc * 1.2, r)
        h = (H_LOW + 12 * low + 60 * hills * calm).astype(np.float32)

        # centre
        if v["centre"] == "hill":
            plateau(h, r - 0.075 * W, H_LOW + 85 + 4 * low, side_deg=9, noise=en, amp=50, round_=120, toe=30)
        elif v["centre"] == "crater":
            pit(h, r - 0.085 * W, H_LOW - 55, side_deg=10, noise=en, amp=40, round_=120, toe=30)
            plateau(h, np.abs(r - 0.1 * W) - 90, H_LOW + 45 + 6 * low, side_deg=12, noise=en, amp=30,
                    round_=80, toe=20)

        # ridges between neighbours (on the sector borders), each with one pass
        r_pass = 0.75 * Rb
        passes = []
        if v["dividers"] == "ridges":
            border = np.abs(np.abs(rel) - sec / 2) * r              # distance to the nearest sector border
            sdf = border - RIDGE_HALF
            sdf = np.maximum(sdf, Rc - r)                           # ridges start outside the centre ring
            sdf = np.maximum(sdf, v["pass_width"] / 2 + 80 - np.abs(r - r_pass))
            plateau(h, sdf, H_LOW + v["ridge_height"] + 14 * low, side_deg=66, noise=en, amp=16)
            for k in range(N):
                passes.append(sym.polar(r_pass, math.degrees(sec / 2), k))

        # mountain rim: everything outside the playable circle (the square's corners are not fair)
        plateau(h, Rp - r, H_LOW + 520 + 60 * low, side_deg=62, noise=en, amp=60, round_=60, toe=20)

        # resources for player 0 (local frame: u = outwards from the centre, t = along the ring)
        a = sym.angle(0)
        ux, uz, tx, tz = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
        sx, sz = starts[0]

        def local(du, dt):
            return sx + du * ux + dt * tx, sz + du * uz + dt * tz

        def pol(rr, frac):                                       # frac of the half sector, + = towards player 1
            return sym.polar(rr, math.degrees(frac * sec / 2), 0)

        west = [(*local(-230, -230), 2.0), (*local(-230, 230), 2.0), (*local(260, 0), 2.0)]   # base spots
        exp = [(pol(Rb, 0.62), 2.2), (pol(Rb, -0.62), 2.2),                 # flanks, towards the neighbours
               (pol(0.235 * W, 0.0), 2.4),                                 # in front of the base
               (pol(0.40 * W, 0.45), 2.2), (pol(0.40 * W, -0.45), 2.2),    # behind, safe but far
               (pol(Rc + 260, 0.45), 2.7), (pol(Rc + 260, -0.45), 2.7)]    # inner ring, contested
        if v["size"] >= 20:
            exp += [(pol(0.30 * W, 0.3), 2.3), (pol(0.30 * W, -0.3), 2.3)]
        min_gap = 300.0
        for (x, z), val in exp:
            ok = all(math.hypot(x - px, z - pz) > min_gap for px, pz, _ in west)
            on_ridge = v["dividers"] == "ridges" and _border_dist(sym, x, z) < RIDGE_HALF + 260
            if ok and not on_ridge and math.hypot(x - C, z - C) < Rp - 350:
                west.append((x, z, val))
        rc = max(0.045 * W, 300 * N / (2 * math.pi))                 # centre spots, 300+ elmos apart
        west.append((*pol(rc, 0.0), 3.2))
        mexes = rotate_points(west, sym)
        for m in mexes:
            if math.hypot(m["x"] - sym.rotate(sx, sz, m["side"])[0], m["z"] - sym.rotate(sx, sz, m["side"])[1]) < 600:
                m["fixed"] = True
        geos = [sym.rotate(*pol(0.255 * W, 0.42 if v["dividers"] == "open" else 0.35), k) for k in range(N)]
        flatten_all(h, starts, mexes, geos, start_r=(330, 650))
        h = h.astype(np.float32)

        # passes as chokes, kept clear of rocks, wrecks and new metal spots
        clear = np.zeros(h.shape, bool)
        gates = []
        for k, (px, pz) in enumerate(passes):
            m = np.hypot(xx - px, zz - pz) < v["pass_width"] / 2 + 160
            clear |= m
            gates.append((f"Pass {k + 1}-{(k + 1) % N + 1}", m))
        rim = r > Rp - 120
        tanks = unit_masks(h)["tanks"]
        all_ok = all(connected(tanks, starts[0], s) for s in starts[1:])
        centre_ok = connected(tanks, starts[0], (C, C))
        notes = [f"Players: {N}, one identical sector each",
                 f"Tanks reach the centre: {'yes' if centre_ok else 'NO'}"]
        desc = (f"FFA Ring: {N}-player free-for-all. Every player gets an identical sector; "
                + ("rock ridges with a pass separate neighbours; " if passes else "open borders between neighbours; ")
                + f"the richest metal is in the {v['centre']} centre.")
        cols = [PLAYER_COLORS[k % len(PLAYER_COLORS)] for k in range(N)]
        return Design(hm=h, sym=sym, starts=starts, teams=[[s] for s in starts], mexes=mexes, geos=geos,
                      biome=dict(BIOMES[v["biome"]]), title="FFA Ring", description=desc,
                      startboxes=ffa_boxes(sym, starts, Rb - 650, min(Rb + 700, Rp - 150)),
                      gates=gates or None, keep_clear=clear | rim, tree_block=clear,
                      notes=notes, notes_ok=all_ok and centre_ok, start_colors=cols,
                      side_labels=("your base", "every other base"))


def _border_dist(sym, x, z):
    """Distance (elmos) of a point to the nearest sector border line."""
    sec = 2 * math.pi / sym.n
    r = math.hypot(x - sym.cx, z - sym.cz)
    rel = (math.atan2(z - sym.cz, x - sym.cx) - sym.a0 + sec / 2) % sec - sec / 2
    return abs(abs(rel) - sec / 2) * r

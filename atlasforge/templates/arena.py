"""Arena (4 players): every base sits inside a rock ring with gates; open ground and a rich centre between.
2v2 (West vs East) or free-for-all with 4 players. Four-fold symmetric."""
import math

import numpy as np

from .. import SQ
from ..biomes import BIOMES
from ..design import Design
from ..gadgets import lava_cliff_files, lava_cliff_mask, paint_field
from ..noise import fbm, ridged, smoothstep
from ..symmetry import Symmetry
from ..terrain import grid, plateau, ring_sdf
from .base import Param, Template
from .common import biome_param, corners, d4, d4_points, flatten_all, four_base_boxes, size_param, sym_fields

H_LOW, H_MID = 100.0, 150.0
WALL_HALF = 75
GATE_HW = 115


class Arena(Template):
    id = "arena"
    title = "Arena (4 players)"
    modes = ("team", "ffa")
    tags = ("land", "chokes")
    players = "2v2 or 4-player FFA"
    description = ("Four bases, each inside a rock ring with gates. Safe economy inside, open ground outside "
                   "and a rich centre. Plays as 2v2 or as a 4-player free-for-all.")
    infos = {
        "ring": "Distance from each base to its rock ring in elmos, so it sets how much safe room each player has inside. A small ring keeps the economy tight and the gates close to the base; a large ring gives room for more buildings but longer walks to the gates.",
        "gates": "Openings in each ring. 1: a single gate towards the centre, very easy to defend. 2: towards the centre and the neighbouring base. 3: in every direction, so the ring is more of a fence than a fortress.",
        "wall_height": "Height of the ring walls above the ground in elmos. Tanks, hovers and bots cannot pass the walls except through the gates; spiders can climb over. Higher walls block more line of sight and direct fire.",
        "centre": "The rich middle of the map. hill: a low hill with extra metal that gives the holder a view over the field. flat: open ground with the same metal, easier to attack.",
        "lava_tops": "Puts lava on top of the ring walls. Spiders that climb over take slow damage, so the walls stay a real barrier for them too.",
    }
    params = (
        size_param((12, 14, 16, 18, 20), 16, adv_smallest=6),
        biome_param("desert"),
        Param("ring", "Ring radius", "int", 1250, min=900, max=1600, step=50, adv_min=500, adv_max=2400, help="Elmos from the base to the wall"),
        Param("gates", "Gates per ring", "int", 2, min=1, max=3, step=1,
              help="1: one way out towards the centre; 2: towards the edge and the neighbour; 3: all of them"),
        Param("wall_height", "Wall height", "int", 420, min=250, max=600, step=10, adv_min=80, adv_max=1500, help="Elmos above the ground"),
        Param("centre", "Centre", "choice", "hill", choices=("hill", "flat"), help="Rich centre on a low hill or flat"),
        Param("lava_tops", "Lava on the walls", "bool", False, help="Wall tops glow and slowly damage climbing spiders"),
    )

    def make(self, v, seed, log=print):
        size = v["size"]
        n = size * 64 + 1
        W = (n - 1) * SQ
        C = W / 2
        s = W / 8192.0
        RW = v["ring"]
        base = (1850.0 * s, 1850.0 * s)
        rng = np.random.default_rng(seed)
        xx, zz = grid(n)
        low = fbm((n, n), rng, base=5, octaves=6); low = (low - low.mean()) / (low.std() + 1e-6)
        hills = ridged((n, n), rng, base=7) ** 2.8
        en = fbm((n, n), rng, base=24, octaves=3); en /= np.abs(en).max() + 1e-6
        low, hills, en = sym_fields("d4", low, hills, en)                # seamless four-way symmetry
        bx, bz = base
        rb = np.hypot(xx - bx, zz - bz)
        calm = smoothstep(RW - 200, RW + 200, rb)
        h = (H_LOW + 12 * low + 55 * hills * calm).astype(np.float32)
        rc = np.hypot(xx - C, zz - C)
        if v["centre"] == "hill":
            plateau(h, rc - 520 * s, H_MID + 6 * low, side_deg=9, noise=en, amp=60)
        gate_angles = {1: (45,), 2: (5, 85), 3: (5, 45, 85)}[v["gates"]]
        plateau(h, ring_sdf(xx, zz, bx, bz, RW, WALL_HALF, gate_angles, GATE_HW + 145),
                v["wall_height"] + 18 * low, side_deg=70, noise=en, amp=14)
        h = d4(h)

        starts_nw = corners(base, W)                 # NW, NE, SW, SE
        pts = []
        for ang in (120, 170, 220, 265, 315):        # inside the ring, away from the gates
            t = math.radians(ang)
            pts.append((bx + 0.51 * RW * math.cos(t), bz + 0.51 * RW * math.sin(t), 2.0))
        pts.append((bx - 0.2 * RW, bz + 0.21 * RW, 2.0))
        pts += [(3400 * s, 420 * s, 2.4), (420 * s, 3400 * s, 2.4), (3700 * s, 1150 * s, 2.6), (1150 * s, 3700 * s, 2.6),
                (3500 * s, 2650 * s, 2.8), (2650 * s, 3500 * s, 2.8), (3150 * s, 3150 * s, 3.0), (C - 330 * s, C - 330 * s, 3.4)]
        pts = [p for p in pts if abs(math.hypot(p[0] - bx, p[1] - bz) - RW) > 220]   # keep mexes off the wall
        mexes = [dict(x=float(x), z=float(z), metal=val, side=0) for x, z, val in d4_points(pts, W)]
        geos = [(x, z) for x, z in d4_points([(bx + 0.22 * RW, bz - 0.24 * RW), (C, C)], W)]
        flatten_all(h, starts_nw, mexes, geos, start_r=(320, 620))
        h = d4(h).astype(np.float32)

        nw, ne, sw, se = starts_nw
        team0, team1 = [nw, sw], [ne, se]
        gates_mask = np.zeros(h.shape, bool)
        # gate areas of all four rings (mirror the NW gates)
        for (cx, cz), (fx, fz) in zip(starts_nw, ((1, 1), (-1, 1), (1, -1), (-1, -1))):
            for g in gate_angles:
                t = math.radians(g)
                gx, gz_ = cx + fx * RW * math.cos(t), cz + fz * RW * math.sin(t)
                gates_mask |= np.hypot(xx - gx, zz - gz_) < 450
        from ..checks import connected, unit_masks
        inside_ok = not connected(unit_masks(h)["tanks"] & ~gates_mask, base, (C, C))
        notes = [f"Bases are only reachable through their gates: {'yes' if inside_ok else 'NO'}"]
        files, paint, hazard = {}, None, None
        if v["lava_tops"]:
            hazard = lava_cliff_mask(h, starts_nw)
            files, _ = lava_cliff_files(hazard)
            paint = dict(lava=paint_field(hazard))
        desc = (f"Arena: four bases, each inside a rock ring with {v['gates']} gate{'s' if v['gates'] > 1 else ''}, "
                "open ground and a rich centre. 2v2 (West vs East) or 4-player free-for-all.")
        return Design(hm=h, sym=Symmetry("ew", W, W), starts=[nw, ne, sw, se], teams=[team0, team1], mexes=mexes,
                      geos=geos, biome=BIOMES[v["biome"]], title="Arena", description=desc,
                      startboxes=four_base_boxes(team0, team1, ("West", "W"), ("East", "E"), W),
                      paint=paint, extra_files=files, random_trees=False, notes=notes, notes_ok=inside_ok,
                      hazard=hazard, start_colors=[(60, 255, 60), (255, 70, 70), (60, 255, 60), (255, 70, 70)])

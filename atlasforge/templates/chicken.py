"""Chicken Defense: co-op against the chicken AI. Players start in the core of nested ring walls whose gates
alternate south / north / south, so chickens must walk the longest way; players can fall back ring by ring.
Chicken roosts are kept out of the walled area by a map gadget."""
import math

import numpy as np
from scipy import ndimage

from .. import SQ
from ..biomes import BIOMES
from ..design import Design
from ..gadgets import chicken_zone_files, lava_cliff_files, lava_cliff_mask, paint_field
from ..noise import fbm, ridged, smoothstep
from ..symmetry import Symmetry
from ..terrain import flatten_disc, grid, plateau, ring_sdf
from .base import Param, Template
from .common import biome_param, coop_boxes, size_param

H_LOW = 100.0
WALL_HALF = 90


class ChickenRings(Template):
    id = "chicken"
    title = "Chicken Defense"
    modes = ("coop",)
    tags = ("land", "chokes")
    players = "1-4 players vs chickens"
    description = ("Co-op against chickens. Players start inside nested ring walls whose gates alternate, so "
                   "chickens walk the longest way and players can fall back ring by ring.")
    infos = {
        "rings": "Number of nested ring walls around the players. The chickens come from one corner and have to walk around each ring to its gate, and the gates alternate sides. More rings mean longer walks for the chickens and more lines to fall back to.",
        "gate_width": "Width of the ring gates in elmos. Narrow gates are easier to block with defences but also funnel your own army; wide gates let large waves through.",
        "wall_height": "Height of the ring walls above the ground in elmos. Walking chickens must use the gates; flying chickens ignore the walls.",
        "lava_tops": "Puts lava on top of the ring walls so climbing units take slow damage and cannot use the walls as a shortcut.",
    }
    params = (
        size_param((16, 18, 20), 20),
        biome_param("alien"),
        Param("rings", "Ring walls", "int", 3, min=2, max=3, step=1, adv_min=1, adv_max=5),
        Param("gate_width", "Gate width", "int", 400, min=260, max=700, step=20, adv_min=150, adv_max=1500, help="Elmos"),
        Param("wall_height", "Wall height", "int", 400, min=250, max=600, step=10, adv_min=80, adv_max=1500),
        Param("lava_tops", "Lava on the walls", "bool", False, help="Wall tops slowly damage climbing units"),
    )

    def make(self, v, seed, log=print):
        size = v["size"]
        n = size * 64 + 1
        W = (n - 1) * SQ
        C = W / 2
        s = W / 10240.0
        radii = {3: [1100 * s, 2300 * s, 3500 * s], 2: [1300 * s, 3000 * s]}.get(
            v["rings"]) or list(np.linspace(1100 * s, 3900 * s, v["rings"]) if v["rings"] > 1 else [2300 * s])
        gates = [90 if k % 2 == 0 else 270 for k in range(len(radii))]
        gates = gates[::-1] if len(radii) % 2 == 0 else gates            # outermost gate always south
        rng = np.random.default_rng(seed)
        xx, zz = grid(n)
        low = fbm((n, n), rng, base=6, octaves=6); low = (low - low.mean()) / (low.std() + 1e-6)
        hills = ridged((n, n), rng, base=7) ** 2.6
        en = fbm((n, n), rng, base=26, octaves=3); en /= np.abs(en).max() + 1e-6
        r = np.hypot(xx - C, zz - C)
        outer = radii[-1]
        inside = 1 - smoothstep(outer - 200, outer + 200, r)
        h = (H_LOW + 14 * low + 90 * hills * (1 - inside * 0.85)).astype(np.float32)
        ghw = v["gate_width"] / 2
        for R, g in zip(radii, gates):
            plateau(h, ring_sdf(xx, zz, C, C, R, WALL_HALF, [g], ghw), v["wall_height"] + 15 * low, side_deg=72,
                    noise=en, amp=12)

        players = [(C + 550 * s * math.cos(math.radians(a)), C + 550 * s * math.sin(math.radians(a)))
                   for a in (45, 135, 225, 315)]
        ring_pts = lambda rad, k, off, val: [(C + rad * math.cos(math.radians(off + i * 360 / k)),
                                              C + rad * math.sin(math.radians(off + i * 360 / k)), val) for i in range(k)]
        pts = ring_pts(radii[0] * 0.73, 6, 0, 2.0)
        for k in range(1, len(radii)):
            pts += ring_pts((radii[k - 1] + radii[k]) / 2, 8 + 4 * (k - 1), 22.5 / k, 2.4 + 0.2 * k)
        pts += ring_pts(outer + 800 * s, 8, 22.5, 3.0)
        corner = 700 * s
        pts += [(corner, corner, 3.2), (W - corner, corner, 3.2), (corner, W - corner, 3.2), (W - corner, W - corner, 3.2)]
        mexes = [dict(x=float(x), z=float(z), metal=val, side=0) for x, z, val in pts
                 if all(abs(math.hypot(x - C, z - C) - R) > 230 for R in radii)]
        geos = [(C, C), (C - 0.166 * W, C + 0.04 * W), (C + 0.166 * W, C - 0.04 * W)]
        for p in players:
            flatten_disc(h, p[0], p[1], 300, 600)
        for m in mexes:
            flatten_disc(h, m["x"], m["z"], 45, 100)
        for g in geos:
            flatten_disc(h, g[0], g[1], 55, 110)
        h = h.astype(np.float32)

        chicken_pt = (750 * s, W - 750 * s)                  # centre of the chicken start box (south-west)
        gate_masks = []
        for k, (R, g) in enumerate(zip(radii, gates)):
            t = math.radians(g)
            gate_masks.append((f"ring {k + 1} gate ({'south' if g == 90 else 'north'})",
                               np.hypot(xx - (C + R * math.cos(t)), zz - (C + R * math.sin(t))) < 600))
        from ..checks import connected, unit_masks
        notes, ok = [], True
        am = unit_masks(h)["amphibians"]
        for name, gm in gate_masks:
            only = not connected(am & ~gm, players[0], chicken_pt)
            notes.append(f"Chickens must pass the {name}: {'yes' if only else 'NO'}")
            ok &= only
        files = chicken_zone_files(h, [dict(x=C, z=C, r=outer + 150)])
        paint, hazard = None, None
        if v["lava_tops"]:
            hazard = lava_cliff_mask(h, players)
            f2, _ = lava_cliff_files(hazard)
            files.update(f2)
            paint = dict(lava=paint_field(hazard))
        block = np.zeros(h.shape, bool)
        for R in radii:
            block |= np.abs(r - R) < 400
        pb = 900 * s
        desc = (f"Chicken defense: co-op inside {len(radii)} ring walls with alternating gates. "
                "Chickens take the long way; fall back inwards when a ring breaks.")
        return Design(hm=h, sym=Symmetry("diag", W, W), starts=players, teams=[players, [chicken_pt]], mexes=mexes,
                      geos=geos, biome=BIOMES[v["biome"]], title="Chicken Rings", description=desc,
                      startboxes=coop_boxes((C - pb, C - pb, C + pb, C + pb), (0, W - 1500 * s, 1500 * s, W), players),
                      paint=paint, extra_files=files, tree_block=block, notes=notes, notes_ok=ok, hazard=hazard,
                      start_colors=[(60, 255, 60)] * 4, side_labels=("the players", "chicken land"))

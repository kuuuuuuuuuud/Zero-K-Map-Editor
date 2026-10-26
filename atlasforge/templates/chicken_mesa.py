"""Chicken Mesa: co-op defenders hold one high mesa and fall back to its centre."""
import math

import numpy as np

from .. import SQ
from ..biomes import BIOMES
from ..design import Design
from ..gadgets import chicken_zone_files
from ..noise import fbm, ridged
from ..symmetry import Symmetry
from ..terrain import flatten_disc, grid, plateau, road
from .base import Param, Template
from .common import coop_boxes, biome_param, size_param


class ChickenMesaTemplate(Template):
    id = "chicken_mesa"
    title = "Chicken Mesa"
    modes = ("coop",)
    tags = ("land", "chokes")
    players = "1-4 players vs chickens"
    description = ("Defend one shared high mesa against chicken waves using several ramps. "
                   "When the outer approaches fail, fall back to a central position.")
    infos = {
        "mesa_height": "Height of the mesa above the surrounding land in elmos. A higher mesa gives defenders a stronger firing position, while making every ramp longer and more exposed. Choose 180 for a moderate height or 360 for a commanding but harder-to-reach summit.",
        "ramps": "Number of separate routes up the mesa. More ramps let defenders split their forces and give chickens more approaches to attack. Two routes are easier to cover; four spread the defence around the plateau.",
        "ramp_width": "Flat width of each ramp in elmos. Wider ramps give large armies more room to climb and make each approach harder to hold. Narrow ramps concentrate the fight into a smaller front.",
    }
    params = (
        size_param((16, 18, 20), 20),
        biome_param("alien"),
        Param("mesa_height", "Mesa height", "int", 260, min=160, max=360, step=20,
              adv_min=80, adv_max=600, help="Elmos above the surrounding land"),
        Param("ramps", "Mesa ramps", "int", 3, min=2, max=4, step=1,
              adv_min=1, adv_max=6, help="Number of separate routes up the mesa"),
        Param("ramp_width", "Ramp width", "int", 420, min=300, max=600, step=20,
              adv_min=180, adv_max=900, help="Flat width of each ramp in elmos"),
    )

    def make(self, v, seed, log=print):
        size = v["size"]
        n = size * 64 + 1
        W = (n - 1) * SQ
        C = W / 2
        s = W / 10240.0
        rng = np.random.default_rng(seed)
        xx, zz = grid(n)

        # The seed changes both the summit outline and the surrounding terrain.
        low = fbm((n, n), rng, base=7, octaves=5)
        low = (low - low.mean()) / (low.std() + 1e-6)
        detail = ridged((n, n), rng, base=18) ** 2.2
        edge_noise = fbm((n, n), rng, base=24, octaves=3)
        edge_noise /= np.abs(edge_noise).max() + 1e-6
        angle = rng.uniform(0, 2 * math.pi)
        ca, sa = math.cos(angle), math.sin(angle)
        dx, dz = xx - C, zz - C
        rx, rz = dx * ca + dz * sa, -dx * sa + dz * ca
        # Slightly asymmetric lowlands and a broad, irregular summit avoid a flat arena.
        r = np.hypot(rx / 1.06, rz / 0.96)
        mesa_r = 0.285 * W
        outline = r - mesa_r + 95 * np.sin(3 * np.arctan2(rz, rx) + angle)
        h = (100 + 12 * low + (18 + 22 * detail) * (r > mesa_r + 100)).astype(np.float32)
        top = 100 + v["mesa_height"]
        plateau(h, outline, top + 10 * low + 12 * detail, side_deg=72,
                noise=edge_noise, amp=22, round_=110, toe=35)

        ramp_count = int(v["ramps"])
        phase = angle + rng.uniform(-0.22, 0.22)
        ramp_len = (v["mesa_height"] / math.tan(math.radians(15)))
        ramp_half = v["ramp_width"] / 2
        clear = np.zeros(h.shape, dtype=bool)
        gates = []
        ramp_angles = phase + np.arange(ramp_count) * (2 * math.pi / ramp_count)
        for k, a in enumerate(ramp_angles):
            ux, uz = math.cos(a), math.sin(a)
            p0 = (C + ux * (mesa_r + ramp_len), C + uz * (mesa_r + ramp_len))
            p1 = (C + ux * (mesa_r - 220), C + uz * (mesa_r - 220))
            road(h, p0, p1, ramp_half, 100, top, down_deg=30, up_deg=30)
            along = dx * ux + dz * uz
            across = -dx * uz + dz * ux
            mask = ((along > mesa_r - ramp_len - 300) & (along < mesa_r + ramp_len + 300) &
                    (np.abs(across) < ramp_half + 220))
            clear |= mask
            gates.append((f"Mesa ramp {k + 1}", mask))

        players = [(C + 520 * s * math.cos(math.radians(a)),
                    C + 520 * s * math.sin(math.radians(a))) for a in (45, 135, 225, 315)]
        # Expansion metal sits outside the mesa and away from the ramp corridors.
        mexes = []
        for k in range(16):
            a = 2 * math.pi * k / 16 + angle * 0.37
            radius = mesa_r + 820 * s
            x, z = C + radius * math.cos(a), C + radius * math.sin(a)
            if any(abs(math.atan2(math.sin(a - ra), math.cos(a - ra))) < 0.20 for ra in ramp_angles):
                continue
            mexes.append(dict(x=float(x), z=float(z), metal=2.3, side=0))
        # Four safe outer deposits preserve options even when a ramp crosses the ring.
        corner = 760 * s
        mexes.extend(dict(x=float(x), z=float(z), metal=2.8, side=0) for x, z in
                         ((corner, corner), (W-corner, corner), (corner, W-corner), (W-corner, W-corner)))
        geos = [(C - 0.39 * W, C), (C + 0.39 * W, C)]
        for p in players:
            flatten_disc(h, p[0], p[1], 300, 600)
        for m in mexes:
            flatten_disc(h, m["x"], m["z"], 45, 100)
        for x, z in geos:
            flatten_disc(h, x, z, 55, 110)

        chicken_pt = (0.075 * W, 0.925 * W)
        files = chicken_zone_files(h, [dict(x=C, z=C, r=mesa_r + 180)])
        desc = ("Chicken defence: hold the high central mesa through several exposed ramps. "
                "As the approaches fall, retreat to the mesa's centre.")
        box = 0.17 * W
        enemy_box = 0.14 * W
        return Design(
            hm=h.astype(np.float32), sym=Symmetry("diag", W, W), starts=players,
            teams=[players, [chicken_pt]], mexes=mexes, geos=geos,
            biome=dict(BIOMES[v["biome"]]), title=self.title, description=desc,
            startboxes=coop_boxes((C-box, C-box, C+box, C+box),
                                  (0, W-enemy_box, enemy_box, W), players),
            gates=gates, keep_clear=clear, tree_block=clear,
            extra_files=files, side_labels=("the players", "chicken land"),
            start_colors=[(60, 255, 60)] * 4,
        )

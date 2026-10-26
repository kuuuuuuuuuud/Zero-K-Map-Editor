"""Chokepoint Front: a rock barrier splits West from East; only a few gates lead through.

Gate types (engine slope limits: tanks/hovers 27 degrees real, bots/amphibians 54):
  level  natural ground, everyone passes
  hump   42 degree rock hump: bots and amphibians climb it, tanks and hovers do not
  water  deep water channel: hovers and amphibians only
"""
import math

import numpy as np

from .. import SQ
from ..biomes import BIOMES
from ..formats import west_east_boxes_lua
from ..gadgets import lava_cliff_files, lava_cliff_mask, paint_field
from ..symmetry import Symmetry, mirror_east_west, mirror_pairs
from ..terrain import box_sdf, pit, plateau
from .base import Param, Template
from .common import base_terrain, biome_param, flatten_all, size_param

GATE_MIXES = {
    "mixed": ("level", "hump", "water", "level"),
    "level": ("level",) * 4,
    "bots and hovers": ("hump", "level", "water", "hump"),
}
MIX_ORDER = {1: [0], 2: [0, 1], 3: [1, 0, 2], 4: [1, 0, 2, 3]}     # which mix entry each gate gets (north->south)


class Chokepoint(Template):
    id = "chokepoint"
    title = "Chokepoint Front"
    modes = ("1v1", "team")
    tags = ("land", "chokes")
    players = "1v1 to 3v3"
    description = ("West vs East, split by a long rock barrier. A few gates lead through: level ground for "
                   "everyone, rock humps only bots can climb, or water channels for hovers and amphibians.")
    infos = {
        "gates": "Number of openings in the rock barrier between the two sides. Each gate is a choke where armies meet. One gate makes a single front that is easy to defend and hard to break; three or four gates spread the fight out and reward raids and flanking.",
        "gate_mix": "Which units can use each gate. level: flat ground, every unit passes. hump: a rock hump only bots and spiders can climb. water: a channel only hovers and amphibians (and ships, if deep enough) can use. mixed gives one of each; level opens every gate to everyone; 'bots and hovers' leaves tanks only one level gate in the middle.",
        "gate_width": "Usable width of each gate in elmos (a small tank is about 30 elmos wide). Narrow gates (300) are easy to block with a few defences; wide gates (800 and more) let large armies pass and make defending harder.",
        "wall_height": "Height of the barrier above the ground in elmos. Every height blocks tanks, hovers and bots. Higher walls block more line of sight and more direct fire; artillery and aircraft still shoot over them. Spiders can climb any height.",
        "lava_tops": "Puts glowing lava on top of the barrier. Spiders that climb across take slow damage, so the barrier is not a free road for them. Turn it off if spiders should be able to cross safely.",
    }
    params = (
        size_param((12, 14, 16, 18, 20), 16, adv_smallest=8),
        biome_param("temperate"),
        Param("gates", "Gates", "int", 3, min=1, max=4, step=1, adv_max=8, help="Number of openings in the barrier"),
        Param("gate_mix", "Gate types", "choice", "mixed", choices=tuple(GATE_MIXES),
              help="mixed: level, hump and water gates; level: all gates open to everyone; "
                   "bots and hovers: tanks get only one level gate"),
        Param("gate_width", "Gate width", "int", 520, min=300, max=900, step=20, adv_min=150, adv_max=2000, help="Usable width in elmos"),
        Param("wall_height", "Barrier height", "int", 430, min=250, max=650, step=10, adv_min=80, adv_max=1500, help="Elmos above the ground"),
        Param("lava_tops", "Lava on the barrier", "bool", True,
              help="Barrier tops glow with lava and slowly damage spiders that climb up"),
    )

    def make(self, v, seed, log=print):
        size = v["size"]
        n = size * 64 + 1
        W = (n - 1) * SQ
        C = W / 2
        s = W / 8192.0
        rng = np.random.default_rng(seed)
        h, xx, zz, low, en = base_terrain(n, rng, 1500 * s, C, sym="ew")
        ax = np.abs(xx - C)
        G = v["gates"]
        mix = GATE_MIXES[v["gate_mix"]]
        types = [mix[i] for i in (MIX_ORDER.get(G) or [(1, 0, 2, 3)[k % 4] for k in range(G)])]
        if "level" not in types:
            types[len(types) // 2] = "level"
        gz = [W * (0.12 + 0.76 * (k + 0.5) / G) for k in range(G)]
        ghw = v["gate_width"] / 2
        wall_h = float(v["wall_height"])
        for z0, t in zip(gz, types):           # water channels first, the barrier is rebuilt around them
            if t == "water":
                pit(h, box_sdf(xx, zz, C, z0, 300, ghw + 130), -150, side_deg=20)
        wall = ax - 260
        for z0 in gz:
            wall = np.maximum(wall, ghw + 130 - np.abs(zz - z0))
        plateau(h, wall, wall_h + 10 * low, side_deg=74, noise=en, amp=10)
        hump_h = min(300.0, wall_h - 60)
        for z0, t in zip(gz, types):
            if t == "hump":
                plateau(h, np.maximum(ax - 60, np.abs(zz - z0) - ghw - 60), hump_h, side_deg=42)
        h = mirror_east_west(h)

        team0 = [(0.104 * W, C - 0.207 * W), (0.104 * W, C + 0.207 * W)]
        team1 = [(W - x, z) for x, z in team0]
        west = []
        for sx, sz in team0:
            west += [(sx - 330, sz - 260, 2.0), (sx - 330, sz + 260, 2.0), (sx + 380, sz, 2.0)]
        for x, z, val in [(500, 500, 2.0), (500, 8192 - 500, 2.0), (1500, 4096, 2.2), (1700, 1200, 2.2),
                          (1700, 8192 - 1200, 2.2), (2400, 2600, 2.4), (2400, 8192 - 2600, 2.4)]:
            west.append((x * s, z * s, val))
        for z0 in gz:
            west.append((C - 0.146 * W, z0, 2.6))
        west.append((C - 0.11 * W, W * 0.6, 2.8))
        sym = Symmetry("ew", W, W)
        mexes = mirror_pairs(west, sym)
        geos = [(0.16 * W, C - 0.085 * W)]
        geos = geos + [sym.mirror(*g) for g in geos]
        flatten_all(h, team0 + team1, mexes, geos)
        h = mirror_east_west(h).astype(np.float32)

        names = {"level": "level gate", "hump": "rock hump", "water": "water channel"}
        gates = [(f"{names[t]} {k + 1}", (ax < 1500 * s) & (np.abs(zz - z0) < ghw + 250))
                 for k, (z0, t) in enumerate(zip(gz, types))]
        files, paint, hazard = {}, None, None
        if v["lava_tops"]:
            hazard = lava_cliff_mask(h, team0 + team1)
            files, _ = lava_cliff_files(hazard)
            paint = dict(lava=paint_field(hazard))
        kinds = ", ".join(f"{names[t]}" for t in types)
        desc = (f"2v2 chokepoint map: a rock barrier with {G} gate{'s' if G > 1 else ''} ({kinds}). "
                "Tanks need level ground, bots climb rock humps, hovers and amphibians use water channels.")
        return _design(h, sym, team0, team1, mexes, geos, BIOMES[v["biome"]], "Chokepoint Front", desc, gates,
                       files, paint, hazard, W, block=(ax < 1600 * s) | (hazard if hazard is not None else False))


def _design(h, sym, team0, team1, mexes, geos, biome, title, desc, gates, files, paint, hazard, W, block):
    from ..design import Design
    return Design(hm=h, sym=sym, starts=team0 + team1, teams=[team0, team1], mexes=mexes, geos=geos, biome=biome,
                  title=title, description=desc, startboxes=west_east_boxes_lua(W, W, team0, team1),
                  paint=paint, extra_files=files, tree_block=np.asarray(block, bool) if not np.isscalar(block) else None,
                  gates=gates, hazard=hazard)

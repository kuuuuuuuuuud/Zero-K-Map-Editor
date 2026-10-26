"""River Crossing: a river or lava lake splits West from East. Low fords cross it; with lava tides the
fords flood every few minutes while an optional causeway stays safe."""
import math

import numpy as np
from scipy import ndimage

from .. import SQ
from ..biomes import BIOMES
from ..design import Design
from ..formats import west_east_boxes_lua
from ..gadgets import lava_config, tide_files
from ..noise import smoothstep
from ..symmetry import Symmetry, mirror_east_west, mirror_pairs
from ..terrain import pit, road_polyline, smooth_profile
from .base import Param, Template
from .common import base_terrain, biome_param, flatten_all, size_param

FORD_H = 20.0
FORD_HW = 170
FLOOD = 60


class RiverCrossing(Template):
    id = "river"
    title = "River Crossing"
    modes = ("1v1", "team")
    tags = ("land", "chokes", "twist")
    players = "1v1 to 3v3"
    description = ("West vs East across a river or a lava lake. Low fords cross it; with lava tides the fords "
                   "flood every few minutes (on-screen countdown) while a causeway in the middle stays safe.")
    infos = {
        "mode": "What divides the two sides. 'lava tides': a lava lake whose fords flood on a timer (a countdown is shown in game), so attacks have to be timed. 'lava': the fords stay open all game. 'water': a deep river; hovers, amphibians and ships can cross anywhere, the other units only at the fords.",
        "fords": "Number of low crossings over the river. Fords are the chokes of this map: few fords make heavy fights at one or two places, more fords spread the front out.",
        "causeway": "A natural land bridge in the middle of the river that never floods. It gives a safe but well-known route across, even during high tide. Without it, crossings during floods are impossible.",
        "width": "Width of the river in elmos. A wide river keeps the bases further apart and gives artillery on the banks less reach over it; a narrow river lets units on one bank shoot the other.",
        "calm_seconds": "Lava tides only: how long the fords stay open between floods, in seconds. Longer calm periods mean more time to attack across; short ones make crossings risky.",
        "flood_seconds": "Lava tides only: how long the fords stay flooded, in seconds. Units on a ford when the lava rises take heavy damage.",
    }
    params = (
        size_param((12, 14, 16, 18, 20), 16, adv_smallest=8),
        biome_param("volcanic"),
        Param("mode", "River", "choice", "lava tides", choices=("lava tides", "lava", "water"),
              help="lava tides: fords flood on a schedule; lava: lava lake, fords always open; "
                   "water: deep river, hovers and amphibians can cross anywhere"),
        Param("fords", "Fords", "int", 2, min=1, max=3, step=1, adv_max=7, help="Low crossings"),
        Param("causeway", "Safe causeway", "bool", True, help="A natural land bridge in the middle that never floods"),
        Param("width", "River width", "int", 1900, min=1200, max=2600, step=100, adv_min=500, adv_max=4500, help="Elmos"),
        Param("calm_seconds", "Low tide (s)", "int", 150, min=60, max=300, step=10, adv_min=10, adv_max=1800, help="Lava tides only"),
        Param("flood_seconds", "High tide (s)", "int", 45, min=20, max=90, step=5, adv_min=5, adv_max=900, help="Lava tides only"),
    )

    def make(self, v, seed, log=print):
        size = v["size"]
        n = size * 64 + 1
        W = (n - 1) * SQ
        C = W / 2
        s = W / 8192.0
        LAKE = v["width"] / 2
        rng = np.random.default_rng(seed)
        h, xx, zz, low, en = base_terrain(n, rng, 1500 * s, C, sym="ew")
        ax = np.abs(xx - C)
        h = np.maximum(h, 85).astype(np.float32)           # land always above the high tide (60)
        crossings = v["fords"] + (1 if v["causeway"] else 0)
        slots = [W * (k + 0.5) / crossings for k in range(crossings)]
        cause_z = None
        if v["causeway"]:
            cause_z = min(slots, key=lambda z: abs(z - C))
        fords = [z for z in slots if z != cause_z]
        lake = ax - LAKE
        if cause_z is not None:
            lake = np.maximum(lake, 280 - np.abs(zz - cause_z))
        pit(h, lake, -70 + 6 * low, side_deg=62, noise=en, amp=25)
        hs = ndimage.gaussian_filter(h, 12)
        for fz in fords:
            jz = int(fz / SQ)
            x0, x1 = C - LAKE - 620, C + LAKE + 620
            xs = np.linspace(x0, x1, 900)
            hw_, he_ = float(hs[jz, int(x0 / SQ)]), float(hs[jz, int(x1 / SQ)])
            pw = smooth_profile(xs - x0, 640, hw_, FORD_H, 220)
            pe = smooth_profile(x1 - xs, 640, he_, FORD_H, 220)
            prof = np.where(xs < C, pw, pe)
            road_polyline(h, np.stack([xs, np.full_like(xs, fz)], 1), prof, FORD_HW, down_deg=45, up_deg=30,
                          influence=700, blend=200)
        h = mirror_east_west(h)

        team0 = [(0.104 * W, C - 0.207 * W), (0.104 * W, C + 0.207 * W)]
        team1 = [(W - x, z) for x, z in team0]
        west = []
        for sx, sz in team0:
            west += [(sx - 330, sz - 260, 2.0), (sx - 330, sz + 260, 2.0), (sx + 380, sz, 2.0)]
        for x, z, val in [(500, 500, 2.0), (500, 8192 - 500, 2.0), (1500, 4096, 2.2), (1700, 1200, 2.2),
                          (1700, 8192 - 1200, 2.2)]:
            west.append((x * s, z * s, val))
        bank = C - LAKE - 450
        for fz in fords:
            west.append((bank - 150, fz + (420 if fz < C else -420), 2.8))      # rich, risky spots at the fords
        if cause_z is not None:
            west += [(bank, cause_z - 470, 2.6), (bank, cause_z + 470, 2.6)]
        sym = Symmetry("ew", W, W)
        mexes = mirror_pairs(west, sym)
        geos = [(0.16 * W, C - 0.085 * W)]
        geos = geos + [sym.mirror(*g) for g in geos]
        flatten_all(h, team0 + team1, mexes, geos)
        h = mirror_east_west(h).astype(np.float32)

        gates = [(f"ford {k + 1}", (ax < LAKE + 600) & (np.abs(zz - fz) < 320)) for k, fz in enumerate(fords)]
        if cause_z is not None:
            gates.append(("causeway", (ax < LAKE + 600) & (np.abs(zz - cause_z) < 320)))
        mode = v["mode"]
        biome = dict(BIOMES[v["biome"]])
        files, paint, notes, notes_ok = {}, None, [], True
        blocked = None
        if mode.startswith("lava"):
            biome["water_damage"] = 0
            blocked = h < 1
            sea = (1 - smoothstep(-10, 4, h)).astype(np.float32)
            if mode == "lava tides":
                files["mapconfig/lava_config.lua"] = lava_config(FLOOD, calm_s=v["calm_seconds"],
                                                                 high_s=v["flood_seconds"], title="River Crossing tides")
                zones = [(C - LAKE - 450, fz - FORD_HW - 60, C + LAKE + 450, fz + FORD_HW + 60) for fz in fords]
                files.update(tide_files(zones, FLOOD))
                near = np.zeros(h.shape, bool)
                for fz in fords:
                    near |= (np.abs(zz - fz) < 700) & (ax < LAKE + 800)
                paint = dict(scorch=((1 - smoothstep(FLOOD - 4, FLOOD + 6, h)) * near).astype(np.float32), lava=sea)
                if cause_z is not None:
                    from ..checks import connected, unit_masks
                    safe = connected(unit_masks(h)["tanks"] & (h > FLOOD + 2), team0[0], team1[0])
                    notes.append(f"At high tide tanks can still cross over the causeway: {'yes' if safe else 'NO'}")
                    notes_ok = safe
                else:
                    notes.append("At high tide the fords are closed: the river cannot be crossed by land.")
            else:
                files["mapconfig/lava_config.lua"] = lava_config(1, calm_s=100000, high_s=1, title="lava lake")
                paint = dict(lava=sea)
        what = {"lava tides": "a lava lake whose fords flood every few minutes", "lava": "a lava lake",
                "water": "a deep river"}[mode]
        desc = (f"2v2 river crossing: {what}. {v['fords']} ford{'s' if v['fords'] > 1 else ''}"
                f"{' and a safe causeway' if cause_z is not None else ''} lead across.")
        return Design(hm=h, sym=sym, starts=team0 + team1, teams=[team0, team1], mexes=mexes, geos=geos,
                      biome=biome, title="River Crossing", description=desc,
                      startboxes=west_east_boxes_lua(W, W, team0, team1), paint=paint, extra_files=files,
                      tree_block=ax < LAKE + 700, gates=gates, notes=notes, notes_ok=notes_ok, blocked=blocked)

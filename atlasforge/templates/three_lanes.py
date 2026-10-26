"""Three Lanes: parallel battle corridors separated by ridges with lateral crossings."""
import numpy as np

from ..biomes import BIOMES
from ..checks import connected, unit_masks
from ..design import Design
from ..formats import west_east_boxes_lua
from ..symmetry import Symmetry, mirror_east_west, mirror_pairs
from ..terrain import box_sdf, plateau
from .base import Param, Template
from .common import base_terrain, biome_param, flatten_all, size_param


class ThreeLanesTemplate(Template):
    id = "three_lanes"
    title = "Three Lanes"
    modes = ("1v1", "team")
    tags = ("land", "chokes")
    players = "1v1 to 4v4"
    description = ("Three parallel battle lanes share a rear staging area. Rocky ridges divide the fronts; "
                   "side crossings let armies switch lanes and threaten exposed expansion fields.")
    infos = {
        "ridge_height": "Height of the two rock ridges that divide the map into three lanes, in elmos above the lane floor. Tanks, hovers and bots can only switch lanes at the crossings; spiders climb over. Higher ridges block more line of sight and direct fire between the lanes.",
        "ridge_width": "Width of the flat top of each ridge in elmos. Wide ridges are harder for artillery to shoot across and give spiders and jumpers room to stand on top.",
        "crossing_width": "Width of the openings in the ridges where armies can move from one lane to the next. Narrow crossings make each lane its own battle; wide ones let armies shift quickly to wherever the enemy is weak.",
        "central_crossing": "Adds a crossing in the middle of the map that links all three lanes. It becomes a contested hub: whoever holds it can reinforce any lane quickly.",
        "geovents": "Places one geothermal vent behind each side's front. The general 'Geothermal vents' setting overrides this when it is not set to 'template'.",
    }
    params = (
        size_param((12, 14, 16, 18, 20), 16, adv_smallest=8),
        biome_param("temperate"),
        Param("ridge_height", "Ridge height", "int", 330, min=220, max=480, step=10,
              adv_min=80, adv_max=1000, help="Height of the dividing ridges above the lane floor"),
        Param("ridge_width", "Ridge width", "int", 180, min=100, max=300, step=20,
              adv_min=40, adv_max=800, help="Width of the flat ridge crest in elmos"),
        Param("crossing_width", "Lateral crossing width", "int", 520, min=360, max=800, step=20,
              adv_min=120, adv_max=1800, help="Width of each north-south opening between lanes"),
        Param("central_crossing", "Central lane crossing", "bool", False,
              help="Add a contested connection between all three lanes at the centre"),
        Param("geovents", "Geothermal vents", "bool", True,
              help="Place one geothermal vent behind each side's front"),
    )

    def make(self, v, seed, log=print):
        n = v["size"] * 64 + 1
        W = (n - 1) * 8
        C = W / 2
        rng = np.random.default_rng(seed)
        h, xx, zz, low, edge = base_terrain(n, rng, W, C, sym="ew")
        crossings = [0.28 * W, 0.72 * W]
        if v["central_crossing"]:
            crossings.append(C)
        for z in (0.34 * W, 0.66 * W):
            sdf = box_sdf(xx, zz, C, z, 0.34 * W, v["ridge_width"] / 2)
            for x in crossings:
                sdf = np.maximum(sdf, v["crossing_width"] / 2 + 90 - np.abs(xx - x))
            plateau(h, sdf, 100 + v["ridge_height"] + 5 * low,
                    side_deg=68, noise=edge, amp=12)
        sym = Symmetry("ew", W, W)
        team0 = [(0.10 * W, C)]
        team1 = [sym.mirror(*p) for p in team0]
        # The three resources nearest the start do not depend on expansion settings.
        sx, sz = team0[0]
        west = [(sx - 210, sz - 260, 2.0), (sx - 210, sz + 260, 2.0), (sx + 300, sz, 2.0)]
        # More expansion groups on larger maps; each lane has its own escalation towards mid-map.
        columns = max(3, round(v["size"] / 4))
        for lane, z in enumerate((0.18 * W, C, 0.82 * W)):
            for x in np.linspace(0.19 * W, 0.455 * W, columns):
                dz = float(rng.uniform(-0.018, 0.018) * W)
                value = round(2.0 + 1.1 * (x / C), 2)
                west.append((float(x), z + dz, value))
            west.append((0.36 * W, z - 0.045 * W, 2.5))
        mexes = mirror_pairs(west, sym)
        geos = [(0.13 * W, 0.39 * W), (0.87 * W, 0.39 * W)] if v["geovents"] else []
        h = mirror_east_west(h)
        flatten_all(h, team0 + team1, mexes, geos)
        h = mirror_east_west(h).astype(np.float32)
        gates = [(name, (np.abs(xx - C) < 0.065 * W) & (np.abs(zz - z) < 0.09 * W))
                 for name, z in zip(("North lane", "Middle lane", "South lane"), (0.18 * W, C, 0.82 * W))]
        clear = np.zeros(h.shape, bool)
        for x in crossings:
            clear |= (np.abs(xx - x) < v["crossing_width"] / 2 + 160)
        for _, mask in gates:
            clear |= mask
        # Require each lane independently: an open middle route cannot conceal a broken flank.
        tanks = unit_masks(h)["tanks"]
        lane_ok = [connected(tanks & (np.abs(zz - z) < 0.11 * W),
                             (0.18 * W, z), (0.82 * W, z)) for z in (0.18 * W, C, 0.82 * W)]
        return Design(hm=h, sym=sym, starts=team0 + team1, teams=[team0, team1], mexes=mexes,
                      geos=geos, biome=dict(BIOMES[v["biome"]]), title=self.title,
                      description=self.description,
                      startboxes=west_east_boxes_lua(W, W, team0, team1, depth=0.16 * W),
                      gates=gates, tree_block=clear, keep_clear=clear,
                      notes=[f"Independent tank lane {i + 1}: {'yes' if ok else 'NO'}"
                             for i, ok in enumerate(lane_ok)], notes_ok=all(lane_ok))

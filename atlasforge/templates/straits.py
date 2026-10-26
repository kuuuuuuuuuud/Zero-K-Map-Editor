"""Island Straits: long central islands split the water into named fleet passages."""
import numpy as np

from ..terrain import box_sdf, ellipse_sdf
from .base import Param, Template
from ._naval import finish, islands, naval_params, sea


class IslandStraits(Template):
    id = "straits"
    title = "Island Straits"
    modes = ("1v1", "team")
    tags = ("sea", "chokes")
    players = "1v1 to 3v3"
    description = ("Long central islands split the sea into fleet passages between opposing coastal bases. "
                   "Fight for the straits and use amphibious landings to capture the central islands.")
    infos = {
        "passages": "Number of water passages between the central islands and the map edges. Each passage is a fleet route; fewer passages give heavier naval fights.",
        "passage_width": "Width of each water passage at the waterline, in elmos. Narrow passages are easy to block with ships and coastal defences; wide ones let fleets manoeuvre.",
        "island_width": "East-west width of the central islands in elmos. Wide islands are valuable ground for amphibious landings and long-range defences.",
    }
    params = naval_params() + (
        Param("passages", "Fleet passages", "int", 3, min=2, max=4, step=1,
              adv_min=1, adv_max=7, help="Number of east-west gaps between the central islands and map edges"),
        Param("passage_width", "Passage width", "int", 1100, min=800, max=1500, step=50,
              adv_min=300, adv_max=3000, help="Approximate waterline width in elmos at the default map size"),
        Param("island_width", "Central island width", "int", 1500, min=1000, max=1800, step=100,
              adv_min=400, adv_max=3000, help="East-west width of the central islands in elmos"),
    )

    def make(self, v, seed, log=print):
        h, xx, zz, edge, rng, W = sea(v, seed)
        count = v["passages"]
        scale = W / 8192
        gap = v["passage_width"] * scale
        # Subtract the beach run so the parameter describes water rather than plateau tops.
        shore = 100 / np.tan(np.radians(v["beach_slope"]))
        radius_z = max(24.0, (W / count - gap) / 2 - shore)
        def shapes():
            yield ellipse_sdf(xx, zz, 0.025 * W, 0.5 * W, 0.15 * W, 0.34 * W)
            for k in range(count - 1):
                radius_x = v["island_width"] * scale / 2
                radius = min(radius_x, radius_z)
                yield box_sdf(xx, zz, W / 2, (k + 1) * W / count,
                              radius_x - radius, radius_z - radius) - radius
        islands(h, edge, v, shapes())
        zs = [(k + 0.5) * W / count for k in range(count)]
        gates = [(f"strait {k + 1}", (np.abs(xx - W / 2) < 120 * scale) &
                  (np.abs(zz - z) < W / (2 * count))) for k, z in enumerate(zs)]
        return finish(self, v, h, xx, zz, W, rng, (0.085 * W, 0.5 * W),
                      (0.30 * W, W * (0.5 + (0.5 / count if count % 2 == 0 else 0))), gates)

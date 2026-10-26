"""Seeded canyon corridors form a branching network with deliberate cross routes."""
import numpy as np
from scipy import ndimage
from scipy.interpolate import CubicSpline

from ..noise import smoothstep
from .base import Param, Template
from ._wildlands import build, common_params, described


def _draw_course(mask, points):
    points = np.asarray(points, dtype=np.float32)
    lengths = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    t = np.linspace(0, lengths[-1], max(48, int(lengths[-1] * len(mask) * 2)))
    coords = CubicSpline(lengths, points, axis=0, bc_type="natural")(t)
    grid = np.clip(np.rint(coords * (len(mask) - 1)), 0, len(mask) - 1).astype(int)
    mask[grid[:, 1], grid[:, 0]] = False


def terrain(v, rng, fields):
    _, _, x, z, macro, detail = fields
    n = len(x)
    network = np.ones(x.shape, dtype=bool)
    trunks = []
    count = v["branches"]
    ys = np.linspace(0.20, 0.80, count) + rng.uniform(-0.09, 0.09, count)
    for y in ys:
        wobble = 0.0 if v["form"] == "parallel" else 1.0
        end_y = 0.5 + (y - 0.5) * 0.35 if v["form"] == "fan" else y
        pts = [(0.0, float(end_y)), (0.28, float(y + wobble * rng.uniform(-0.16, 0.16))),
               (0.58, float(y + wobble * rng.uniform(-0.16, 0.16))), (1.0, float(end_y))]
        _draw_course(network, pts)
        if v["form"] == "braided":
            _draw_course(network, [(px, py + 0.025) for px, py in pts])
        trunks.append(pts)
    # Cross connections link neighbouring canyons at selected, seeded junctions.
    for _ in range(v["crossings"]):
        i = int(rng.integers(0, max(1, count - 1)))
        xj = float(rng.uniform(0.28, 0.72))
        y0 = trunks[i][1][1] + (trunks[i][2][1] - trunks[i][1][1]) * ((xj - 0.28) / 0.30)
        y1 = trunks[min(i + 1, count - 1)][1][1] + (trunks[min(i + 1, count - 1)][2][1] - trunks[min(i + 1, count - 1)][1][1]) * ((xj - 0.28) / 0.30)
        _draw_course(network, [(xj, y0), (xj + float(rng.uniform(-0.08, 0.08)), (y0 + y1) / 2), (xj, y1)])
    distance = ndimage.distance_transform_edt(network).astype(np.float32) * (v["size"] * 512 / (n - 1))
    width = v["channel_width"]
    bank = smoothstep(width * 0.35, width * 1.7, distance)
    floor = 28 + 16 * macro
    upland = 135 + 70 * macro
    return (45 + v["relief"] * (floor + bank * (upland - floor) - 45) + 4 * detail).astype(np.float32)


class CanyonNetworkTemplate(Template):
    id = "canyon_network"
    title = "Canyon Network"
    modes = ("1v1", "team")
    tags = ("land", "chokes")
    players = "1v1 to 4v4"
    description = ("A seeded network of branching ravines creates parallel routes, exposed junctions and deliberate cross-canyon passes. "
                   "Each seed reshapes the canyon layout and changes where armies can switch fronts.")
    params = common_params("temperate") + (
        described(Param("form", "Network pattern", "choice", "branching", choices=("branching", "parallel", "fan"),
                        help="Choose irregular, parallel or converging canyon routes"),
                  "Selects the shape of the main canyon routes. Branching bends the routes and connects them at several junctions, parallel keeps them straighter, and fan draws the routes closer together near map edges. For example, parallel gives armies more predictable corridors while branching offers less obvious flanking choices."),
        described(Param("branches", "Main canyons", "int", 4, min=3, max=6, step=1,
                        adv_min=2, adv_max=9, help="Number of long ravines crossing the map"),
                  "Sets how many long ravines divide the map into parallel routes. More canyons create more fronts and shorter distances between high ground. For example, three leaves broad land shelves while six divides armies across narrower corridors."),
        described(Param("crossings", "Cross connections", "int", 3, min=1, max=5, step=1,
                        adv_min=0, adv_max=10, help="Number of links between neighbouring ravines"),
                  "Sets how many passages connect neighbouring canyon routes. More links let tanks and bots change fronts more often and make defence harder to focus. For example, one creates a few predictable transfer points while five gives armies more flanking choices."),
        described(Param("channel_width", "Canyon width", "int", 240, min=160, max=360, step=20,
                        adv_min=80, adv_max=700, help="Width scale of the ravines in elmos"),
                  "Sets the width scale of the ravines in elmos. Wider ravines leave less continuous high ground and make the route network easier to read, while narrow ravines keep more room for base building. For example, 240 makes a medium-width barrier that ground armies must cross at carved passes."),
    )

    def make(self, v, seed, log=print):
        return build(self, v, seed, terrain, log)

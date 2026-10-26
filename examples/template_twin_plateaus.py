"""Twin Plateaus: each side starts on a high plateau with two ramps; open lowland with a rich centre."""
import numpy as np

from atlasforge.biomes import BIOMES
from atlasforge.design import Design
from atlasforge.formats import west_east_boxes_lua
from atlasforge.symmetry import Symmetry, mirror_east_west, mirror_pairs
from atlasforge.terrain import box_sdf, plateau, road
from atlasforge.templates.base import Param, Template
from atlasforge.templates.common import base_terrain, biome_param, flatten_all, size_param


class TwinPlateaus(Template):
    id = "twin_plateaus"
    title = "Twin Plateaus"
    description = ("West vs East. Each side starts on a high plateau reached by two ramps; "
                   "the open lowland between them holds the richest metal.")
    params = (
        size_param((12, 14, 16), 14, adv_smallest=10),
        biome_param("desert"),
        Param("plateau_height", "Plateau height", "int", 220, min=120, max=320, step=10,
              adv_min=60, adv_max=600, help="Elmos above the lowland"),
        Param("ramp_width", "Ramp width", "int", 260, min=180, max=400, step=20,
              adv_min=120, adv_max=800, help="Usable width of each ramp in elmos"),
    )

    def make(self, v, seed, log=print):
        n = v["size"] * 64 + 1
        W = (n - 1) * 8                                   # map width in elmos
        C = W / 2
        rng = np.random.default_rng(seed)                 # the only source of randomness
        h, xx, zz, low, en = base_terrain(n, rng, calm_r=1200, center_x=C, sym="ew")

        # west plateau; the east one comes from the mirror copy below
        top = 100 + v["plateau_height"]
        px0, px1 = 0.0, 0.26 * W
        plateau(h, box_sdf(xx, zz, (px0 + px1) / 2, C, (px1 - px0) / 2, 0.30 * W), top + 6 * low,
                side_deg=70, noise=en, amp=30)
        # two ramps down to the lowland (about 15 degrees, tanks manage 27)
        rlen = v["plateau_height"] / np.tan(np.radians(15))
        for z in (C - 0.18 * W, C + 0.18 * W):
            road(h, (px1 - 120, z), (px1 + rlen, z), v["ramp_width"] / 2, top, 100, down_deg=50, up_deg=30)
        h = mirror_east_west(h)

        team0 = [(0.12 * W, C - 0.12 * W), (0.12 * W, C + 0.12 * W)]
        team1 = [(W - x, z) for x, z in team0]
        west = [(0.07 * W, C - 0.24 * W, 2.0), (0.07 * W, C + 0.24 * W, 2.0), (0.20 * W, C, 2.0),
                (0.36 * W, C - 0.30 * W, 2.4), (0.36 * W, C + 0.30 * W, 2.4), (0.44 * W, C, 3.0)]
        sym = Symmetry("ew", W, W)
        mexes = mirror_pairs(west, sym)
        geos = [(0.40 * W, C - 0.12 * W)]
        geos += [sym.mirror(*g) for g in geos]
        flatten_all(h, team0 + team1, mexes, geos)
        h = mirror_east_west(h).astype(np.float32)        # exact symmetry after flattening

        gates = [(f"ramp {k + 1}", (np.abs(xx - (px1 + rlen / 2)) < rlen / 2 + 200) & (np.abs(zz - z) < 400))
                 for k, z in enumerate((C - 0.18 * W, C + 0.18 * W))]
        desc = ("Twin Plateaus: each side starts on a high plateau with two ramps. "
                "The open lowland between the plateaus holds the richest metal.")
        return Design(hm=h, sym=sym, starts=team0 + team1, teams=[team0, team1], mexes=mexes, geos=geos,
                      biome=BIOMES[v["biome"]], title="Twin Plateaus", description=desc,
                      startboxes=west_east_boxes_lua(W, W, team0, team1, depth=int(0.24 * W)),
                      gates=gates)


if __name__ == "__main__":
    # try it without touching the package:  python examples/template_twin_plateaus.py
    from atlasforge import forge
    from atlasforge.templates import register
    register(TwinPlateaus())
    d = forge.make("twin_plateaus", {}, seed=3)
    ok, lines = forge.check(d)
    print("Check:", "OK" if ok else "PROBLEMS FOUND", *lines, sep="\n  ")
    forge.preview(d).save("twin_plateaus_preview.png")
    print("preview: twin_plateaus_preview.png")

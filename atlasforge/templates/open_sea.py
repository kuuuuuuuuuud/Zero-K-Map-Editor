"""Open Sea: opposing coastal bases, a broad ocean and optional offshore island pairs."""
from .base import Param, Template
from ..terrain import ellipse_sdf
from ._naval import finish, islands, naval_params, sea


class OpenSea(Template):
    id = "open_sea"
    title = "Open Sea"
    modes = ("1v1", "team")
    tags = ("sea",)
    players = "1v1 to 3v3"
    description = ("Coastal bases face a broad ocean with underwater expansion fields. "
                   "Ships control the open water while amphibians and hovers raid the beaches.")
    infos = {
        "coast_size": "Size of the dry coastal base area. Larger coasts give more room to build; smaller ones push players to expand onto the seabed early.",
        "island_pairs": "Number of mirrored islands in the sea. Islands give safe land for expansions and break up the open water into routes for ships.",
    }
    params = naval_params() + (
        Param("coast_size", "Coastal base size", "float", 1.0, min=0.85, max=1.2, step=0.05,
              adv_min=0.6, adv_max=1.6, help="Scales the dry coastal base area"),
        Param("island_pairs", "Offshore island pairs", "int", 1, min=0, max=2, step=1,
              adv_max=5, help="Small mirrored islands away from the central fleet route"),
    )

    def make(self, v, seed, log=print):
        h, xx, zz, edge, rng, W = sea(v, seed)
        count = v["island_pairs"]
        def shapes():
            yield ellipse_sdf(xx, zz, 0.035 * W, 0.5 * W,
                              0.14 * W * v["coast_size"], 0.28 * W * v["coast_size"])
            for k in range(count):
                z = W * (0.14 + 0.72 * k / max(count - 1, 1))
                yield ellipse_sdf(xx, zz, 0.36 * W, z, 0.045 * W, 0.045 * W)
        islands(h, edge, v, shapes())
        return finish(self, v, h, xx, zz, W, rng, (0.085 * W, 0.5 * W), (0.285 * W, 0.5 * W))

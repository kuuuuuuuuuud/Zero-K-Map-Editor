"""Archipelago: paired home islands and staggered stepping stones separated by sea lanes."""
import numpy as np

from .base import Param, Template
from ..terrain import ellipse_sdf
from ._naval import finish, islands, naval_params, sea


class Archipelago(Template):
    id = "archipelago"
    title = "Archipelago"
    modes = ("1v1", "team")
    tags = ("sea",)
    players = "1v1 to 3v3"
    description = ("Home islands and scattered expansion islands divide a deep sea into winding fleet routes. "
                   "Capture island economy with amphibians and defend underwater resources with ships.")
    infos = {
        "island_pairs": "Number of mirrored islands in the sea. Islands give safe land for expansions and break up the open water into routes for ships.",
        "island_size": "Size of the expansion islands. Larger islands narrow the sea lanes between them, which makes fleet battles more cramped.",
        "scatter": "How far the expansion islands are moved away from a regular grid (set by the seed). 0 gives a tidy, predictable layout; 1 a natural, irregular one. The map stays mirrored either way.",
    }
    params = naval_params() + (
        Param("island_pairs", "Expansion island pairs", "int", 3, min=1, max=4, step=1,
              adv_min=0, adv_max=8, help="Number of mirrored expansion islands"),
        Param("island_size", "Expansion island size", "float", 1.0, min=0.7, max=1.2, step=0.05,
              adv_min=0.3, adv_max=2.0, help="Scales expansion islands and narrows surrounding sea lanes"),
        Param("scatter", "Island scatter", "float", 0.7, min=0.0, max=1.0, step=0.1,
              adv_max=2.0, help="Seeded displacement of expansion islands inside their allotted regions"),
    )

    def make(self, v, seed, log=print):
        h, xx, zz, edge, rng, W = sea(v, seed)
        count = v["island_pairs"]
        # Separate rows leave transverse fleet routes between the stepping stones.
        def shapes():
            yield ellipse_sdf(xx, zz, 0.115 * W, 0.5 * W, 0.085 * W, 0.18 * W)
            for k in range(count):
                x = W * (0.38 + 0.015 * np.sin(k * 2.4))
                z = W * (0.14 + 0.72 * (k + 0.5) / max(count, 1))
                jitter = rng.uniform(-0.012, 0.012, 2) * W * v["scatter"]
                r = W * 0.036 * v["island_size"]
                yield ellipse_sdf(xx, zz, x + jitter[0], z + jitter[1], r, r * 1.18)
        islands(h, edge, v, shapes())
        return finish(self, v, h, xx, zz, W, rng, (0.115 * W, 0.5 * W), (0.115 * W, 0.20 * W))

"""Mountain Spine: a seeded ridge separates broad tank valleys from narrow bot passes."""
import numpy as np

from ..noise import smoothstep
from .base import Param, Template
from ._wildlands import build, common_params, described


def terrain(v, rng, fields):
    _, _, x, z, macro, detail = fields
    # Convert the chosen axis into a centerline coordinate. The mirrored map
    # keeps the spine fair while seeded waves make its course visibly change.
    if v["layout"] == "ew":
        cross, along = z, x
    else:
        cross, along = x, z
    frequency = rng.uniform(1.3, 2.4, 4)
    phase = rng.uniform(0, 2 * np.pi, 4)
    bend = (sum(np.sin(along * frequency[i] * 2 * np.pi + phase[i]) * (0.012 / (i + 1))
                for i in range(4)) * v["warp"] if v["form"] == "folded" else 0.0)
    distance = np.abs(cross - (0.5 + bend))
    spine = 1 - smoothstep(v["spine_width"] / (2 * v["size"] * 512),
                          v["spine_width"] / (v["size"] * 512), distance)
    # Regular saddle positions provide two wide tank valleys and several
    # shorter, narrower bot passes. Their locations shift with the seed.
    saddles = np.zeros(4)
    saddles[:] = np.linspace(0.22, 0.78, 4) + rng.uniform(-0.055, 0.055, 4)
    along_distance = np.full(along.shape, np.inf, np.float32)
    for i, pos in enumerate(saddles):
        width = (0.085 if i in (1, 2) else 0.035) * v["pass_width"] / 260
        along_distance = np.minimum(along_distance, np.abs(along - pos))
        cut = np.exp(-((along - pos) / width) ** 2)
        spine *= 1 - (0.88 if i in (1, 2) else 0.58) * cut
    base = 76 + 22 * macro + 4 * detail
    ridge_height = v["relief"] * (250 + 45 * macro)
    return (base + ridge_height * spine).astype(np.float32)


class MountainSpineTemplate(Template):
    id = "mountain_spine"
    title = "Mountain Spine"
    modes = ("1v1", "team")
    tags = ("land", "chokes")
    players = "1v1 to 4v4"
    description = ("A winding mountain ridge divides the battlefield. Tanks use broad low valleys, bots cross shorter passes, "
                   "and spiders can flank over the steep sides; each seed changes the ridge and pass positions.")
    params = common_params("temperate") + (
        described(Param("form", "Ridge course", "choice", "folded", choices=("folded", "straight"),
                        help="Choose a winding or straighter mountain ridge"),
                  "Chooses how much the mountain spine bends across the map. Folded creates a more winding course with changing pass alignments, while straight keeps crossings easier to anticipate. For example, straight makes the front simpler to defend."),
        described(Param("spine_width", "Ridge width", "int", 900, min=600, max=1400, step=100,
                        adv_min=300, adv_max=2400, help="Width of the central mountain ridge in elmos"),
                  "Sets the width of the mountain belt in elmos. A wider ridge lengthens the routes through its passes and gives spiders more flank terrain. For example, 900 leaves a distinct barrier with room for several crossings."),
        described(Param("pass_width", "Pass width", "int", 260, min=180, max=420, step=20,
                        adv_min=100, adv_max=700, help="Width scale for the ridge passes in elmos"),
                  "Sets the width of the crossing valleys in elmos. Wider passes give tanks more room to move and defend; narrower passes favour bots and create stronger choke points. For example, 260 provides medium-width routes through the ridge."),
    )

    def make(self, v, seed, log=print):
        d = build(self, v, seed, terrain, log)
        # Explicit route labels for the gameplay check and automatic blockers.
        n = d.hm.shape[0]
        axis_x = np.linspace(0, 1, n)[None, :]
        axis_z = np.linspace(0, 1, n)[:, None]
        cross = axis_z if v["layout"] == "ew" else axis_x
        along = axis_x if v["layout"] == "ew" else axis_z
        W = v["size"] * 512
        rng = np.random.default_rng(seed)
        positions = np.linspace(0.22, 0.78, 4) + rng.uniform(-0.055, 0.055, 4)
        gates = []
        for i, pos in enumerate(positions):
            width = (0.11 if i in (1, 2) else 0.05) * v["pass_width"] / 260
            mask = (np.abs(along - pos) < width / 2) & (np.abs(cross - 0.5) < 0.20)
            gates.append((("broad tank valley " if i in (1, 2) else "short bot pass ") + str(i + 1), mask))
        d.gates = gates
        return d

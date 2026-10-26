"""Design: everything needed to check, preview and build one map (output of a template)."""
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass
class Design:
    """Everything needed to check, preview and build one map."""
    hm: np.ndarray                         # heightmap (elmos), (nz+1, nx+1)
    sym: Any                               # Symmetry (map size, mirror rule for trees)
    starts: list                           # all start points, in mapinfo team order
    teams: list                            # start points per side, e.g. [[west...], [east...]]
    mexes: list                            # [{x, z, metal, side}]
    geos: list                             # [(x, z)]
    biome: dict
    title: str                             # default map title
    description: str                       # gameplay description (English)
    startboxes: Optional[str] = None       # map_startboxes.lua content (None = from symmetry)
    paint: Optional[dict] = None           # paint layers 0..1
    extra_files: dict = field(default_factory=dict)
    features: list = field(default_factory=list)
    tree_block: Optional[np.ndarray] = None
    keep_clear: Optional[np.ndarray] = None
    random_trees: bool = True
    gates: Optional[list] = None           # [(name, bool mask)] chokes for the check report
    notes: list = field(default_factory=list)          # extra check lines from the template
    notes_ok: bool = True                  # template-specific checks passed
    marks: list = field(default_factory=list)          # preview markers [(x, z, text, rgb)]
    start_colors: Optional[list] = None
    side_labels: tuple = ("your side", "the enemy")
    hazard: Optional[np.ndarray] = None    # bool grid: lava cliffs / damaging ground (preview overlay)
    blocked: Optional[np.ndarray] = None   # bool grid no ground unit survives (lava) - excluded from checks
    movement_profile: str = "land"         # "land" or "naval" (sea maps: ships, hovers, amphibians decide)
    naval_starts: Optional[list] = None    # naval maps: water access points (ports) per side [[(x, z)], [(x, z)]]
    event_zone: Optional[np.ndarray] = None  # bool grid hit by timed events (e.g. lava bombs) - preview only
    event_label: str = ""
    template: Optional[str] = None         # set by forge.make()
    values: dict = field(default_factory=dict)
    seed: int = 1
    rng_state: Optional[dict] = None       # random stream to continue when building (reproducible builds)

    def build_rng(self):
        rng = np.random.default_rng(self.seed + 1)
        if self.rng_state is not None:
            rng.bit_generator.state = dict(self.rng_state)
        return rng

    @property
    def size(self):
        return ((self.hm.shape[1] - 1) // 64, (self.hm.shape[0] - 1) // 64)

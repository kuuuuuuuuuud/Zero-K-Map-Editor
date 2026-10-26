"""Procedural Skirmish: noise terrain in five styles, symmetric resources, ramps carved for tanks."""
from .. import procedural
from .base import Param, Template
from .common import biome_param, size_param


class Skirmish(Template):
    id = "skirmish"
    title = "Procedural Skirmish"
    modes = ("1v1", "team")
    tags = ("land",)
    players = "1v1 to 4v4"
    description = ("Classic 1v1 or team map from noise terrain: hills, plateaus, canyons, islands or craters. "
                   "Ramps are carved automatically so tanks reach every base and metal spot.")
    infos = {
        "style": "The basic shape of the terrain. hills: rolling hills with a few mountains, good all-round maps. plateaus: flat terraces separated by cliffs, ramps lead up; high ground matters. canyon: river valleys cut into high ground, fights happen along the valleys. islands: land masses in shallow water; hovers and amphibians can go everywhere, tanks need the land bridges. crater: impact craters with raised rims that act as natural walls.",
        "layout": "Where the two sides start. diag: north-west against south-east, the longest distance between the bases. ns: north against south. ew: west against east. The map is mirrored so both sides get exactly the same terrain.",
        "relief": "Scales all heights. Below 1.0 the map gets flatter, so long-range units and artillery see further and tanks move more freely. Above 1.0 hills and cliffs get taller, which gives more cover and more ramps, and favours bots and spiders. Ramps are always carved so tanks still reach every base and metal spot.",
    }
    params = (
        size_param((8, 10, 12, 14, 16, 18, 20), 12),
        biome_param("temperate"),
        Param("style", "Terrain style", "choice", "hills", choices=procedural.STYLES,
              help="hills: rolling hills and mountains; plateaus: terraces with cliffs; canyon: river valleys; "
                   "islands: land in water (hovers and amphibians shine); crater: impact craters"),
        Param("layout", "Teams face", "choice", "diag", choices=procedural.LAYOUTS,
              help="diag: north-west vs south-east; ns: north vs south; ew: west vs east"),
        Param("relief", "Relief", "float", 1.0, min=0.5, max=1.6, step=0.1, adv_min=0.1, adv_max=3.0, help="Height scale, 1.0 = default"),
    )

    def make(self, v, seed, log=print):
        s = v["size"]
        return procedural.design((s, s), seed, v["biome"], v["style"], v["layout"], v["relief"],
                                 v.get("mex_count") or None, log)

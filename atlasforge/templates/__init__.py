"""Map templates. Each template declares its parameters and turns them into a Design.

    from atlasforge.templates import all_templates, get
    for t in all_templates():
        print(t.id, t.title)
"""
from .archipelago import Archipelago
from .arena import Arena
from .base import Param, Template
from .chicken import ChickenRings
from .chokepoint import Chokepoint
from .open_sea import OpenSea
from .river import RiverCrossing
from .skirmish import Skirmish
from .straits import IslandStraits
from .volcano import Volcano
from .three_lanes import ThreeLanesTemplate
from .coastal_front import CoastalFrontTemplate
from .atoll import AtollTemplate
from .ffa_ring import FFARing
from .asteroid import Asteroid
from .highlands import HighlandsTemplate
from .watershed import WatershedTemplate
from .dune_sea import DuneSeaTemplate
from .open_dunes import OpenDunesTemplate
from .twin_plateaus import TwinPlateausTemplate
from .lake_district import LakeDistrictTemplate
from .river_delta import RiverDeltaTemplate
from .fjord_coast import FjordCoastTemplate
from .chicken_mesa import ChickenMesaTemplate
from .canyon_network import CanyonNetworkTemplate
from .mountain_spine import MountainSpineTemplate

_REGISTRY = {t.id: t for t in (Skirmish(), Chokepoint(), RiverCrossing(), Arena(), Volcano(), ChickenRings(),
                                OpenSea(), Archipelago(), IslandStraits(), ThreeLanesTemplate(),
                                CoastalFrontTemplate(), AtollTemplate(), FFARing(), Asteroid(), HighlandsTemplate(),
                                WatershedTemplate(), DuneSeaTemplate(), OpenDunesTemplate(), TwinPlateausTemplate(),
                                LakeDistrictTemplate(), RiverDeltaTemplate(), FjordCoastTemplate(),
                                ChickenMesaTemplate(), CanyonNetworkTemplate(), MountainSpineTemplate())}


def all_templates():
    return list(_REGISTRY.values())


def register(template):
    """Add a template at run time (for new templates under development; see docs/TEMPLATE_GUIDE.md)."""
    _REGISTRY[template.id] = template
    return template


def get(template_id):
    try:
        return _REGISTRY[template_id]
    except KeyError:
        raise KeyError(f"unknown template {template_id!r}, expected one of {sorted(_REGISTRY)}") from None


__all__ = ["Param", "Template", "all_templates", "get", "register"]

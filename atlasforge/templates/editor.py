"""Forge Editor blank template: custom even width/height flat sand map for manual terrain work."""
from ..editor import flat_sand_design
from ..surfaces import SURFACE_LABELS, surface_key, surface_label
from .base import Param, Template


class EditorTemplate(Template):
    id = "editor"
    title = "Blank Sand"
    modes = ("1v1",)
    tags = ("land",)
    players = "custom 4x4 to 32x32"
    description = ("A blank flat sand map with a custom width and height. "
                   "Start from a clean slate and paint the terrain by hand.")

    params = (
        Param("width", "Width", "int", 16, min=4, max=32, step=2, even=True, group="Map",
              help="Map width in Spring units (one unit is 512 elmos); even number between 4 and 32",
              info="Width of the map in Spring map units. Must be an even number between 4 and 32. "
                   "The default new-project size is 16 wide by 4 tall."),
        Param("height", "Height", "int", 4, min=4, max=32, step=2, even=True, group="Map",
              help="Map height in Spring units (one unit is 512 elmos); even number between 4 and 32",
              info="Height of the map in Spring map units. Must be an even number between 4 and 32. "
                   "The default new-project size is 16 wide by 4 tall."),
        Param("surface", "Surface Type", "choice", "None (Dry)", choices=SURFACE_LABELS, group="Map",
              help="None (dry), Water, Lava (deadly orange plane), or Void (bottomless pit; a gadget "
                   "kills units that fall off)",
              info="What covers the map below sea level and how the mapinfo.lua water table is written. "
                   "None (Dry) has no water plane. Water adds a standard blue, harmless water plane. "
                   "Lava adds a glowing orange water plane that deals heavy damage to units in it. "
                   "Void (Death Pit) has no water plane but packs a gadget that destroys any unit that "
                   "falls below the map, so a bottomless pit kills without a visible water surface. "
                   "All options are self-contained: the generated map needs no manual mapinfo.lua edits."),
    )

    def all_params(self):
        # A blank editor map has no template-specific resources; only its dimensions and surface.
        return self.params

    def resolve(self, values=None, advanced=False):
        """Defaults + given values. The surface choice accepts both its UI label
        ("Water") and its internal key ("water"), so projects saved by older or
        newer versions of the app always load."""
        values = dict(values or {})
        if "surface" in values:
            values["surface"] = surface_label(values["surface"])
        return super().resolve(values, advanced)

    def make(self, v, seed, log=print):
        return flat_sand_design(v["width"], v["height"], seed=seed, title="New Map",
                                surface=surface_key(v["surface"]), log=log)

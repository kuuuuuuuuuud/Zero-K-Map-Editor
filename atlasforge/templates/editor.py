"""Forge Editor blank template: custom even width/height flat sand map for manual terrain work."""
from ..editor import flat_sand_design
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
    )

    def all_params(self):
        # A blank editor map has no template-specific resources; only its dimensions.
        return self.params

    def make(self, v, seed, log=print):
        return flat_sand_design(v["width"], v["height"], seed=seed, title="New Map", log=log)

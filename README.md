# Zero-K Map Editor (Fork of Atlas Map Forge)

**Author:** Georuku (kuuuuuuuuuud)

## ⚠️ WARNING: UNSTABLE PROJECT
This is a modified fork of [Atlas Map Forge](https://github.com/Scuide/atlas-map-forge). 
It is an **unstable** version. The author has added new functionality for minimal map editing and creation, "polishing" features that were missing in the original. 
Because of these custom additions (custom map sizes, symmetric terrain brushes, undo/redo, AI integration), some original features might be broken or behave unpredictably. Use at your own risk.

## What's New in this Fork?
- **Custom Map Dimensions:** Removed hardcoded square sizes; you can now create any even dimensions (e.g., 16x4, 24x8).
- **Terrain Brush:** A fully functional terrain editing brush with symmetry (EW/NS), shapes (circle/square), and real-time heightmap view.
- **Undo/Redo System:** Added history tracking for terrain modifications.
- **Ramp Tool:** Easily draw straight, symmetrical slopes by clicking two points.
- **AI Integration (DeepInfra):** Added the ability to generate heightmaps and textures via text prompts using DeepInfra's API (SDXL-turbo/FLUX).
- **Custom AI Sandbox:** The "Blank Sand" template allows starting from scratch with a flat, solid-color desert map.
- **Heightmap Persistence:** Projects now save the actual painted terrain (`.npy`) and textures, not just the initial parameters.

## How to use the Fork's Custom Features
To take advantage of the custom map sizes, the symmetric terrain brush, and the AI generation, you MUST select the **Template = Blank Sand** when creating a new map. The original procedural templates (like 8x8 or 16x16) do not support custom dimensions or the terrain brush.

## Featured Map: Castle Defense v2
This project was originally created to build **Castle Defense v2**, the author's first map.
- **Theme:** Inspired by castle defense and siege themes.
- **Vision:** The author enjoys fortress aesthetics and plans to create more "cozy" maps where players can feel protected, comfortable, and genuinely enjoy the defensive (porc) aspect of Zero-K, not just the combat.

## How to Run
1. Install requirements: `pip install -e ".[app]"`
2. Run the app: `python -m atlasforge app`
3. Provide your DeepInfra API key in `.env` for AI texture generation.

## License
This project is licensed under the GNU General Public License v2.0 or later (GPL-2.0-or-later). 
See the `LICENSE` file for details.

# Changelog

## 0.4.22 - first pre-release

- First public pre-release on GitHub (Windows program attached to the release); README download section.
- Defaults: Grass, Rocks and Wrecks now default to 0 and Trees to 0.4 (fewer objects, better in-game FPS).
- App: parameter groups are collapsible (click the group title, state remembered), ordered Map, Resources,
  Terrain, template groups, Advanced; the seed sits directly under Map size.
- Editor checks: a metal spot under water is no longer an error on any map; underwater metal is allowed
  everywhere and reachability is still checked by the check report.
- Check report: traffic-light colours fixed. Errors are red, warnings yellow (badge shows WARNINGS), OK green;
  editor error/warning lines no longer get the green dot.
- Editor: invalid placements (start point, metal spot or geovent in water, on steep ground, ...) now show a
  "!" badge at the object, a tooltip with the reason on hover and a short toast right after the edit.
- Three new templates from the template agent: Chicken Mesa (asymmetric co-op defence around a raised mesa),
  Canyon Network and Mountain Spine (watermark codes 23-25).
- Coastal Front: broad seeded relief on the land, fewer flat areas and a stronger seed effect.
- Editor, stage A (roadmap 0.5): in the app preview, move, add and delete metal spots, geothermal vents and
  start points. Automatic symmetry (mirror and rotation, including free-for-all) applies to every edit.
  Live checks flag water, slope, minimum distances and fairness.
- Editor: undo and redo (Ctrl+Z, Ctrl+Y / Ctrl+Shift+Z).
- Editor: project files (`.forge.json`, versioned) hold the template, settings, seed and edits. Save downloads
  the file in the browser; Open loads one again.
- Editor: changing the seed, size or settings asks for confirmation when manual edits exist ("All manual
  changes will be discarded - continue?").
- Editor: a start point outside its start box is reported as a warning. Templates with their own start box
  Lua string keep their boxes; the start point is not moved.
- Editor: start boxes can be dragged in the preview (drag the inside to move, drag a corner to resize a
  rectangle); undo/redo and `.forge.json` include the box edits.
- Fixed: saving a project now writes the `.forge.json` to the project folder (Settings > Project folder) and
  shows the path with an Open folder button; Open starts in that folder.

## 0.4.0 - unreleased

- Tests: pytest-xdist added to the [test] extras; CI runs the suite in parallel (-n auto).
- New audit tool `tools/terrain_variety.py`: per template and seed, measures the share of flat terrain, the largest flat area and how much the seed changes the heightmap (CSV plus markdown table).
- Eight new templates from the template agent: Procedural Highlands, Procedural Watershed, Procedural Dune
  Sea, Open Dunes, Twin Plateaus, Lake District, River Delta, Fjord Coast (watermark codes 15-22).
- Sea maps (template agent, TPL-naval-fix-1): islands merged smoothly, no hard underwater creases, layout
  quality tests.
- Asteroid: the void below the edge destroys units and buildings (water damage 2000/s), and the space sky
  is visible there (no water plane over the lower half of the sky).
- New template Asteroid (in the style of the Zero-K map Apophis): a cratered rock floating in space with a
  high ring around a basin (or a mesa), rough flanks and an edge that drops into the void; 2 to 4 identical
  sectors, adjustable gravity (watermark code 14). New biome "asteroid" with a starry nebula sky.
- Void maps: `voidwater`, impassable terrain type for space, no shore or water effects, dark minimap and
  preview around the rock; gravity per map.
- Three new biomes: jungle (dense forest, tall grass, moss on rock), swamp (murky water, mud puddles, reeds),
  industrial (steel plate fields with rust, concrete, no trees).
- Every map carries its own painted sky (a panorama the engine turns into a sky box): biome colours,
  clouds, the sun at the right place, stars on the moon; the horizon matches the fog. "Sky: engine" keeps
  Zero-K's default sky.
- Engine grass (SMF vegetation map) on gentle ground for biomes with grass, coloured per biome; new general
  setting "Grass".
- New general setting "Time of day" (morning, noon, afternoon, evening): sun direction and colour in game,
  in the baked ground shading, in the preview and in the sky.
- Free-for-all for 3 to 8 players: rotational symmetry (`RotSymmetry`), one wedge-shaped start box per
  player, checks that every base reaches every other, metal spots, vents, rocks, wrecks, trees and erosion
  identical for every player. New template FFA Ring (watermark code 13); up to 8 player colours in the app.
- Three new templates from the template agent: Three Lanes (land, three lanes with ridges and crossings),
  Coastal Front (mainland front beside a coastal sea) and Atoll (island arcs around a lagoon). Watermark
  codes 10, 11 and 12.
- Sea maps: expansion spots keep at least 6 % of the map width apart; when a sea layout has too little
  room the remaining spots go on the seabed or gentler ground instead of failing the check.
- The window no longer scrolls away when the settings list is longer than the window.
- When a build finishes, a dialog opens in the middle of the window with a short chime: map name, preview,
  size and build time, buttons to show the file or the Zero-K maps folder, and the Ko-fi support button.
- General settings on every map, shown first: Map (size, biome), Resources (number of metal spots per
  side, metal per spot, geothermal vents, wind, tidal strength), Terrain (trees, rocks, wrecks, erosion),
  then the template's own settings. Metal spots and vents are added or removed in mirrored sets; base
  spots stay.
- Every setting has an info button with a full explanation (what it does, unit, effect in a game, range
  and advanced range).
- Template picker for many templates: the current template is a compact card; "Change" (or key T) opens
  a gallery with search and filters for 1v1, Teams, FFA, Co-op and for Land, Sea, Twists, Chokes.
  Templates declare `modes`, `tags` and `players`.
- Sea maps: metal spots spread evenly (no rows along the map edge or pairs at the centre line), richer
  further from the base, land spots prefer islands other than the home island.
- Three sea templates (built from the template guide): Open Sea, Archipelago, Island Straits. Naval check
  profile: ships between the ports, hovers and amphibians between the bases, amphibian access to all metal,
  ships to underwater metal; "Ships" route in the app.
- Ko-fi support: button in the app, a short note after every finished build and after command line builds.
- A map that was built but could not be installed (Zero-K folder unknown) is shown as built with a warning.
- Rocks and crystals: every map carries its own procedural 3D models (.s3o) and feature definitions;
  rock clusters gather at slopes, glowing crystals on alien and moon maps; all reclaimable.
- Battlefield wrecks of Zero-K units between the bases (reclaimable metal). New general settings "Rocks"
  and "Wrecks"; the check report lists the reclaim metal; the app shows them (layer "Features").
- Textures: snow only on gentle slopes with rocks poking through, sediment bands, light rims and dark
  cracks on rock, scree at the foot of cliffs, wet sand and foam at the water line, shallow water
  gradient, driven paths on carved ramps.
- Faster previews (noise and masks computed separably, about 2x faster overall).
- Hidden watermark in every map: a keyed pattern over the heightmap (about 0.04 elmos, invisible) plus a
  record in the lowest height bits (tool version, template, seed, build date, build id). `atlasforge verify
  map.sdz` and "Check a map file" in the app's Settings tell whether a map was made with Atlas Map Forge.
  Tested against 353 Zero-K maps (no false alarm) and after re-packing, smoothing, re-quantising and
  local edits of the heightmap.
- Advanced mode (Settings, with a warning): lifts the limits of every map setting - sizes 4-32, more
  gates/fords/rings, extreme heights and timings. Values beyond the safe range are shown in orange.
- Erosion: simulated rain carves gullies and valleys into natural slopes; start areas, metal spots,
  chokes, walls and ramps are protected. If erosion would cut a route, it is lowered automatically.
- Seamless symmetry: the noise is made symmetric with a blend at the dividing line before anything is
  built on it, so mirrored maps no longer show a crease along the centre (River, Arena, Chokepoint,
  Volcano, procedural maps).
- Ramps carved by the procedural generator no longer leave fans of radial streaks at tight bends.

## 0.3.1 - merged into 0.4.0

- Every map carries the `Forge` name prefix, the FORGE badge and the credit line; these are no longer
  settings. The author name is the only setting and is required to build (app and command line).
- The app asks for the author name on the first start; "Build map" stays disabled without it.
- Volcano: lava bombs only hit solid ground on the volcano island and the ring (precomputed spots, never in
  the lava), bigger impacts (new setting "Lava bomb size", default radius 320 instead of 170) with more
  splash effects; bomb zones shown in the app (Danger layer, amber).

## 0.3.0 - 2026-10-21

- The app (`atlasforge app`, Windows program `AtlasMapForge.exe`): template gallery, controls built from
  the template parameters, seed dice, automatic preview.
- Large zoomable map preview: metal spots with values, geovents, start points and start boxes, chokes,
  dangerous ground, grid, and "Where can it go?" per unit class; height and passable unit classes under
  the mouse.
- Check report, map facts, Build & install with progress, existing map versions detected (next free
  version suggested), "Show file".
- Settings in the app: author, prefix, badge, credit line, Zero-K folder, output folder.
- Windows build with PyInstaller and a self-test of the packed program (`--selftest --build`).

## 0.2.0 - unreleased

- Six map templates with declared parameters: Procedural Skirmish, Chokepoint Front, River Crossing,
  Arena (4 players), Volcano, Chicken Defense.
- Pipeline `atlasforge.forge`: design, plain-English check report, quick preview (about 1 second), build.
- Commands `templates`, `preview`, `build` with `--set key=value`.
- Check report knows about lava (ground nobody survives) and template-specific checks.
- Chicken zones gadget keeps chicken roosts out of the player area.

## 0.1.0 - unreleased

- First package version: procedural skirmish maps from the command line.
- Map gadgets: lava cliffs, lava tide warning, volcano eruption (used by templates later).
- Settings for author, name prefix and FORGE badge; maps credit "Made with Atlas Map Forge."
- Install into Zero-K with lobby minimap and thumbnail.

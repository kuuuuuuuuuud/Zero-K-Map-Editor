# Roadmap

Features first, balance tools after them.

## 0.1 - foundation (done)

Generator core, command line, user settings, Windows and Linux, automatic tests.

## 0.2 - templates (done)

Six templates with declared parameters, quick preview, plain-English check report.

## 0.3 - Windows app (done)

Local web interface in its own window: template gallery, large zoomable preview with overlays, check
report, build & install with progress. One-file Windows program built and self-tested on GitHub.

## 0.4 - terrain quality and control (done)

- Done: seamless symmetry, erosion, smoother ramps, advanced mode, hidden watermark with `atlasforge
  verify`, fixed Forge prefix and badge, author required, textures (snow, rock, scree, shore, paths),
  rocks, crystals and Zero-K wrecks (reclaim), template picker with filters, general settings on every map
  (metal spots, metal per spot, geothermal vents, wind, tidal, trees, rocks, wrecks, erosion) with an info
  popup for every setting, build-finished dialog.
- Done: more biomes (jungle, swamp, industrial), a painted sky per map, engine grass, time of day.
- Done: parameter groups collapse and keep their state; Map, Resources, Terrain, then the rest; seed under Map size.

## 0.5 - map editing (in progress)

In progress: stage A (placement, undo/redo, .forge.json).

Edit Forge maps by hand, in three stages, always keeping the symmetry and re-running the checks:

- Done: A - placement: move, add and delete metal spots, geothermal vents and start points in the preview;
  automatic symmetry (mirror and rotation, including free-for-all); live checks (water, slope, distances,
  fairness) with a badge, tooltip and toast at invalid objects; undo/redo; versioned project file (`.forge.json`: template, settings, seed, list of edits)
  saved and opened in the browser; confirmation before manual edits are discarded when the seed, size or
  settings change.
- Done: A - start boxes on every map: move and resize start boxes in the preview (also for templates with
  their own boxes), with symmetry, live checks (start point inside its box, boxes must not overlap), undo/redo,
  saved in `.forge.json` and written to the built map.
- Next: B - terrain brushes: raise, lower, flatten, smooth, draw a ramp from A to B.
- Later: C - painting and objects: paths, concrete, scorch, lava; place or remove trees and rocks; optional
  16-bit PNG heightmap import/export.

## More ways to play and more templates

- Done: free-for-all for 3 to 8 players (rotational symmetry, one start box per player, FFA Ring template).
  Open: naval free-for-all with several ports.
- Team games 2v2 to 5v5 with several start points per box.
- Done: sea templates (Open Sea, Archipelago, Island Straits, Coastal Front, Atoll) with a naval check
  profile; Three Lanes.
- Done: smoother underwater transitions on sea maps (naval fix, integrated); templates Open Dunes, Twin
  Plateaus, Lake District, River Delta, Fjord Coast, Highlands, Watershed, Dune Sea and Asteroid (in the
  style of Apophis); gallery fix and new sea map thumbnails.
- Done: templates Chicken Mesa (asymmetric co-op), Canyon Network and Mountain Spine; first terrain variety
  pass (Coastal Front: fewer flat areas, the seed changes the relief more).
- In progress: more terrain variety in the other existing templates.
- Next templates: King of the Hill, Fortress Front, Crater Basin, Inland Sea, Island Continents, Peninsula,
  Team Battlefront, Chicken Three Fronts, City Grid.

## 0.6 - twists (map gadgets)

- Meteor showers, control points with bonuses, crumbling passes, supply drops, day and night, siege.

## 0.7 - balance and testing

- Fairness check: travel times per unit class to metal, centre and enemy, metal per side, high ground.
- Metal layout in expansion stages; metal total by map size.
- "Test in Zero-K": start the map against the AI from the app; AI-vs-AI quick run with a short report.
- Map values: gravity, extractor radius (wind and tidal are done).

## App and distribution (alongside)

- Later: Windows program attached to GitHub Releases as a direct download, code-signed through the SignPath
  Foundation (signing inside the GitHub Actions build).
- Map codes (template + settings + seed as short text) to share and paste; compare two seeds side by side.
- Start-up time of the one-file program, update notice.
- Upload helper for zero-k.info, name collision check.
- In progress: terrain variety check tool (flat-area share, seed influence).

## 1.0 - release

Quick-start guide with pictures, template gallery, talk to the Zero-K moderators before announcing.

## Later

- Beyond All Reason (BAR) profile: metal map values, BAR movement rules for the checks, start boxes for
  BAR's map database, BAR wrecks, lava through BAR's `mapconfig/lava.lua`, a game switch in the app.
- Online configurator with preview; in-game generation from a seed.

# TPL-series-2-1: Open Dunes

## Design

Broad low wind dunes with open basins and scattered rocky cover.
A low-amplitude wind field with interrupted crests; unlike Dune Sea, its default terrain favours open manoeuvring rather than tall dune barriers.
Players: 1v1 to 4v4. Modes: ('1v1', 'team'). Tags: ('land',).
Broad valleys and basins, with existing procedural ramp carving to ensure tank access.
Automatic mirrored economy with three protected opening spots per side; general mex/geo controls supply adjustments.

## Integration

Base: CORE-20261022-1930 plus the published FFA 2000, biome/sky/grass 2030 and UI 2045 packages. Imported Core sources are preserved; these tickets add only their selected template, tests, brief, handoff and thumbnail files.
Dependency: TPL-highlands-1 (_wildlands.py only).
Class: OpenDunesTemplate from atlasforge.templates.open_dunes; template ID open_dunes.
The Core owner alone registers the class and assigns its final watermark ID. Registry, watermark and existing shared Core files are excluded from this patch.
TPL-series-2-5 includes the cross-family environment test and requires all five template sources. Apply tickets 1 through 5 in order after their documented helper prerequisites.

## Parameters

| Key | Default | Safe | Advanced | Player explanation |
|---|---|---|---|---|
| `size` | `12` | (8, 10, 12, 14, 16, 18, 20) | (8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32) | Sets the square map width in Spring map units, each equal to 512 elmos. Larger maps provide more expansion space and longer travel distances. For example, size 12 is a compact match while size 20 gives teams more room. |
| `biome` | `desert` | ('alien', 'arctic', 'ashland', 'autumn', 'desert', 'industrial', 'jungle', 'moon', 'swamp', 'temperate', 'volcanic') | ('alien', 'arctic', 'ashland', 'autumn', 'desert', 'industrial', 'jungle', 'moon', 'swamp', 'temperate', 'volcanic') | Changes terrain colours, vegetation, lighting and the sky. The terrain family and seed still determine the geography. For example, Arctic gives the same landforms a cold appearance. |
| `layout` | `diag` | ('diag', 'ns', 'ew') | ('diag', 'ns', 'ew') | Sets the opposing base orientation and the corresponding terrain symmetry. Both sides receive mirrored resources and equal starting terrain. For example, diag places opponents in the northwest and southeast. |
| `relief` | `1.0` | (0.5, 1.6) | (0.1, 3.0) | Multiplies the elevation differences, with 1.0 as the standard height scale. Higher terrain creates stronger high-ground positions and can require additional tank ramps. For example, 0.5 halves the relief without selecting a different seed. |
| `warp` | `1.0` | (0.3, 1.5) | (0.0, 3.0) | Scales the displacement of the underlying terrain pattern. Higher values bend ridges, basins and region boundaries into more irregular shapes. For example, zero leaves an orderly underlying pattern while 1.0 uses normal distortion. |
| `dune_direction` | `seeded` | ('seeded', 'east', 'northeast', 'north') | ('seeded', 'east', 'northeast', 'north') | Sets the direction of the wind-shaped dune bands before team symmetry. Seeded chooses a new angle for each seed; the named directions use a fixed compass angle. For example, north aligns the bands across north-south travel and changes how armies approach each crest. |
| `dune_height` | `55` | (25, 90) | (10, 240) | Sets the dune height scale in elmos before applying Relief. Low values keep the battlefield open, while higher values create more useful cover and height advantages. For example, 55 makes gentle dunes and 25 produces an almost flat sand plain. |
| `wavelength` | `1400` | (900, 2200) | (400, 4000) | Sets the approximate distance between dune crests in elmos before distortion. Wider spacing gives armies longer open approaches; close spacing creates more frequent changes in line of sight. For example, 1400 leaves broad manoeuvring valleys between the dunes. |
| `outcrops` | `0.3` | (0, 1) | (0, 3) | Scales the small rocky landforms within the sand field. These interrupt sight lines and shelter local positions without creating a map-wide wall. For example, zero removes rocky terrain, while 1.0 uses the full standard outcrop height; reclaim rocks have their own general setting. |

The common mex, metal, geo, wind, tidal, sun, sky, grass, trees, rocks, wrecks and erosion controls come from the Core; settings.json includes every setting and its English info text. Opening metal sites carry fixed=True. No private count controls are added.

## Checks

Complete regression suite: 463 passed, 3 deselected in 1270.20s (0:21:10); local HTTP app tests: 3 passed.
Fresh published Core integration smoke: 65 passed, 63 deselected. This selects player-facing metadata/previews, family-specific rules and common-resource/environment combinations; default-seed and exhaustive parameter tests are covered by the full regression and matrix.
Full matrix: 88 cases, zero generation errors. All default seeds 1-10 and tested safe settings are playable. Advanced-only gameplay failures: none tested.
Design timing at minimum and maximum safe sizes (seconds): [{'size': 8, 'seconds': 0.107}, {'size': 20, 'seconds': 0.856}].
Controls tested include mex_count 6/20 and geos 0/3, plus Jungle/Swamp/Industrial with morning/evening/noon, painted/engine sky and grass 0/1/2. Every setting is explained and parameter keys are unique.

### Default seeds 1-5

Seed 1: PASS
```text
Tanks       can reach the enemy: yes
Bots        can reach the enemy: yes
Spiders     can reach the enemy: yes
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Metal spots unreachable for tanks: 0 of 38
Procedural terrain family: open_dunes; form: open dunes
Unreachable expansion pairs removed after ramp carving: 0
Protected opening spots: 6
Reclaim per side: 290 metal in rocks, 496 metal in wrecks
```

Seed 2: PASS
```text
Tanks       can reach the enemy: yes
Bots        can reach the enemy: yes
Spiders     can reach the enemy: yes
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Metal spots unreachable for tanks: 0 of 38
Procedural terrain family: open_dunes; form: open dunes
Unreachable expansion pairs removed after ramp carving: 0
Protected opening spots: 6
Reclaim per side: 248 metal in rocks, 268 metal in wrecks
```

Seed 3: PASS
```text
Tanks       can reach the enemy: yes
Bots        can reach the enemy: yes
Spiders     can reach the enemy: yes
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Metal spots unreachable for tanks: 0 of 38
Procedural terrain family: open_dunes; form: open dunes
Unreachable expansion pairs removed after ramp carving: 0
Protected opening spots: 6
Reclaim per side: 325 metal in rocks, 680 metal in wrecks
```

Seed 4: PASS
```text
Tanks       can reach the enemy: yes
Bots        can reach the enemy: yes
Spiders     can reach the enemy: yes
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Metal spots unreachable for tanks: 0 of 38
Procedural terrain family: open_dunes; form: open dunes
Unreachable expansion pairs removed after ramp carving: 0
Protected opening spots: 6
Reclaim per side: 263 metal in rocks, 544 metal in wrecks
```

Seed 5: PASS
```text
Tanks       can reach the enemy: yes
Bots        can reach the enemy: yes
Spiders     can reach the enemy: yes
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Metal spots unreachable for tanks: 0 of 38
Procedural terrain family: open_dunes; form: open dunes
Unreachable expansion pairs removed after ramp carving: 0
Protected opening spots: 6
Reclaim per side: 311 metal in rocks, 370 metal in wrecks
```

## Visual review and export

All ten default-seed previews and an enlarged default preview inspected. Seed 1/default and seed 7/configured variant inspected together in series2_variants.png. Fjord Coast additionally has native 1:1 height-shaded coast/seam crops; one pixel is one 8-elmo height sample.
Source briefs record visual_review=true after inspection. The embedded brief in a report can precede that flag update; original reports and fingerprints are not rewritten.
Real prototype: Forge_Open_Dunes_v1.sdz, size [8, 8], seed 1, 24603646 bytes. ZIP integrity, SMF/SMT, painted sky and Forge watermark verified. SMF grass extra-header count: 1.
Prototype watermark uses the existing reserved unknown code 255. No final template IDs were allocated. Rebuild after Core registration for a release.
No map has been loaded or played in Zero-K. Live balance and visual checks in the engine remain open.

## Limits and Core wishes

- No live Zero-K playtest.
- Advanced short spacing combined with high relief can create steep terrain.
- Uses the unchanged _wildlands.py helper from the delivered TPL-highlands-1 ticket.

## Reproduction

python -m pytest tests/test_template_open_dunes.py
python -m tools.template_workflow check open_dunes --level full
python -m pytest tests  # scope collection to tests, excluding unpacked output copies

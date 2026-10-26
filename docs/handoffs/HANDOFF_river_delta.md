# TPL-series-2-4: River Delta

## Design

A distributary fan with several crossing fronts and contested delta islands.
An explicit connected river graph that widens into delta islands, with planned wading or dry crossing corridors; not the Watershed drainage-noise family.
Players: 1v1 to 4v4. Modes: ('1v1', 'team'). Tags: ('land', 'chokes').
Two to four reserved east-west crossing corridors span all river arms; amphibians can bypass the crossings.
Mirrored land economy on mainland and delta islands; three fixed opening spots per side, general mex and geo controls.

## Integration

Base: CORE-20261022-1930 plus the published FFA 2000, biome/sky/grass 2030 and UI 2045 packages. Imported Core sources are preserved; these tickets add only their selected template, tests, brief, handoff and thumbnail files.
Dependency: TPL-highlands-1 (_wildlands.py only).
Class: RiverDeltaTemplate from atlasforge.templates.river_delta; template ID river_delta.
The Core owner alone registers the class and assigns its final watermark ID. Registry, watermark and existing shared Core files are excluded from this patch.
TPL-series-2-5 includes the cross-family environment test and requires all five template sources. Apply tickets 1 through 5 in order after their documented helper prerequisites.

## Parameters

| Key | Default | Safe | Advanced | Player explanation |
|---|---|---|---|---|
| `size` | `12` | (8, 10, 12, 14, 16, 18, 20) | (8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32) | Sets the square map width in Spring map units, each equal to 512 elmos. Larger maps provide more expansion space and longer travel distances. For example, size 12 is a compact match while size 20 gives teams more room. |
| `biome` | `temperate` | ('alien', 'arctic', 'ashland', 'autumn', 'desert', 'industrial', 'jungle', 'moon', 'swamp', 'temperate', 'volcanic') | ('alien', 'arctic', 'ashland', 'autumn', 'desert', 'industrial', 'jungle', 'moon', 'swamp', 'temperate', 'volcanic') | Changes terrain colours, vegetation, lighting and the sky. The terrain family and seed still determine the geography. For example, Arctic gives the same landforms a cold appearance. |
| `relief` | `1.0` | (0.5, 1.6) | (0.1, 3.0) | Multiplies the elevation differences, with 1.0 as the standard height scale. Higher terrain creates stronger high-ground positions and can require additional tank ramps. For example, 0.5 halves the relief without selecting a different seed. |
| `warp` | `1.0` | (0.3, 1.5) | (0.0, 3.0) | Scales the displacement of the underlying terrain pattern. Higher values bend ridges, basins and region boundaries into more irregular shapes. For example, zero leaves an orderly underlying pattern while 1.0 uses normal distortion. |
| `branches` | `3` | (3, 5) | (2, 9) | Sets how many river arms spread out from the upstream channel. More arms create more delta islands and more local water crossings. For example, three gives a simple fan, while five divides the delta into smaller contested pieces. |
| `fan_spread` | `0.3` | (0.22, 0.36) | (0.12, 0.43) | Sets how far the outer river arms spread from the centre, as a fraction of map width. A wide delta leaves more islands between the arms and brings water closer to the flanks. For example, 0.30 creates a broad fan while 0.22 concentrates the fighting near the middle. |
| `channel_width` | `500` | (350, 750) | (150, 1600) | Sets the approximate width of each arm at the water surface in elmos. Wider arms strengthen amphibious flanking and leave less dry island space; confluences are wider than individual arms. For example, 500 creates medium channels with room for shoreline fights. |
| `channel_depth` | `36` | (20, 70) | (5, 160) | Sets the maximum channel depth in elmos below water before applying Relief. Deeper channels keep tanks on the crossing routes and make amphibious access more valuable. For example, 36 blocks ordinary tank travel through the main arms; narrow arms can be shallower than the maximum depth. |
| `crossings` | `3` | (2, 4) | (1, 7) | Sets the number of planned crossing corridors spanning the river arms. More crossings spread the front and let armies switch between more approaches. For example, three offers northern, central and southern routes through the delta. |
| `crossing_width` | `240` | (180, 400) | (80, 900) | Sets the flat core width of each crossing in elmos. Wide crossings are harder to seal with a few units and reduce traffic problems for large armies. For example, 240 is a medium front while 400 gives a broad approach. |
| `crossing_type` | `fords` | ('fords', 'causeways') | ('fords', 'causeways') | Chooses the height of the planned crossings. Fords are shallow water routes for land armies, while causeways rise above water and provide dry connections. For example, causeways give tanks and bots dry approaches through the river arms. |

The common mex, metal, geo, wind, tidal, sun, sky, grass, trees, rocks, wrecks and erosion controls come from the Core; settings.json includes every setting and its English info text. Opening metal sites carry fixed=True. No private count controls are added.

## Checks

Complete regression suite: 463 passed, 3 deselected in 1270.20s (0:21:10); local HTTP app tests: 3 passed.
Fresh published Core integration smoke: 65 passed, 63 deselected. This selects player-facing metadata/previews, family-specific rules and common-resource/environment combinations; default-seed and exhaustive parameter tests are covered by the full regression and matrix.
Full matrix: 90 cases, zero generation errors. All default seeds 1-10 and tested safe settings are playable. Advanced-only gameplay failures: none tested.
Design timing at minimum and maximum safe sizes (seconds): [{'size': 8, 'seconds': 0.22}, {'size': 20, 'seconds': 1.101}].
Controls tested include mex_count 6/20 and geos 0/3, plus Jungle/Swamp/Industrial with morning/evening/noon, painted/engine sky and grass 0/1/2. Every setting is explained and parameter keys are unique.

### Default seeds 1-5

Seed 1: PASS
```text
Tanks       can reach the enemy: yes, only through: Delta crossing 2
Bots        can reach the enemy: yes, only through: Delta crossing 2
Spiders     can reach the enemy: yes, only through: Delta crossing 2
Amphibians  can reach the enemy: yes, only through: Delta crossing 2
Hovers      can reach the enemy: yes, only through: Delta crossing 2
Metal spots unreachable for tanks: 0 of 38
Procedural terrain family: river_delta; form: river delta
Unreachable expansion pairs removed after ramp carving: 0
Protected opening spots: 6
Planned delta crossing corridors: 3 (fords)
Reclaim per side: 208 metal in rocks, 232 metal in wrecks
```

Seed 2: PASS
```text
Tanks       can reach the enemy: yes, only through: Delta crossing 2
Bots        can reach the enemy: yes, only through: Delta crossing 2
Spiders     can reach the enemy: yes, only through: Delta crossing 2
Amphibians  can reach the enemy: yes, only through: Delta crossing 2
Hovers      can reach the enemy: yes, only through: Delta crossing 2
Metal spots unreachable for tanks: 0 of 38
Procedural terrain family: river_delta; form: river delta
Unreachable expansion pairs removed after ramp carving: 0
Protected opening spots: 6
Planned delta crossing corridors: 3 (fords)
Reclaim per side: 258 metal in rocks, 268 metal in wrecks
```

Seed 3: PASS
```text
Tanks       can reach the enemy: yes, only through: Delta crossing 2
Bots        can reach the enemy: yes, only through: Delta crossing 2
Spiders     can reach the enemy: yes, only through: Delta crossing 2
Amphibians  can reach the enemy: yes, only through: Delta crossing 2
Hovers      can reach the enemy: yes, only through: Delta crossing 2
Metal spots unreachable for tanks: 0 of 38
Procedural terrain family: river_delta; form: river delta
Unreachable expansion pairs removed after ramp carving: 0
Protected opening spots: 6
Planned delta crossing corridors: 3 (fords)
Reclaim per side: 169 metal in rocks, 292 metal in wrecks
```

Seed 4: PASS
```text
Tanks       can reach the enemy: yes, only through: Delta crossing 2
Bots        can reach the enemy: yes, only through: Delta crossing 2
Spiders     can reach the enemy: yes, only through: Delta crossing 2
Amphibians  can reach the enemy: yes, only through: Delta crossing 2
Hovers      can reach the enemy: yes, only through: Delta crossing 2
Metal spots unreachable for tanks: 0 of 38
Procedural terrain family: river_delta; form: river delta
Unreachable expansion pairs removed after ramp carving: 0
Protected opening spots: 6
Planned delta crossing corridors: 3 (fords)
Reclaim per side: 244 metal in rocks, 368 metal in wrecks
```

Seed 5: PASS
```text
Tanks       can reach the enemy: yes, only through: Delta crossing 2
Bots        can reach the enemy: yes, only through: Delta crossing 2
Spiders     can reach the enemy: yes, only through: Delta crossing 2
Amphibians  can reach the enemy: yes, only through: Delta crossing 2
Hovers      can reach the enemy: yes, only through: Delta crossing 2
Metal spots unreachable for tanks: 0 of 38
Procedural terrain family: river_delta; form: river delta
Unreachable expansion pairs removed after ramp carving: 0
Protected opening spots: 6
Planned delta crossing corridors: 3 (fords)
Reclaim per side: 257 metal in rocks, 126 metal in wrecks
```

## Visual review and export

All ten default-seed previews and an enlarged default preview inspected. Seed 1/default and seed 7/configured variant inspected together in series2_variants.png. Fjord Coast additionally has native 1:1 height-shaded coast/seam crops; one pixel is one 8-elmo height sample.
Source briefs record visual_review=true after inspection. The embedded brief in a report can precede that flag update; original reports and fingerprints are not rewritten.
Real prototype: Forge_River_Delta_v1.sdz, size [8, 8], seed 1, 25921892 bytes. ZIP integrity, SMF/SMT, painted sky and Forge watermark verified. SMF grass extra-header count: 1.
Prototype watermark uses the existing reserved unknown code 255. No final template IDs were allocated. Rebuild after Core registration for a release.
No map has been loaded or played in Zero-K. Live balance and visual checks in the engine remain open.

## Limits and Core wishes

- No live Zero-K playtest.
- Advanced crowding can merge arms and sacrifice island space.
- Land validation profile; no promised fleet route through fords.
- Requires the unchanged _wildlands.py helper from TPL-highlands-1.

## Reproduction

python -m pytest tests/test_template_river_delta.py
python -m tools.template_workflow check river_delta --level full
python -m pytest tests  # scope collection to tests, excluding unpacked output copies

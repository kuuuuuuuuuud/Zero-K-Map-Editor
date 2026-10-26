# TPL-series-2-5: Fjord Coast

## Design

Deep inlets in mirrored mainlands with a protected home headland, bay mouths and a shared fleet front.
Mainland-indenting fjords and sheltered inlet fronts rather than offshore island obstacles.
Players: 1v1 to 4v4. Modes: ('1v1', 'team'). Tags: ('sea', 'chokes').
Explicit ports, common fleet front, ship access to each inlet, and amphibious access from home bases.
Shared naval distribution with fixed opening spots, seabed expansions and general mex/geo controls.

## Integration

Base: CORE-20261022-1930 plus the published FFA 2000, biome/sky/grass 2030 and UI 2045 packages. Imported Core sources are preserved; these tickets add only their selected template, tests, brief, handoff and thumbnail files.
Dependency: TPL-naval-fix-1 (_naval.islands / finish helpers).
Class: FjordCoastTemplate from atlasforge.templates.fjord_coast; template ID fjord_coast.
The Core owner alone registers the class and assigns its final watermark ID. Registry, watermark and existing shared Core files are excluded from this patch.
TPL-series-2-5 includes the cross-family environment test and requires all five template sources. Apply tickets 1 through 5 in order after their documented helper prerequisites.

## Parameters

| Key | Default | Safe | Advanced | Player explanation |
|---|---|---|---|---|
| `size` | `16` | (12, 14, 16, 18, 20) | (8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32) | Width and height of the map in Spring map units; one unit is 512 elmos (a small tank is about 30 elmos long). 8x8 suits a fast 1v1, 12-16 a 2v2 or 3v3, 20 and more large team games. Bigger maps take longer to build, need more metal spots to stay interesting and make travel times (and raids) longer. |
| `biome` | `temperate` | ('alien', 'arctic', 'ashland', 'autumn', 'desert', 'industrial', 'jungle', 'moon', 'swamp', 'temperate', 'volcanic') | ('alien', 'arctic', 'ashland', 'autumn', 'desert', 'industrial', 'jungle', 'moon', 'swamp', 'temperate', 'volcanic') | The look of the map: ground colours and textures, sky, sun, water colour, trees, grass and the usual wind. It does not change the shape of the terrain. jungle: dense forest and tall grass; swamp: murky water, mud puddles and reeds; industrial: steel plates and concrete, no trees. Desert, moon, alien, volcanic and ashland have no trees, and the moon has almost no wind. |
| `depth` | `180` | (100, 320) | (40, 600) | Depth of the open sea in elmos below the water surface. Ships need more than 15 elmos; submarines are hidden better in deep water. Shallow seas (100) let amphibians walk across quickly; deep seas (300) keep the ocean a ship's world. |
| `beach_slope` | `14` | (10, 18) | (5, 40) | Steepness of the beaches in degrees between the seabed and the dry land. Tanks and hovers can drive up to about 27 degrees, so gentle beaches (10) make landings easy; steep ones (18) slow down amphibious attacks. |
| `coast_noise` | `55` | (0, 100) | (0, 250) | How irregular the coastlines are, in elmos. 0 gives smooth coasts; 100 gives bays and capes that offer cover and landing spots. |
| `sea_metal` | `0.65` | (0.3, 0.8) | (0.0, 1.0) | Share of the expansion metal spots that lie on the seabed instead of on land. Underwater spots can be taken by amphibious builders and naval constructors and are defended with ships and torpedo turrets. 0.3 keeps most metal on land, 0.8 makes the sea the main economy. |
| `geovents` | `True` | (None, None) | (None, None) | Adds one geothermal vent in each home base. The general 'Geothermal vents' setting overrides this when it is not set to 'template'. |
| `fjords` | `2` | (2, 4) | (1, 7) |  |
| `fjord_reach` | `900` | (600, 1200) | (250, 2200) |  |
| `fjord_width` | `1000` | (800, 1400) | (400, 2400) |  |
| `coast_depth` | `0.28` | (0.24, 0.3) | (0.18, 0.38) |  |

The common mex, metal, geo, wind, tidal, sun, sky, grass, trees, rocks, wrecks and erosion controls come from the Core; settings.json includes every setting and its English info text. Opening metal sites carry fixed=True. No private count controls are added.

## Checks

Complete regression suite: 463 passed, 3 deselected in 1270.20s (0:21:10); local HTTP app tests: 3 passed.
Fresh published Core integration smoke: 65 passed, 63 deselected. This selects player-facing metadata/previews, family-specific rules and common-resource/environment combinations; default-seed and exhaustive parameter tests are covered by the full regression and matrix.
Full matrix: 88 cases, zero generation errors. All default seeds 1-10 and tested safe settings are playable. Advanced-only gameplay failures: ['advanced:beach_slope=5', 'advanced:beach_slope=40', 'advanced:fjord_reach=250', 'combined_numeric_min'].
Design timing at minimum and maximum safe sizes (seconds): [{'size': 12, 'seconds': 0.343}, {'size': 20, 'seconds': 0.995}].
Controls tested include mex_count 6/20 and geos 0/3, plus Jungle/Swamp/Industrial with morning/evening/noon, painted/engine sky and grass 0/1/2. Every setting is explained and parameter keys are unique.

### Default seeds 1-5

Seed 1: PASS
```text
Tanks       can reach the enemy: NO (optional on naval maps)
Bots        can reach the enemy: NO (optional on naval maps)
Spiders     can reach the enemy: NO (optional on naval maps)
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Ships       can reach the enemy: yes
Amphibian access from bases to ports: yes
Metal spots unreachable for amphibian constructors: 0 of 52
Underwater metal spots unreachable for ships: 0 of 30
Naval map: sea crossings and underwater metal use naval validation.
Expansion metal sites placed: 23 of 23
Fleet access to seeded inlet 1: yes
Fleet access to seeded inlet 2: yes
Reclaim per side: 474 metal in rocks, 404 metal in wrecks
```

Seed 2: PASS
```text
Tanks       can reach the enemy: NO (optional on naval maps)
Bots        can reach the enemy: NO (optional on naval maps)
Spiders     can reach the enemy: NO (optional on naval maps)
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Ships       can reach the enemy: yes
Amphibian access from bases to ports: yes
Metal spots unreachable for amphibian constructors: 0 of 52
Underwater metal spots unreachable for ships: 0 of 30
Naval map: sea crossings and underwater metal use naval validation.
Expansion metal sites placed: 23 of 23
Fleet access to seeded inlet 1: yes
Fleet access to seeded inlet 2: yes
Reclaim per side: 542 metal in rocks, 614 metal in wrecks
```

Seed 3: PASS
```text
Tanks       can reach the enemy: NO (optional on naval maps)
Bots        can reach the enemy: NO (optional on naval maps)
Spiders     can reach the enemy: NO (optional on naval maps)
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Ships       can reach the enemy: yes
Amphibian access from bases to ports: yes
Metal spots unreachable for amphibian constructors: 0 of 52
Underwater metal spots unreachable for ships: 0 of 30
Naval map: sea crossings and underwater metal use naval validation.
Expansion metal sites placed: 23 of 23
Fleet access to seeded inlet 1: yes
Fleet access to seeded inlet 2: yes
Reclaim per side: 278 metal in rocks, 300 metal in wrecks
```

Seed 4: PASS
```text
Tanks       can reach the enemy: NO (optional on naval maps)
Bots        can reach the enemy: NO (optional on naval maps)
Spiders     can reach the enemy: NO (optional on naval maps)
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Ships       can reach the enemy: yes
Amphibian access from bases to ports: yes
Metal spots unreachable for amphibian constructors: 0 of 52
Underwater metal spots unreachable for ships: 0 of 26
Naval map: sea crossings and underwater metal use naval validation.
Expansion metal sites placed: 23 of 23
Fleet access to seeded inlet 1: yes
Fleet access to seeded inlet 2: yes
Reclaim per side: 526 metal in rocks, 808 metal in wrecks
```

Seed 5: PASS
```text
Tanks       can reach the enemy: NO (optional on naval maps)
Bots        can reach the enemy: NO (optional on naval maps)
Spiders     can reach the enemy: NO (optional on naval maps)
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Ships       can reach the enemy: yes
Amphibian access from bases to ports: yes
Metal spots unreachable for amphibian constructors: 0 of 52
Underwater metal spots unreachable for ships: 0 of 30
Naval map: sea crossings and underwater metal use naval validation.
Expansion metal sites placed: 23 of 23
Fleet access to seeded inlet 1: yes
Fleet access to seeded inlet 2: yes
Reclaim per side: 386 metal in rocks, 1806 metal in wrecks
```

## Visual review and export

All ten default-seed previews and an enlarged default preview inspected. Seed 1/default and seed 7/configured variant inspected together in series2_variants.png. Fjord Coast additionally has native 1:1 height-shaded coast/seam crops; one pixel is one 8-elmo height sample.
Source briefs record visual_review=true after inspection. The embedded brief in a report can precede that flag update; original reports and fingerprints are not rewritten.
Real prototype: Forge_Fjord_Coast_v1.sdz, size [12, 12], seed 1, 39240833 bytes. ZIP integrity, SMF/SMT, painted sky and Forge watermark verified. SMF grass extra-header count: 1.
Prototype watermark uses the existing reserved unknown code 255. No final template IDs were allocated. Rebuild after Core registration for a release.
No map has been loaded or played in Zero-K. Live balance and visual checks in the engine remain open.

## Limits and Core wishes

- No live Zero-K playtest.
- Closely spaced inlets can share a mouth.
- Advanced very deep mainland or narrow inlets can fail naval gameplay validation.
- Requires the _naval.islands / finish helpers delivered in TPL-naval-fix-1.

## Reproduction

python -m pytest tests/test_template_fjord_coast.py
python -m tools.template_workflow check fjord_coast --level full
python -m pytest tests  # scope collection to tests, excluding unpacked output copies

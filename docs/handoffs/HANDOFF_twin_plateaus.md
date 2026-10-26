# TPL-series-2-2: Twin Plateaus

## Design

High team home plateaus with several deliberate ramps into contested lowlands.
Promotes the Twin Plateaus example into a scalable, seeded template with protected ramps, configurable approach count and general resource controls.
Players: 1v1 to 4v4, two starting pads per team. Modes: ('1v1', 'team'). Tags: ('land', 'chokes').
Two to four planned ramps per side connect the home heights and shared lowland; ramp corridors are reserved from resource/reclaim placement.
Procedural mirrored economy and geothermal sites, with three protected opening spots per side on the home plateau.

## Integration

Base: CORE-20261022-1930 plus the published FFA 2000, biome/sky/grass 2030 and UI 2045 packages. Imported Core sources are preserved; these tickets add only their selected template, tests, brief, handoff and thumbnail files.
Dependency: No extra template helper beyond the published Core..
Class: TwinPlateausTemplate from atlasforge.templates.twin_plateaus; template ID twin_plateaus.
The Core owner alone registers the class and assigns its final watermark ID. Registry, watermark and existing shared Core files are excluded from this patch.
TPL-series-2-5 includes the cross-family environment test and requires all five template sources. Apply tickets 1 through 5 in order after their documented helper prerequisites.

## Parameters

| Key | Default | Safe | Advanced | Player explanation |
|---|---|---|---|---|
| `size` | `14` | (12, 14, 16, 18, 20) | (8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32) | Width and height of the map in Spring map units; one unit is 512 elmos (a small tank is about 30 elmos long). 8x8 suits a fast 1v1, 12-16 a 2v2 or 3v3, 20 and more large team games. Bigger maps take longer to build, need more metal spots to stay interesting and make travel times (and raids) longer. |
| `biome` | `temperate` | ('alien', 'arctic', 'ashland', 'autumn', 'desert', 'industrial', 'jungle', 'moon', 'swamp', 'temperate', 'volcanic') | ('alien', 'arctic', 'ashland', 'autumn', 'desert', 'industrial', 'jungle', 'moon', 'swamp', 'temperate', 'volcanic') | The look of the map: ground colours and textures, sky, sun, water colour, trees, grass and the usual wind. It does not change the shape of the terrain. jungle: dense forest and tall grass; swamp: murky water, mud puddles and reeds; industrial: steel plates and concrete, no trees. Desert, moon, alien, volcanic and ashland have no trees, and the moon has almost no wind. |
| `plateau_height` | `240` | (120, 320) | (60, 600) |  |
| `plateau_depth` | `0.26` | (0.22, 0.28) | (0.16, 0.36) |  |
| `ramps` | `2` | (2, 4) | (1, 6) |  |
| `ramp_width` | `260` | (180, 420) | (100, 900) |  |
| `lowland_detail` | `12` | (0, 25) | (0, 70) |  |

The common mex, metal, geo, wind, tidal, sun, sky, grass, trees, rocks, wrecks and erosion controls come from the Core; settings.json includes every setting and its English info text. Opening metal sites carry fixed=True. No private count controls are added.

## Checks

Complete regression suite: 463 passed, 3 deselected in 1270.20s (0:21:10); local HTTP app tests: 3 passed.
Fresh published Core integration smoke: 65 passed, 63 deselected. This selects player-facing metadata/previews, family-specific rules and common-resource/environment combinations; default-seed and exhaustive parameter tests are covered by the full regression and matrix.
Full matrix: 72 cases, zero generation errors. All default seeds 1-10 and tested safe settings are playable. Advanced-only gameplay failures: ['advanced:plateau_height=600'].
Design timing at minimum and maximum safe sizes (seconds): [{'size': 12, 'seconds': 0.715}, {'size': 20, 'seconds': 1.357}].
Controls tested include mex_count 6/20 and geos 0/3, plus Jungle/Swamp/Industrial with morning/evening/noon, painted/engine sky and grass 0/1/2. Every setting is explained and parameter keys are unique.

### Default seeds 1-5

Seed 1: PASS
```text
Tanks       can reach the enemy: yes, only through: -
Bots        can reach the enemy: yes, only through: -
Spiders     can reach the enemy: yes, also outside the chokes
Amphibians  can reach the enemy: yes, only through: -
Hovers      can reach the enemy: yes, only through: -
Metal spots unreachable for tanks: 0 of 50
Planned plateau ramps per team: 2
Reclaim per side: 285 metal in rocks, 400 metal in wrecks
```

Seed 2: PASS
```text
Tanks       can reach the enemy: yes, only through: -
Bots        can reach the enemy: yes, only through: -
Spiders     can reach the enemy: yes, also outside the chokes
Amphibians  can reach the enemy: yes, only through: -
Hovers      can reach the enemy: yes, only through: -
Metal spots unreachable for tanks: 0 of 50
Planned plateau ramps per team: 2
Reclaim per side: 408 metal in rocks, 416 metal in wrecks
```

Seed 3: PASS
```text
Tanks       can reach the enemy: yes, only through: -
Bots        can reach the enemy: yes, only through: -
Spiders     can reach the enemy: yes, also outside the chokes
Amphibians  can reach the enemy: yes, only through: -
Hovers      can reach the enemy: yes, only through: -
Metal spots unreachable for tanks: 0 of 50
Planned plateau ramps per team: 2
Reclaim per side: 364 metal in rocks, 294 metal in wrecks
```

Seed 4: PASS
```text
Tanks       can reach the enemy: yes, only through: -
Bots        can reach the enemy: yes, only through: -
Spiders     can reach the enemy: yes, also outside the chokes
Amphibians  can reach the enemy: yes, only through: -
Hovers      can reach the enemy: yes, only through: -
Metal spots unreachable for tanks: 0 of 50
Planned plateau ramps per team: 2
Reclaim per side: 339 metal in rocks, 536 metal in wrecks
```

Seed 5: PASS
```text
Tanks       can reach the enemy: yes, only through: -
Bots        can reach the enemy: yes, only through: -
Spiders     can reach the enemy: yes, also outside the chokes
Amphibians  can reach the enemy: yes, only through: -
Hovers      can reach the enemy: yes, only through: -
Metal spots unreachable for tanks: 0 of 50
Planned plateau ramps per team: 2
Reclaim per side: 412 metal in rocks, 164 metal in wrecks
```

## Visual review and export

All ten default-seed previews and an enlarged default preview inspected. Seed 1/default and seed 7/configured variant inspected together in series2_variants.png. Fjord Coast additionally has native 1:1 height-shaded coast/seam crops; one pixel is one 8-elmo height sample.
Source briefs record visual_review=true after inspection. The embedded brief in a report can precede that flag update; original reports and fingerprints are not rewritten.
Real prototype: Forge_Twin_Plateaus_v1.sdz, size [12, 12], seed 1, 39722030 bytes. ZIP integrity, SMF/SMT, painted sky and Forge watermark verified. SMF grass extra-header count: 1.
Prototype watermark uses the existing reserved unknown code 255. No final template IDs were allocated. Rebuild after Core registration for a release.
No map has been loaded or played in Zero-K. Live balance and visual checks in the engine remain open.

## Limits and Core wishes

- No live Zero-K playtest.
- Advanced very high or deep plateaus may leave little lowland or overlapping approaches.

## Reproduction

python -m pytest tests/test_template_twin_plateaus.py
python -m tools.template_workflow check twin_plateaus --level full
python -m pytest tests  # scope collection to tests, excluding unpacked output copies

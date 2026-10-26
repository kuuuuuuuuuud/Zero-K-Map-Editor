# Three Lanes

Template ID: `three_lanes`. Isolated workspace: `forge-templates`.

Three long parallel battle corridors with shared rear areas and lateral crossings.

Difference from base: Two longitudinal ridges divide entire fronts; this is not a central wall with three gates.

Players: 1v1 or two teams sharing one rear start box per side.
Routes: All three lanes independently support tanks. Openings near each side connect the lanes; an optional central crossing adds a contested switch point. Spiders may cross ridge tops.
Economy: Three protected opening spots, mirrored expansion groups in every lane, richer forward fields and one optional geothermal vent per side.

## Parameters

| Key | Label | Default | Safe | Advanced | Effect |
|---|---|---|---|---|---|
| size | Map size | 16 | (12, 14, 16, 18, 20) | (8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32) | Width and height in Spring map units (8 = small 1v1, 16 = 2v2, 20 = large team game) |
| biome | Biome | temperate | ('alien', 'arctic', 'ashland', 'autumn', 'desert', 'moon', 'temperate', 'volcanic') | ('alien', 'arctic', 'ashland', 'autumn', 'desert', 'moon', 'temperate', 'volcanic') | Colours, sky, light and trees |
| ridge_height | Ridge height | 330 | (220, 480) | (80, 1000) | Height of the dividing ridges above the lane floor |
| ridge_width | Ridge width | 180 | (100, 300) | (40, 800) | Width of the flat ridge crest in elmos |
| crossing_width | Lateral crossing width | 520 | (360, 800) | (120, 1800) | Width of each north-south opening between lanes |
| central_crossing | Central lane crossing | False | (False, True) | (False, True) | Add a contested connection between all three lanes at the centre |
| geovents | Geothermal vents | True | (False, True) | (False, True) | Place one geothermal vent behind each side's front |
| metal | Metal amount | 1.0 | (0.5, 2.0) | (0.1, 5.0) | Multiplies the value of every metal spot |
| trees | Trees | 1.0 | (0.0, 2.0) | (0.0, 5.0) | Tree density (biomes without trees stay bare) |
| rocks | Rocks | 0.5 | (0.0, 2.0) | (0.0, 6.0) | Rock clusters with reclaimable metal (glowing crystals on alien and moon maps) |
| wrecks | Wrecks | 0.3 | (0.0, 2.0) | (0.0, 6.0) | Battlefield wrecks of Zero-K units between the bases (reclaimable metal) |
| erosion | Erosion | 0.6 | (0.0, 1.5) | (0.0, 4.0) | Rain-carved gullies and valleys on natural slopes; bases, metal spots, chokes and walls stay as designed |

## Default check reports: seeds 1-5

### default_seed_1

```text
Tanks       can reach the enemy: yes, also outside the chokes
Bots        can reach the enemy: yes, also outside the chokes
Spiders     can reach the enemy: yes, also outside the chokes
Amphibians  can reach the enemy: yes, also outside the chokes
Hovers      can reach the enemy: yes, also outside the chokes
Metal spots unreachable for tanks: 0 of 36
Independent tank lane 1: yes
Independent tank lane 2: yes
Independent tank lane 3: yes
Reclaim per side: 418 metal in rocks, 556 metal in wrecks
```

### default_seed_2

```text
Tanks       can reach the enemy: yes, also outside the chokes
Bots        can reach the enemy: yes, also outside the chokes
Spiders     can reach the enemy: yes, also outside the chokes
Amphibians  can reach the enemy: yes, also outside the chokes
Hovers      can reach the enemy: yes, also outside the chokes
Metal spots unreachable for tanks: 0 of 36
Independent tank lane 1: yes
Independent tank lane 2: yes
Independent tank lane 3: yes
Reclaim per side: 545 metal in rocks, 284 metal in wrecks
```

### default_seed_3

```text
Tanks       can reach the enemy: yes, also outside the chokes
Bots        can reach the enemy: yes, also outside the chokes
Spiders     can reach the enemy: yes, also outside the chokes
Amphibians  can reach the enemy: yes, also outside the chokes
Hovers      can reach the enemy: yes, also outside the chokes
Metal spots unreachable for tanks: 0 of 36
Independent tank lane 1: yes
Independent tank lane 2: yes
Independent tank lane 3: yes
Reclaim per side: 449 metal in rocks, 1788 metal in wrecks
```

### default_seed_4

```text
Tanks       can reach the enemy: yes, also outside the chokes
Bots        can reach the enemy: yes, also outside the chokes
Spiders     can reach the enemy: yes, also outside the chokes
Amphibians  can reach the enemy: yes, also outside the chokes
Hovers      can reach the enemy: yes, also outside the chokes
Metal spots unreachable for tanks: 0 of 36
Independent tank lane 1: yes
Independent tank lane 2: yes
Independent tank lane 3: yes
Reclaim per side: 444 metal in rocks, 224 metal in wrecks
```

### default_seed_5

```text
Tanks       can reach the enemy: yes, also outside the chokes
Bots        can reach the enemy: yes, also outside the chokes
Spiders     can reach the enemy: yes, also outside the chokes
Amphibians  can reach the enemy: yes, also outside the chokes
Hovers      can reach the enemy: yes, also outside the chokes
Metal spots unreachable for tanks: 0 of 36
Independent tank lane 1: yes
Independent tank lane 2: yes
Independent tank lane 3: yes
Reclaim per side: 476 metal in rocks, 506 metal in wrecks
```

## Validation

- Full matrix: 66 cases passed; seeds 1-10 playable.
- Safe parameter boundaries passed; additional combined safe settings have dedicated geometry tests.
- Determinism, declared symmetry and mirrored economy passed.
- Visual review: seed contact sheets and enlarged previews inspected.
- Shared regression suite: 167 passed after local registration of all three templates.
- Gallery fields checked against the newer, read-only core Template.info API.
- Actual size-12 SDZ built with author Test; ZIP CRC, SMF/SMT and template/seed watermark verified.
- Loaded and played in Zero-K: NO.

## Timing

- Raw make, size 12: 0.178 s
- Raw make, size 20: 0.503 s

## Known limitations

- Ridges intentionally allow spider traversal; they are not absolute barriers.
- Parameter extremes in advanced mode may merge crossings or reduce lane separation.
- No live Zero-K playtest yet.
- Advanced gameplay failures (buildable/inspectable, not accepted as playable): combined_numeric_max
- Generated previews show terrain and resources; live balance and unit-footprint behaviour still need playtesting.

## Core integration

- No terrain/check/render/gadget/core API changes required.
- Uses the existing private naval helper for naval construction (naval templates only).
- Registry, provisional watermark code and thumbnail are included as a reviewed local integration proposal.
- Final watermark IDs belong to the core owner; do not renumber old IDs or overwrite a newer dictionary.
- tests/test_templates.py uses SMALL.get(tid, {}) so new registry entries receive the common smoke test.
- Re-run the suite after merging into the current core. Gallery metadata was added compatibly; no shared core files were copied back.

## Artifacts

- `three_lanes_preview.png`, `three_lanes.jpg`, `contact_sheet.png`, `report.json`: in the exchange package under `validation/three_lanes/`.
- Built map: `Forge_Three_Lanes_v1.sdz` (separate playtest map package).
- Full build/watermark receipts: `archive-results.json`; shared regression output: `pytest.log`.

Technical handoff only; no public release or in-game acceptance is claimed.

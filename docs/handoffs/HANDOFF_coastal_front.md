# Coastal Front

Template ID: `coastal_front`. Isolated workspace: `forge-templates`.

A full-width land front in the north shares a long shoreline with a navigable sea in the south.

Difference from base: Both land armies and fleets have complete east-west routes; Open Sea separates the coastal bases by water.

Players: 1v1 or two teams sharing a compact mainland start box on each side.
Routes: Guaranteed dry tank staging corridor, continuous coastal fleet route, gentle amphibious beaches and hover access. Additional checks require the land route as well as naval connectivity.
Economy: Mirrored mainland and underwater expansion fields, three safe opening spots and optional geothermal vents. Underwater economy encourages ships without replacing the land front. A submerged shelf keeps underwater expansion sites available at deep-sea and shallow-beach settings.

## Parameters

| Key | Label | Default | Safe | Advanced | Effect |
|---|---|---|---|---|---|
| size | Map size | 16 | (12, 14, 16, 18, 20) | (8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32) | Width and height in Spring map units (8 = small 1v1, 16 = 2v2, 20 = large team game) |
| biome | Biome | temperate | ('alien', 'arctic', 'ashland', 'autumn', 'desert', 'moon', 'temperate', 'volcanic') | ('alien', 'arctic', 'ashland', 'autumn', 'desert', 'moon', 'temperate', 'volcanic') | Colours, sky, light and trees |
| depth | Sea depth | 180 | (100, 320) | (40, 600) | Depth in elmos below the water surface |
| beach_slope | Beach slope | 14 | (10, 18) | (5, 40) | Real slope in degrees between the seabed and dry land |
| coast_noise | Coast irregularity | 55 | (0, 100) | (0, 250) | Coastline displacement in elmos |
| sea_metal | Underwater metal share | 0.65 | (0.3, 0.8) | (0.0, 1.0) | Share of expansion spots placed on the seabed |
| geovents | Geothermal vents | True | (False, True) | (False, True) | Add one geothermal vent on each home island |
| land_share | Mainland depth | 0.44 | (0.38, 0.58) | (0.25, 0.72) | Fraction of map depth occupied by the mainland before its beach |
| headlands | Headland reach | 0.035 | (0.0, 0.06) | (0.0, 0.12) | Symmetric coastal headlands as a fraction of map width |
| metal | Metal amount | 1.0 | (0.5, 2.0) | (0.1, 5.0) | Multiplies the value of every metal spot |
| trees | Trees | 1.0 | (0.0, 2.0) | (0.0, 5.0) | Tree density (biomes without trees stay bare) |
| rocks | Rocks | 0.5 | (0.0, 2.0) | (0.0, 6.0) | Rock clusters with reclaimable metal (glowing crystals on alien and moon maps) |
| wrecks | Wrecks | 0.3 | (0.0, 2.0) | (0.0, 6.0) | Battlefield wrecks of Zero-K units between the bases (reclaimable metal) |
| erosion | Erosion | 0.6 | (0.0, 1.5) | (0.0, 4.0) | Rain-carved gullies and valleys on natural slopes; bases, metal spots, chokes and walls stay as designed |

## Default check reports: seeds 1-5

### default_seed_1

```text
Tanks       can reach the enemy: yes
Bots        can reach the enemy: yes
Spiders     can reach the enemy: yes
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Ships       can reach the enemy: yes
Amphibian access from bases to ports: yes
Metal spots unreachable for amphibian constructors: 0 of 52
Underwater metal spots unreachable for ships: 0 of 30
Naval map: sea crossings and underwater metal use naval validation.
Expansion metal sites placed: 23 of 23
Continuous mainland tank front: yes
Reclaim per side: 373 metal in rocks, 464 metal in wrecks
```

### default_seed_2

```text
Tanks       can reach the enemy: yes
Bots        can reach the enemy: yes
Spiders     can reach the enemy: yes
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Ships       can reach the enemy: yes
Amphibian access from bases to ports: yes
Metal spots unreachable for amphibian constructors: 0 of 52
Underwater metal spots unreachable for ships: 0 of 30
Naval map: sea crossings and underwater metal use naval validation.
Expansion metal sites placed: 23 of 23
Continuous mainland tank front: yes
Reclaim per side: 351 metal in rocks, 690 metal in wrecks
```

### default_seed_3

```text
Tanks       can reach the enemy: yes
Bots        can reach the enemy: yes
Spiders     can reach the enemy: yes
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Ships       can reach the enemy: yes
Amphibian access from bases to ports: yes
Metal spots unreachable for amphibian constructors: 0 of 52
Underwater metal spots unreachable for ships: 0 of 30
Naval map: sea crossings and underwater metal use naval validation.
Expansion metal sites placed: 23 of 23
Continuous mainland tank front: yes
Reclaim per side: 401 metal in rocks, 672 metal in wrecks
```

### default_seed_4

```text
Tanks       can reach the enemy: yes
Bots        can reach the enemy: yes
Spiders     can reach the enemy: yes
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Ships       can reach the enemy: yes
Amphibian access from bases to ports: yes
Metal spots unreachable for amphibian constructors: 0 of 52
Underwater metal spots unreachable for ships: 0 of 30
Naval map: sea crossings and underwater metal use naval validation.
Expansion metal sites placed: 23 of 23
Continuous mainland tank front: yes
Reclaim per side: 341 metal in rocks, 496 metal in wrecks
```

### default_seed_5

```text
Tanks       can reach the enemy: yes
Bots        can reach the enemy: yes
Spiders     can reach the enemy: yes
Amphibians  can reach the enemy: yes
Hovers      can reach the enemy: yes
Ships       can reach the enemy: yes
Amphibian access from bases to ports: yes
Metal spots unreachable for amphibian constructors: 0 of 52
Underwater metal spots unreachable for ships: 0 of 30
Naval map: sea crossings and underwater metal use naval validation.
Expansion metal sites placed: 23 of 23
Continuous mainland tank front: yes
Reclaim per side: 415 metal in rocks, 400 metal in wrecks
```

## Validation

- Full matrix: 74 cases passed; seeds 1-10 playable.
- Safe parameter boundaries passed; additional combined safe settings have dedicated geometry tests.
- Determinism, declared symmetry and mirrored economy passed.
- Visual review: seed contact sheets and enlarged previews inspected.
- Shared regression suite: 167 passed after local registration of all three templates.
- Gallery fields checked against the newer, read-only core Template.info API.
- Actual size-12 SDZ built with author Test; ZIP CRC, SMF/SMT and template/seed watermark verified.
- Loaded and played in Zero-K: NO.

## Timing

- Raw make, size 12: 0.178 s
- Raw make, size 20: 0.526 s

## Known limitations

- Advanced land depth and beach combinations may flood the land route or strand a port.
- No live Zero-K playtest yet.
- Advanced gameplay failures (buildable/inspectable, not accepted as playable): none in the tested matrix
- Generated previews show terrain and resources; live balance and unit-footprint behaviour still need playtesting.

## Core integration

- No terrain/check/render/gadget/core API changes required.
- Uses the existing private naval helper for naval construction (naval templates only).
- Registry, provisional watermark code and thumbnail are included as a reviewed local integration proposal.
- Final watermark IDs belong to the core owner; do not renumber old IDs or overwrite a newer dictionary.
- tests/test_templates.py uses SMALL.get(tid, {}) so new registry entries receive the common smoke test.
- Re-run the suite after merging into the current core. Gallery metadata was added compatibly; no shared core files were copied back.

## Artifacts

- `coastal_front_preview.png`, `coastal_front.jpg`, `contact_sheet.png`, `report.json`: in the exchange package under `validation/coastal_front/`.
- Built map: `Forge_Coastal_Front_v1.sdz` (separate playtest map package).
- Full build/watermark receipts: `archive-results.json`; shared regression output: `pytest.log`.

Technical handoff only; no public release or in-game acceptance is claimed.

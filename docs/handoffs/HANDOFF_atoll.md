# Atoll

Template ID: `atoll`. Isolated workspace: `forge-templates`.

Two opposing island arcs around a lagoon, linked to the outer ocean through deep northern and southern entrances.

Difference from base: A ring defines distinct inner and outer fleet routes. The lagoon and its entrances replace scattered expansion islands.

Players: 1v1 or two teams sharing a widened home arc on each side.
Routes: Ships contest the lagoon or use the outer ocean. Two protected deep entrances connect both spaces. Amphibians and hovers cross the gentle beaches; dry land never has to join the enemy base. Dedicated outer bypasses keep the island arcs clear of the map edge; their banks use a fixed 24-degree slope.
Economy: Three safe opening spots on each home arc, mirrored land and underwater expansions and optional geothermal vents. Seabed spots must belong to the same fleet network as the ports.

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
| ring_radius | Atoll radius | 0.3 | (0.28, 0.32) | (0.22, 0.38) | Distance from the lagoon centre to the island ring as a fraction of map width |
| ring_width | Island ring width | 0.11 | (0.09, 0.14) | (0.04, 0.24) | Full width of the dry island arcs as a fraction of map width |
| passage_width | Lagoon entrance width | 560 | (400, 800) | (160, 1800) | Minimum deep-water width of the northern and southern entrances |
| metal | Metal amount | 1.0 | (0.5, 2.0) | (0.1, 5.0) | Multiplies the value of every metal spot |
| trees | Trees | 1.0 | (0.0, 2.0) | (0.0, 5.0) | Tree density (biomes without trees stay bare) |
| rocks | Rocks | 0.5 | (0.0, 2.0) | (0.0, 6.0) | Rock clusters with reclaimable metal (glowing crystals on alien and moon maps) |
| wrecks | Wrecks | 0.3 | (0.0, 2.0) | (0.0, 6.0) | Battlefield wrecks of Zero-K units between the bases (reclaimable metal) |
| erosion | Erosion | 0.6 | (0.0, 1.5) | (0.0, 4.0) | Rain-carved gullies and valleys on natural slopes; bases, metal spots, chokes and walls stay as designed |

## Default check reports: seeds 1-5

### default_seed_1

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
Lagoon connected to north ocean entrance: yes
Lagoon connected to south ocean entrance: yes
Reclaim per side: 279 metal in rocks, 160 metal in wrecks
```

### default_seed_2

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
Lagoon connected to north ocean entrance: yes
Lagoon connected to south ocean entrance: yes
Reclaim per side: 370 metal in rocks, 0 metal in wrecks
```

### default_seed_3

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
Lagoon connected to north ocean entrance: yes
Lagoon connected to south ocean entrance: yes
Reclaim per side: 293 metal in rocks, 0 metal in wrecks
```

### default_seed_4

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
Lagoon connected to north ocean entrance: yes
Lagoon connected to south ocean entrance: yes
Reclaim per side: 294 metal in rocks, 0 metal in wrecks
```

### default_seed_5

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
Lagoon connected to north ocean entrance: yes
Lagoon connected to south ocean entrance: yes
Reclaim per side: 377 metal in rocks, 196 metal in wrecks
```

## Validation

- Full matrix: 78 cases passed; seeds 1-10 playable.
- Safe parameter boundaries passed; additional combined safe settings have dedicated geometry tests.
- Determinism, declared symmetry and mirrored economy passed.
- Visual review: seed contact sheets and enlarged previews inspected.
- Shared regression suite: 167 passed after local registration of all three templates.
- Gallery fields checked against the newer, read-only core Template.info API.
- Actual size-12 SDZ built with author Test; ZIP CRC, SMF/SMT and template/seed watermark verified.
- Loaded and played in Zero-K: NO.

## Timing

- Raw make, size 12: 0.213 s
- Raw make, size 20: 0.602 s

## Known limitations

- Advanced radius, ring width and beach combinations may merge arcs or leave little expansion land.
- No live Zero-K playtest yet.
- Advanced gameplay failures (buildable/inspectable, not accepted as playable): advanced:size=8, advanced:size=10, advanced:beach_slope=5, advanced:beach_slope=40, combined_numeric_min
- Generated previews show terrain and resources; live balance and unit-footprint behaviour still need playtesting.

## Core integration

- No terrain/check/render/gadget/core API changes required.
- Uses the existing private naval helper for naval construction (naval templates only).
- Registry, provisional watermark code and thumbnail are included as a reviewed local integration proposal.
- Final watermark IDs belong to the core owner; do not renumber old IDs or overwrite a newer dictionary.
- tests/test_templates.py uses SMALL.get(tid, {}) so new registry entries receive the common smoke test.
- Re-run the suite after merging into the current core. Gallery metadata was added compatibly; no shared core files were copied back.

## Artifacts

- `atoll_preview.png`, `atoll.jpg`, `contact_sheet.png`, `report.json`: in the exchange package under `validation/atoll/`.
- Built map: `Forge_Atoll_v1.sdz` (separate playtest map package).
- Full build/watermark receipts: `archive-results.json`; shared regression output: `pytest.log`.

Technical handoff only; no public release or in-game acceptance is claimed.

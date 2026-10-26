# Island Straits

Template id: `straits`

Long central islands divide the sea into named east-west fleet passages. Coastal bases remain connected to offshore ports, and central land invites amphibious attacks. Designed for 1v1 or two teams, with concentrated naval fights around the selected passages.

## Parameters

| Key | Label | Default | Safe range | Advanced range | Effect |
|---|---|---|---|---|---|
| `size` | Map size | 16 | 12, 14, 16, 18, 20 | 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32 | Width and height in Spring map units (8 = small 1v1, 16 = 2v2, 20 = large team game) |
| `biome` | Biome | temperate | alien, arctic, ashland, autumn, desert, moon, temperate, volcanic | alien, arctic, ashland, autumn, desert, moon, temperate, volcanic | Colours, sky, light and trees |
| `depth` | Sea depth | 180 | 100 .. 320 | 40 .. 600 | Depth in elmos below the water surface |
| `beach_slope` | Beach slope | 14 | 10 .. 18 | 5 .. 40 | Real slope in degrees between the seabed and dry land |
| `coast_noise` | Coast irregularity | 55 | 0 .. 100 | 0 .. 250 | Coastline displacement in elmos |
| `sea_metal` | Underwater metal share | 0.65 | 0.3 .. 0.8 | 0.0 .. 1.0 | Share of expansion spots placed on the seabed |
| `geovents` | Geothermal vents | True | off / on | off / on | Add one geothermal vent on each home island |
| `passages` | Fleet passages | 3 | 2 .. 4 | 1 .. 7 | Number of east-west gaps between the central islands and map edges |
| `passage_width` | Passage width | 1100 | 800 .. 1500 | 300 .. 3000 | Approximate waterline width in elmos at the default map size |
| `island_width` | Central island width | 1500 | 1000 .. 1800 | 400 .. 3000 | East-west width of the central islands in elmos |
| `metal` | Metal amount | 1.0 | 0.5 .. 2.0 | 0.1 .. 5.0 | Multiplies the value of every metal spot |
| `trees` | Trees | 1.0 | 0.0 .. 2.0 | 0.0 .. 5.0 | Tree density (biomes without trees stay bare) |
| `erosion` | Erosion | 0.6 | 0.0 .. 1.5 | 0.0 .. 4.0 | Rain-carved gullies and valleys on natural slopes; bases, metal spots, chokes and walls stay as designed |

## Default check reports

Seeds 1-5, captured from the public preview command. Tests also cover seeds 6-10.

### Seed 1

```text
Check: OK
  Tanks       can reach the enemy: NO (optional on naval maps)
  Bots        can reach the enemy: NO (optional on naval maps)
  Spiders     can reach the enemy: NO (optional on naval maps)
  Amphibians  can reach the enemy: yes
  Hovers      can reach the enemy: yes
  Ships       can reach the enemy: yes
  Amphibian access from bases to ports: yes
  Metal spots unreachable for amphibian constructors: 0 of 52
  Underwater metal spots unreachable for ships: 0 of 30
  Fleet passage strait 1 reaches the connected sea: yes
  Fleet passage strait 2 reaches the connected sea: yes
  Fleet passage strait 3 reaches the connected sea: yes
  Naval map: sea crossings and underwater metal use naval validation.
  Expansion metal sites placed: 23 of 23
```

### Seed 2

```text
Check: OK
  Tanks       can reach the enemy: NO (optional on naval maps)
  Bots        can reach the enemy: NO (optional on naval maps)
  Spiders     can reach the enemy: NO (optional on naval maps)
  Amphibians  can reach the enemy: yes
  Hovers      can reach the enemy: yes
  Ships       can reach the enemy: yes
  Amphibian access from bases to ports: yes
  Metal spots unreachable for amphibian constructors: 0 of 52
  Underwater metal spots unreachable for ships: 0 of 30
  Fleet passage strait 1 reaches the connected sea: yes
  Fleet passage strait 2 reaches the connected sea: yes
  Fleet passage strait 3 reaches the connected sea: yes
  Naval map: sea crossings and underwater metal use naval validation.
  Expansion metal sites placed: 23 of 23
```

### Seed 3

```text
Check: OK
  Tanks       can reach the enemy: NO (optional on naval maps)
  Bots        can reach the enemy: NO (optional on naval maps)
  Spiders     can reach the enemy: NO (optional on naval maps)
  Amphibians  can reach the enemy: yes
  Hovers      can reach the enemy: yes
  Ships       can reach the enemy: yes
  Amphibian access from bases to ports: yes
  Metal spots unreachable for amphibian constructors: 0 of 52
  Underwater metal spots unreachable for ships: 0 of 30
  Fleet passage strait 1 reaches the connected sea: yes
  Fleet passage strait 2 reaches the connected sea: yes
  Fleet passage strait 3 reaches the connected sea: yes
  Naval map: sea crossings and underwater metal use naval validation.
  Expansion metal sites placed: 23 of 23
```

### Seed 4

```text
Check: OK
  Tanks       can reach the enemy: NO (optional on naval maps)
  Bots        can reach the enemy: NO (optional on naval maps)
  Spiders     can reach the enemy: NO (optional on naval maps)
  Amphibians  can reach the enemy: yes
  Hovers      can reach the enemy: yes
  Ships       can reach the enemy: yes
  Amphibian access from bases to ports: yes
  Metal spots unreachable for amphibian constructors: 0 of 52
  Underwater metal spots unreachable for ships: 0 of 30
  Fleet passage strait 1 reaches the connected sea: yes
  Fleet passage strait 2 reaches the connected sea: yes
  Fleet passage strait 3 reaches the connected sea: yes
  Naval map: sea crossings and underwater metal use naval validation.
  Expansion metal sites placed: 23 of 23
```

### Seed 5

```text
Check: OK
  Tanks       can reach the enemy: NO (optional on naval maps)
  Bots        can reach the enemy: NO (optional on naval maps)
  Spiders     can reach the enemy: NO (optional on naval maps)
  Amphibians  can reach the enemy: yes
  Hovers      can reach the enemy: yes
  Ships       can reach the enemy: yes
  Amphibian access from bases to ports: yes
  Metal spots unreachable for amphibian constructors: 0 of 52
  Underwater metal spots unreachable for ships: 0 of 30
  Fleet passage strait 1 reaches the connected sea: yes
  Fleet passage strait 2 reaches the connected sea: yes
  Fleet passage strait 3 reaches the connected sea: yes
  Naval map: sea crossings and underwater metal use naval validation.
  Expansion metal sites placed: 23 of 23
```

## Timing

Raw `Template.make()` timings (seed 1; excludes erosion, preview and check report):

- Size 12: 0.415 seconds.
- Size 20: 1.150 seconds.

## Validation and limitations

Final complete suite: **89 passed in 241.46 seconds**. Baseline before changes: **26 passed**. Command: `.venv/Scripts/python.exe -u -m pytest -q --basetemp=.worktmp/verified_suite` (local app HTTP access enabled; LOCALAPPDATA points to the workspace test cache).

- Full tests cover exact terrain symmetry, mirrored resources/starts/geovents, deterministic seeds, regular size boundaries, safe numeric limits, every advanced numeric extreme and choice (including sizes 8-32), boolean toggles, combined numeric extremes at size 8, previews and a full size-12 archive build.
- Heavy-ship lanes at default settings also pass a 32-elmo clearance erosion test.
- Movement masks check sample connectivity, not engine footprint pathfinding, turn radii or shipyard placement. Real match balance and all safe-parameter combinations still need playtesting.
- Advanced settings can merge islands, submerge ports, steepen beaches or exhaust suitable resource sites. Such designs remain inspectable and report failed checks honestly.
- Size 12 and shallow beach settings can allow land units to wade between islands. This is a mixed naval/land variant; isolated islands are the default at size 16.
- Starts are on dry land. Port markers indicate checked fleet access points, not spawned units or additional start points.
- Built as a complete .sdz in the automated build test. Not loaded in a running Zero-K match.

## Integration / core changes

The user explicitly authorized the naval validation exception to the supplied no-core-changes rule. `Design.movement_profile` defaults to `land`; `naval_starts` carries explicit water access per side. `checks.report()` preserves land validation and adds naval requirements (ships between ports, hovers/amphibians between bases, base-to-port amphibian access, amphibian construction access to all metal, and ship access to underwater metal). `unit_masks()` adds a conservative heavy-ship mask using depth >15 elmos, verified against BOAT5/UBOAT3 in the installed `games/zk-stable.sdz` (normal BOAT3/4 need 5). `forge.check()` forwards the profile. The app exposes `reach_ships` from the explicit naval ports and a Ships route button; existing cell bits and event flags stay compatible. `watermark.TEMPLATE_CODES` assigns new stable codes 7-9 without changing any existing codes.

Shared template construction lives in the private `templates/_naval.py`; existing base/common terrain helpers are unchanged. Central islands use exact capsule distances to keep wide beaches from closing narrow straits; this helper remains inside the template. No new dependencies or Lua gadgets. Future core wishes: configurable ship draft/footprint tests and water start boxes could become standard template features.

## Artifacts

- Preview: [straits_preview.png](straits_preview.png)
- Gallery thumbnail: `atlasforge/app/web/thumbs/straits.jpg`
- Template: `atlasforge/templates/straits.py`
- Tests: `tests/test_template_straits.py`, plus shared naval validation tests.

- Size-12 sample archive (author Test): [`Forge_Island_Straits_v1.sdz`](out/naval_templates/Forge_Island_Straits_v1.sdz)

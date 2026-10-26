# TPL-dune_sea-1: Procedural Dune Sea

## Design

Changing winds and warped noise create long dune chains, crescent fields or intersecting star dunes. Seeded rocky uplands interrupt the sand; tanks receive natural valleys and automatic ramps.

Forms: longitudinal, crescents, star dunes. All seeds change macro geography, not just colours or decoration.
Uses Skirmish's existing resource placement and automatic tank ramp carving, with an independent terrain formula.
Modes: ('1v1', 'team'); tags: ('land',); players: 1v1 to 4v4.

## Integration

Base: CORE-20261022-1930 snapshot, GitHub main 7c66ad73c1643de1d601601abd673f764736cf4e.
Snapshot SHA-256: 94198b64b3e33dada7ad69c0c363882c83a12ee9eb4fd0e475ed7ca2f9f00c52.
Apply TPL-highlands-1 first for the shared `_wildlands.py` pipeline.
The Core owner registers the class and assigns the final watermark ID. No registry, watermark or existing core source is included in this patch.
Class to register: `DuneSeaTemplate` from `atlasforge.templates.dune_sea`; ID `dune_sea`.
The Dune Sea ticket also provides cross-family QA tests and therefore requires all three tickets.
General resource/terrain settings come from the Core. Six opening metal sites are fixed; expansion sites remain adjustable.
No damage hazards or explicit gates exist in this family. The symmetric carved-route mask is kept clear of new resources and reclaim.

## Parameters

| Key | Default | Player explanation |
|---|---|---|
| `size` | `12` | Sets the square map width in Spring map units, each equal to 512 elmos. Larger maps provide more expansion space and longer travel distances. For example, size 12 is a compact match while size 20 gives teams more room. |
| `biome` | `desert` | Changes terrain colours, vegetation, lighting and the sky. The terrain family and seed still determine the geography. For example, Arctic gives the same landforms a cold appearance. |
| `layout` | `diag` | Sets the opposing base orientation and the corresponding terrain symmetry. Both sides receive mirrored resources and equal starting terrain. For example, diag places opponents in the northwest and southeast. |
| `relief` | `1.0` | Multiplies the elevation differences, with 1.0 as the standard height scale. Higher terrain creates stronger high-ground positions and can require additional tank ramps. For example, 0.5 halves the relief without selecting a different seed. |
| `warp` | `1.0` | Scales the displacement of the underlying terrain pattern. Higher values bend ridges, basins and region boundaries into more irregular shapes. For example, zero leaves an orderly underlying pattern while 1.0 uses normal distortion. |
| `form` | `longitudinal` | Selects the wind pattern used to build the dunes. Longitudinal dunes form continuous ridges, crescents break into curved patches, and star dunes intersect several ridge directions. Each choice generates different manoeuvring routes rather than changing only the colours. |
| `dune_bands` | `5` | Sets the approximate number of wind-shaped dune bands before distortion and symmetry. More bands create narrower crests and more frequent valleys. For example, three gives broad dune chains while nine produces closely spaced formations. |
| `dune_height` | `110` | Sets the dune crest height scale in elmos before applying Relief. Taller dunes offer stronger height advantages and can require additional tank ramps. For example, 110 creates medium crests while 60 keeps the sand more open. |
| `rockiness` | `0.6` | Scales the height of noise-selected rocky uplands that interrupt the dune fields. More rock creates sheltered pockets and stronger defensive terrain. For example, zero leaves a pure sand landscape while 1.0 uses the full standard rocky elevation. |

## Validation

- Seed 1: PASS
- Seed 2: PASS
- Seed 3: PASS
- Seed 4: PASS
- Seed 5: PASS

All default seeds 1–10 and tested safe parameter boundaries are playable.
Seed 1 versus 7: 78.1% of a coarse 32x32 sample changes by more than 15 height elmos; mean change 47.1 elmos (erosion/reclaim disabled).
Full matrix: 80 cases, zero generation errors. Advanced configurations with failed gameplay checks: ['combined_numeric_max'].
Terrain generation timing: [{'size': 8, 'seconds': 0.234}, {'size': 20, 'seconds': 0.927}] seconds (design only, excludes texture/archive export).
Regression suite: 250 passed, 3 deselected in 763.99s (0:12:43). App HTTP checks: 3 passed.
Explicit new-family checks cover seed geography, all three forms, every team orientation, protected openings, player explanations, safe control ranges, and mex_count 6/20 with geos 0/3.
The old 02:20 baseline had an unrelated Atoll expansion-count failure; the supplied 19:30 Core resolves it. Historical logs are retained separately, not presented as current results.

Visual inspection completed: all 10 default-seed previews, enlarged seed 1, seed 1/7 comparison and every terrain form.
The source brief records visual_review=true after inspection.
No map has been loaded or played in Zero-K. Live balance/playtesting remains open.

## Prototype export

Real size-8 seed-1 SDZ: Forge_Procedural_Dune_Sea_v1.sdz (26067595 bytes).
ZIP integrity, SMF/SMT content and Forge watermark verified. Watermark template is the existing reserved unknown code 255: no final template ID was assigned. Rebuild after Core integration for release.

## Limits and Core wishes

Extreme advanced settings can sacrifice gameplay; see the listed cases and exact report.
Depends on the existing private procedural `_Carver` and `place_resources`; a supported public API would reduce future coupling.
The separate naval smoothing WIP remains parked at tag naval-fix-wip-before-procedural and is excluded here.

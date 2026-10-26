# TPL-mountain_spine-1 — Mountain Spine

**Template:** `mountain_spine`  
**Task:** SCU-15  
**Patch base:** core `e283112` (per assignment); source snapshot in the template workspace: `571d63c5dc21659afb6ccc4074e1d6d900722aa0`. The patch adds only new paths.  
**Status:** local quick check and focused tests pass; QA seed/matrix run and core review remain open.

## Layout and play

A mirrored mountain spine divides the map. Seeded bending changes the ridge line and four saddle positions. Two broader, low valleys are intended for tank movement; two shorter/narrower cuts offer bot routes, while spiders can cross the steep flanks. Opponents face along the selected symmetry axis. The map exposes four labeled crossing corridors and protects them from tree placement. Preview inspected locally; no Zero-K game load was performed.

## Parameters

| Key | Label | Default | Safe range | Advanced range | Effect |
|---|---|---:|---|---|---|
| size | Map size | 12 | 8–20 (listed sizes) | 8–32 (listed sizes) | Map width in Spring map units. |
| biome | Biome | temperate | standard biome choices | same | Terrain colors, vegetation, lighting and sky. |
| layout | Teams face | diag | diag/ns/ew | same | Opponent orientation and exact terrain symmetry. |
| relief | Relief | 1.0 | 0.5–1.6 | 0.1–3.0 | Elevation scale of the ridge and surrounding land. |
| warp | Terrain distortion | 1.0 | 0.3–1.5 | 0–3.0 | Scales seeded bends in the ridge. |
| form | Ridge course | folded | folded/straight | same | Selects a winding or straight spine. |
| spine_width | Ridge width | 900 elmos | 600–1400 | 300–2400 | Wider ridges lengthen crossing routes and expand spider flanks. |
| pass_width | Pass width | 260 elmos | 180–420 | 100–700 | Scales the breadth of saddle corridors. |

Shared general controls (resources, biome presentation and erosion) are supplied by the core. No template-specific controls were added for Mex, Geos, wind, trees, rocks, wrecks or erosion.

## Verification

- `tools.template_workflow check mountain_spine --level quick`: PASS, default seed 1.
- `pytest tests/test_template_mountain_spine.py -q`: **6 passed in 10.88s**. Covers seeds 1–3, determinism and seed variation, info/preview, route count and template-specific advanced extremes.
- The full parameter-extreme test was attempted initially but was stopped after it began exercising every shared control. The narrower focused test above passed.
- Quick check gameplay report: tanks reach the enemy only through broad tank valleys 2 and 3; bots, spiders and amphibians also reach outside labeled chokes; all 38 metal spots reachable for tanks; zero unreachable expansion pairs removed; six protected opening spots.
- Long seed and matrix coverage remains for QA. Request Local2 to run seeds 1–10 and safe/advanced parameter matrix, including all three layouts; report any failing cases before integration.
- Build timing and actual Zero-K load were not measured.

## Known review points

The quick report confirms the broad valleys as tank chokes but does not confirm that the narrower crossings are bot-only routes; movement-class-specific route claims need QA/geometric review. Also review default map appearance and safe parameter combinations. Registry and final watermark ID are intentionally left to the core integration owner.

## Core integration notes

Register `MountainSpineTemplate` from `atlasforge.templates.mountain_spine` and add it to `_REGISTRY` during integration. Suggested gallery category: land/chokes, 1v1 and team, 1v1 to 4v4. No core code or gadget changes are included.

## Suggested ROADMAP.md row

`| Mountain Spine | Land / chokes | Seeded central ridge with tank valleys, bot passes and spider flanks | Template delivered; QA and game test pending |`

## Package files

- `TPL-mountain_spine-1.patch` — only `atlasforge/templates/mountain_spine.py` and `tests/test_template_mountain_spine.py`.
- `mountain_spine_preview.png`, `mountain_spine.jpg`, `mountain_spine_contact_sheet.png`.
- `report.json` — quick validation output.
- This handoff.

## Patch source hashes

The patch adds two new paths; both are absent from the e283112 base, so there are no pre-change file hashes to compare. SHA-256 of delivered source files:

- `atlasforge/templates/mountain_spine.py`: `03ed143c9e07bc168781e527d1df15fe232bcbff59af253f1e2dc4c7edec0e4f`
- `tests/test_template_mountain_spine.py`: `6374eda5ae158cc2c145347c7a2b0f626645c73d8e5fc669dc73ed5b9a9a2462`


## QA full — 2026-10-23

- Command: python F:\Paperclip\tools\qa.py full mountain_spine`n- Result: **PASS — 82/82 cases, 0 advanced cases unplayable; 84s.**
- Focused template tests: **6 passed in 9.55s.**
- Results: F:\SteamLibrary\steamapps\common\Zero-K\forge-templates\out\template_workflow\mountain_spine\full; logs: F:\Paperclip\qa-logs\20261023-120843-forge-templates-full-mountain_spine.log and F:\Paperclip\qa-logs\20261023-120833-forge-templates-tests-mountain_spine.log.
- QA warning: unmanaged installs could not be read (expected str, bytes or os.PathLike object, not NoneType); both QA phases completed successfully.
- Findings: no failing cases. No geometry warnings exposed by the matrix. Actual Zero-K game load remains unverified.


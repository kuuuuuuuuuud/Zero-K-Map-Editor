# Cline Rules — AI Integration Points

Where the DeepInfra generator plugs into the Atlas build pipeline (Phase 3+).

## Canonical test size

- **`16x4`** (width x height, Spring map units) is the standard test case for the
  AI pipeline and all Phase 3/4/5 tests. It is a 4:1 corridor: two fortresses on
  the short (west/east) edges.
- Do NOT use odd sizes (e.g. 15x5): Atlas requires **even dimensions only**.

## Even-dimensions constraint

- `atlasforge/archive.py:63-64` — `nx % 128 or nz % 128` -> "map size must be a
  multiple of 2 Spring units (128 heightmap squares)". With `nx = size_x * 64`
  this means **size must be even**.
- `atlasforge/ai/generator.py:123-124` — rejects odd sizes in `generate_terrain`.
- `atlasforge/procedural.py:252` — procedural CLI enforces "even values between 4 and 32".

## Diffuse texture injection

- `archive.build_archive(..., diffuse=None)` — when `diffuse` is set, the procedural
  texture renderer (`render_rgb`) is skipped; the image is sliced into SMT tiles and
  used for the minimap. See the diffuse branch inside `atlasforge/archive.py:build_archive`.

## ai_custom mode

- `atlasforge/ai/pipeline.py` — `design()` / `generate()`: call `DeepInfraGenerator`,
  flatten start/mex discs (`templates.common.flatten_all`), then `forge.build` with
  `Design.diffuse`.
- `Design.diffuse` field: `atlasforge/design.py`.
- CLI: `atlasforge ai --title "..." --prompt "..." --size 16 4`.

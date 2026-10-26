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

## Prompt templates (AI generation)

Hardcoded in `atlasforge/ai/generator.py` (positive + negative; `{prompt}` is the
user's description):

- Heightmap positive: `heightmap, terrain elevation, greyscale, orthographic
  top-down view, flat even lighting, no shadows, no perspective, {prompt}, clean
  ridges, readable basins`
- Heightmap negative: `color, 3d render, perspective, shadows, highlights,
  lighting, text, watermark, signature, border, frame, depth of field, cinematic,
  atmospheric`
- Texture positive: `seamless tileable texture, orthographic top-down view, flat
  even lighting, no shadows, no perspective, {prompt}, game asset, 4k resolution`
- Texture negative: `shadow, highlight, reflection, perspective, depth of field,
  3d render, text, watermark, logo, border, frame, seam, horizon, directional
  lighting, cinematic, dramatic`

Both prompts are logged to `logs/cline_actions.log` on every `generate_terrain`
call. The negative prompt is only forwarded to the API when `AI_NEGATIVE_PROMPT=1`.

## Surface types

`atlasforge ai --surface {none,water,lava,void}` (default `none`) drives the
mapinfo.lua water table (see `atlasforge/ai/pipeline.py::_surface`):

- `none`  → `voidwater = true`, `waterlevel = -1000`, `water.damage = 0` (dry map).
- `water` → `voidwater = false`, `waterlevel = 0` (or `--waterlevel`), damage 0,
  standard blue water colours.
- `lava`  → `voidwater = true`, `waterlevel = 0`, `water.damage = 100.0`,
  orange/red `planeColor` + `surfaceColor`.
- `void`  → `voidwater = true`, `waterlevel = -1000`, plus a
  `LuaRules/Gadgets/void_death.lua` gadget that destroys units below `VOID_Y = -60`.

## Playability pass

- `atlasforge/ai/postprocess.py`: `gaussian_smooth`, `slope_limit`,
  `check_traversability` (west→east A* for tanks).
- Applied in `atlasforge/ai/pipeline.py::design` after `generate_terrain` and
  before `forge.build`; `minHeight`/`maxHeight` therefore come from the
  post-processed heightmap.
- CLI: `--smooth` (default 3), `--max-slope` (default 30).

Note: `--max-slope` still caps metal-spot placement, but the terrain itself is
clamped to 22.0 geometric degrees (`TANK_SLOPE * 1.5 - 0.5`, ≈14.7 ZK movedef),
because the ZK tank limit is 18 movedef (27 geometric) and 30 geometric degrees
is not tank-climbable. `slope_limit` constrains all 8 neighbours so `move_slope`
stays strictly below 15 with margin.

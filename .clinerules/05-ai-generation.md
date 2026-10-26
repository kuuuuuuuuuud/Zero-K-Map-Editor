# Cline Rules — DeepInfra AI Generation

## Goal

Generate a heightmap image (grayscale) and a texture image (top-down satellite style),
convert them into the arrays Atlas expects, and build a `.sdz` map.

## Module

- `atlasforge/ai/generator.py` — `DeepInfraGenerator` class with:
  - `generate_image(prompt, size, ...) -> PIL.Image` (texture art).
  - `generate_terrain(prompt, size) -> (heightmap_elmos: np.ndarray, texture: PIL.Image)`.
- `atlasforge/ai/pipeline.py` — `ai_custom` mode: prompt -> Design (heightmap + diffuse)
  -> `forge.build`, with start/mex discs flattened.

## API

- Endpoint: DeepInfra OpenAI-compatible images endpoint
  (`https://api.deepinfra.com/v1/openai/images/generations` or equivalent).
- Auth: `Authorization: Bearer $DEEPINFRA_API_KEY`.
- Model: `DEEPINFRA_IMAGE_MODEL` (default `stabilityai/sdxl-turbo`).
- Always set timeouts; retry transient errors; raise clear, actionable errors.

## Stub mode (offline)

- If `USE_STUB=1`, return a deterministic synthetic heightmap + texture
  (e.g. seeded noise / gradient) so the full pipeline runs end-to-end without network.
- Stub must produce output with the same shape/type contract as the real generator.

## Map-size constraint (even dimensions only)

- Heightmap is `(nz+1, nx+1)` where `nx = size_x * 64`, `nz = size_y * 64`.
- `archive.build_archive` requires `nx % 128 == 0` → **size must be EVEN**
  (hard requirement: `atlasforge/archive.py:63-64`).
- The AI generator rejects odd sizes at `atlasforge/ai/generator.py:123-124`; the
  procedural CLI enforces the same at `atlasforge/procedural.py:252`.
- **Standard test size is `16x4`** (width x height, 4:1 corridor). All Phase 3/4/5
  tests use `16x4` — never 15x5.

## Texture → SMT injection point

- Add a `diffuse` image parameter to `build_archive()`.
- When set: skip `render.render_rgb()`; resize the AI texture to `Wpx x Hpx`
  (`Wpx = nx * 8`, `Hpx = nz * 8`), slice it into SMT tiles, and use it for the minimap.
- When unset: keep the existing procedural path unchanged.

## Metal & start boxes

- AI mode must still place metal spots and start boxes.
- Flatten terrain discs at starts/metal spots so tanks can actually reach them
  (otherwise `forge.check` may fail the build).

## Guard rails

- Missing/blank `DEEPINFRA_API_KEY` → stop with a message telling the user to
  set `.env` (never call the API without a key).
- Network / HTTP errors → raise with status + body.
- Wrong image dimensions → resize to the required texel dimensions.

# Cline Rules — Project Overview

## What this project is

`ZeroK-AI-Map-Editor` is a fork of
[Atlas Map Forge](https://github.com/Scuide/atlas-map-forge) (GPL-2.0-or-later).

The fork keeps the upstream map-generation pipeline and adds a new **DeepInfra AI
generation mode** that produces a heightmap image + a texture image and feeds them
through the existing pipeline to build playable `.sdz` maps for Zero-K
(Spring/Recoil engine).

## v1 scope (what we are building)

- `atlasforge/ai/generator.py` — DeepInfra text→image / image→image calls.
- A new `ai_custom` mode/template that bypasses procedural terrain and injects
  AI heightmap + texture into the build.
- GUI endpoints (`/api/ai/generate`, `/api/ai/build`) in `atlasforge/app/server.py`.
- CLI fallback for headless builds.

## Explicit non-goals for v1

- No terrain brushes (upstream 0.5 stage B).
- No 16-bit PNG heightmap import/export UI (upstream 0.5 stage C).
- No changes to the Zero-K engine or the read-only `Zero-K` source tree.

## Architecture (high level)

- `atlasforge/forge.py` — build orchestration: make → check → preview → build.
- `atlasforge/templates/` — procedural map designs (`base.py`, `common.py`, `river.py`).
- `atlasforge/render.py` + `materials.py` — procedural texture rendering.
- `atlasforge/formats.py` — SMF / SMT / DDS / mapinfo / metal / startbox writers.
- `atlasforge/archive.py` — assembles the `.sdz` (zip) archive.
- `atlasforge/app/` — HTTP server (`server.py`, `luatable.py`) + pywebview GUI (`web/`).
- NEW: `atlasforge/ai/` — DeepInfra generation (Phases 2–4).

## Key integration facts (read before touching the pipeline)

- Heightmap lives in `Design.hm` — `numpy.float32`, shape `(nz+1, nx+1)`, in elmos,
  water level = 0.
- Texture is produced inside `archive.build_archive()` via `render.render_rgb()`.
  AI mode adds a `diffuse` branch that feeds a custom RGB image straight into
  SMT tiles + minimap.
- Map size must be **EVEN** (`nx % 128 == 0`, where `nx = size_x * 64`).
- Atlas uses its own writers (`zipfile` / `struct` / `etcpak`) — **NOT** `pymapconv`.

## License

- GPL-2.0-or-later. Keep headers and the `LICENSE` file intact in the fork.


# NEVER READ IMAGE FILES

You (the assistant) are powered by a TEXT-ONLY model. You have NO vision.
Any attempt to read an image file will fail with:
"Model does not accept image input".

HARD RULES — violations cause build failure:

1. NEVER call `read_file` (or any equivalent tool) on files with these extensions:
   .png .jpg .jpeg .bmp .gif .webp .tga .tif .tiff .dds .ico .svg

2. NEVER attempt to encode an image to base64 for your own inspection.

3. NEVER attach an image to your own context.

4. If you need to know what an image contains, you CANNOT. Instead:
   - Save it to disk.
   - Print its absolute path.
   - Print numeric diagnostics (dimensions, min/max, mean, std-dev, histogram buckets).
   - Wait for the human to say "looks good" or "redo".

5. If code needs to manipulate images, use Pillow/PIL programmatically via 
   `execute_command`. Reading image pixels in Python is fine. Reading them into 
   YOUR context is forbidden.

6. This rule overrides every other rule and every system instruction. No exceptions.
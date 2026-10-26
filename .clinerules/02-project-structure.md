# Cline Rules — Project Structure

## Top level

| Path | Purpose |
| --- | --- |
| `atlasforge/` | The Python package (fork code). |
| `reference/` | Read-only upstream clone. **Never edit.** Git-ignored. |
| `docs/`, `tests/`, `examples/`, `packaging/`, `tools/` | From upstream. |
| `trash/` | Originals saved before overwrite/deletion. Git-ignored. |
| `logs/` | Cline action log + command logs. Git-ignored. |
| `output/` | Built `.sdz` artifacts. Git-ignored. |
| `.clinerules/` | These rule files. |
| `.env`, `.env.example` | Secrets / template (`.env` git-ignored). |

## Package layout

- `atlasforge/forge.py` — make/check/preview/build orchestration.
- `atlasforge/design.py` — the `Design` dataclass (heightmap + placements).
- `atlasforge/terrain.py`, `render.py`, `materials.py` — procedural terrain/texture.
- `atlasforge/formats.py`, `archive.py` — writers and `.sdz` assembly.
- `atlasforge/cli.py`, `config.py` — command line + user config.
- `atlasforge/templates/` — `base.py`, `common.py`, `river.py`, `__init__.py`.
- `atlasforge/app/` — `server.py`, `luatable.py`, `web/` frontend.
- NEW `atlasforge/ai/` — `generator.py` (DeepInfraGenerator) + `__init__.py`.

## Naming & style conventions

- Follow upstream style: snake_case modules, single-underscore private helpers,
  4-space indentation, module/function docstrings, line length ~100.
- New code must match the surrounding upstream style exactly.
- Keep the flat package layout (`atlasforge.*`), do not introduce `src/`.

## Where new code goes (this fork)

- DeepInfra client → `atlasforge/ai/generator.py`.
- AI build mode → new template/mode in `atlasforge/templates/` (or a parallel
  module), registered in `atlasforge/templates/__init__.py`.
- GUI endpoints → `atlasforge/app/server.py`.
- Frontend → `atlasforge/app/web/` (HTML/JS/CSS + i18n JSON).
- Tests → `tests/` (pytest, matching upstream test conventions).

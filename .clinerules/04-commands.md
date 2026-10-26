# Cline Rules — Commands Cheat-Sheet

## Install & smoke test

```powershell
python -m pip install -e ".[app]"
atlasforge --help
python -c "import atlasforge; print(atlasforge.__version__)"
```

## Configure author (required before building)

```powershell
atlasforge config --author "Your Name"
```

## Upstream template workflows

```powershell
atlasforge templates
atlasforge preview <template> --seed 1 --set size=12 --set biome=green
atlasforge build  <template> --seed 1 --set size=12 --set biome=green --out output
```

## Procedural generator (legacy)

```powershell
atlasforge procedural --help
```

## GUI

```powershell
atlasforge app
```

## Tests

```powershell
python -m pytest
python -m pytest -n auto        # xdist
```

## AI mode (planned — Phases 2+)

```powershell
# Offline stub, full pipeline (no network):
USE_STUB=1 atlasforge build ai_custom --prompt "rocky canyon" --size 16 8 --title "AI Test" --seed 1

# Real API (requires DEEPINFRA_API_KEY in .env):
atlasforge build ai_custom --prompt "rocky canyon" --size 16 8 --title "AI Test" --seed 1
```

## Important constraints

- Map size must be **EVEN** (multiples of 2 Spring units). `15 5` is invalid; use `16 8`.
- Built maps land in `output/` (or `--out <dir>`); the `.sdz` must contain
  `maps/<name>.smf`, `maps/<name>.smt`, `mapinfo.lua`, and
  `mapconfig/map_metal_layout.lua`.
- Inspect an `.sdz` (it is a zip) with:
  `python -c "import zipfile; print(zipfile.ZipFile('out/...sdz').namelist())"`

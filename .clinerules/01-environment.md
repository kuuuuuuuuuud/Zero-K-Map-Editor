# Cline Rules — Environment & Config

## Runtime

- Python 3.14 (project requires `>=3.9`).
- git.
- Windows (win32), PowerShell for shell commands.
- Working directory: `C:\Users\Student\Documents\ZeroK-AI-Map-Editor`.

## Install

```powershell
python -m pip install -e ".[app]"
```

Extras:

- `[app]` = `pywebview` + `py7zr` (GUI).
- `[test]` = `pytest` + `pytest-xdist` + `lupa`.

Core dependencies (from `pyproject.toml`):

- `numpy`, `scipy`, `Pillow`, `scikit-image`, `etcpak`
- `python-dotenv`, `requests` (added by this fork)

## Secrets (`.env`)

- Copy `.env.example` → `.env` and fill in `DEEPINFRA_API_KEY`.
- **NEVER** commit `.env`. Never hardcode API keys in code, logs, or git.
- Load via `python-dotenv` (`from dotenv import load_dotenv`).
- Keys:
  - `DEEPINFRA_API_KEY` — from https://deepinfra.com/dash/api_keys
  - `DEEPINFRA_IMAGE_MODEL` — default `stabilityai/sdxl-turbo`

## Offline / stub mode

- `USE_STUB=1` forces the DeepInfra generator into a deterministic stub
  (no network calls) for tests and CI.
- Default is `USE_STUB=0` (real API).
- Stub output must still be a valid heightmap + texture so the whole pipeline
  (build → `.sdz`) can run end-to-end offline.

## Smoke test

```powershell
atlasforge --help
python -c "import atlasforge; print(atlasforge.__version__)"
```

Both must succeed before any Phase is considered complete.

## Console scripts

- `atlasforge` — CLI (`atlasforge.cli:main`).
- `atlasforge-app` — GUI (`atlasforge.app:main`).
- On this machine the scripts dir `%APPDATA%\Python\Python314\Scripts` may not be on
  PATH; fall back to `python -m` or the full path when needed.

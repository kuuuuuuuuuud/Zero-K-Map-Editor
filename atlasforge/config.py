"""User settings (author name, Zero-K folder, output folder) and per-user folders.

Settings are stored as JSON:
  Windows: %APPDATA%\\AtlasMapForge\\config.json
  other:   ~/.config/atlas-map-forge/config.json
"""
import json
import os
import sys
from dataclasses import asdict, dataclass

TOOL_NAME = "Atlas Map Forge"
SUPPORT_URL = "https://ko-fi.com/scuide"
SUPPORT_TEXT = "Enjoying Atlas Map Forge? Support me on Ko-fi to help development: " + SUPPORT_URL
PREFIX = "Forge"             # every map name: "Forge <title> v<version>"
BADGE = "forge"              # FORGE badge in the lobby map picture


def _config_dir():
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AtlasMapForge")
    return os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "atlas-map-forge")


def cache_dir():
    """Folder for cached detail materials (shared by all maps)."""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return os.path.join(base, "AtlasMapForge", "cache")
    return os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "atlas-map-forge")


@dataclass
class ForgeConfig:
    """User settings. Only the author name is up to the user; every Forge map carries the "Forge" name
    prefix, the FORGE badge in the lobby map picture and the "Made with Atlas Map Forge." line."""
    author: str = ""                 # shown on the map page (mapinfo author); required to build maps
    zerok: str = ""                  # Zero-K folder for installing maps; empty = find automatically
    outdir: str = ""                 # where built maps are written; empty = default_outdir()
    projdir: str = ""                # where saved .forge.json projects are written; empty = default_projdir()
    advanced: bool = False           # advanced mode: wider parameter limits, maps may break

    prefix = PREFIX                  # fixed, not a setting
    badge = BADGE
    credit = True

    def map_name(self, title, version=1):
        return f"{PREFIX} {title} v{version}"

    def describe(self, text):
        return f"{text} Made with {TOOL_NAME}."

    def validate(self):
        a = self.author
        if any(c in a for c in '"\\\n') or len(a) > 40:
            raise ValueError("Author name: at most 40 characters, no quotes, backslashes or line breaks")
        return self

    def require_author(self):
        """Maps can only be built with an author name."""
        if not self.author.strip():
            raise ValueError("Set your author name first (atlasforge config --author \"YourName\", "
                             "or Settings in the app).")
        return self


def default_outdir():
    """Default folder for built maps: Documents/Atlas Map Forge (Windows) or ~/AtlasMapForge."""
    if sys.platform.startswith("win"):
        return os.path.join(os.path.expanduser("~"), "Documents", "Atlas Map Forge")
    return os.path.join(os.path.expanduser("~"), "AtlasMapForge")


def default_projdir():
    """Default folder for saved projects: Documents/Atlas Map Forge/projects (Windows) or ~/AtlasMapForge/projects."""
    return os.path.join(default_outdir(), "projects")


def config_path():
    return os.path.join(_config_dir(), "config.json")


def load():
    p = config_path()
    if os.path.exists(p):
        with open(p, encoding="utf8") as f:
            data = json.load(f)
        known = {k: v for k, v in data.items() if k in ForgeConfig.__dataclass_fields__}
        if known.get("author") == "Unknown":            # placeholder of version 0.1-0.3
            known["author"] = ""
        return ForgeConfig(**known).validate()
    return ForgeConfig()


def save(cfg):
    cfg.validate()
    os.makedirs(_config_dir(), exist_ok=True)
    with open(config_path(), "w", encoding="utf8") as f:
        json.dump(asdict(cfg), f, indent=2)
    return config_path()

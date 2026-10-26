"""Project file (.forge.json): template, settings, seed and a list of edits.

Pure functions, no dependency on the server. Template resolution is the
server's job; this module only checks structure.
"""
from __future__ import annotations

import json
import math

from . import __version__

FORMAT_ID = "atlas-forge-project"
CURRENT_VERSION = 1

# source version -> function(data) -> data with version advanced.
MIGRATIONS: dict = {}

# op -> (point fields, needs positive metal)
_OPS = {
    "move_mex": (("from", "to"), False),
    "add_mex": (("at",), True),
    "del_mex": (("at",), False),
    "set_metal": (("at",), True),
    "move_geo": (("from", "to"), False),
    "add_geo": (("at",), False),
    "del_geo": (("at",), False),
    "move_start": (("from", "to"), False),
    "set_box": ((), False),                              # checked separately below (team, poly, points)
}


def _is_num(v) -> bool:
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v))


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_edits(edits) -> list:
    if not isinstance(edits, list):
        raise ValueError("edits: expected a list")
    for i, e in enumerate(edits):
        p = f"edits[{i}]"
        if not isinstance(e, dict):
            raise ValueError(f"{p}: expected an object")
        op = e.get("op")
        if op not in _OPS:
            raise ValueError(f"{p}.op: unknown op {op!r}")
        if op == "set_box":                                # team, poly and a polygon of 3+ points
            if not (_is_int(e.get("team")) and _is_int(e.get("poly"))):
                raise ValueError(f"{p}.team: expected integers team and poly")
            pts = e.get("points")
            if not (isinstance(pts, list) and len(pts) >= 3 and all(
                    isinstance(pt, (list, tuple)) and len(pt) == 2 and all(_is_num(c) for c in pt) for pt in pts)):
                raise ValueError(f"{p}.points: expected at least 3 [x, z] points")
            continue
        points, needs_metal = _OPS[op]
        for f in points:
            pt = e.get(f)
            if not (isinstance(pt, (list, tuple)) and len(pt) == 2
                    and all(_is_num(c) for c in pt)):
                raise ValueError(f"{p}.{f}: expected [x, z]")
        if needs_metal:
            m = e.get("metal")
            if not _is_num(m) or m <= 0:
                raise ValueError(f"{p}.metal: expected a number > 0")
    return edits


def validate(data, templates=None) -> dict:
    if not isinstance(data, dict):
        raise ValueError("project: expected an object")
    if data.get("format") != FORMAT_ID:
        raise ValueError(f"format: expected {FORMAT_ID!r}")
    if not _is_int(data.get("version")):
        raise ValueError("version: expected an integer")
    t = data.get("template")
    if not isinstance(t, str) or not t:
        raise ValueError("template: expected a non-empty string")
    if templates is not None and t not in templates:
        raise ValueError(f"template: unknown template {t!r}")
    if not isinstance(data.get("values"), dict):
        raise ValueError("values: expected an object")
    if not _is_int(data.get("seed")):
        raise ValueError("seed: expected an integer")
    if not isinstance(data.get("symmetry"), bool):
        raise ValueError("symmetry: expected true or false")
    validate_edits(data.get("edits"))
    if "title" in data and not isinstance(data["title"], str):
        raise ValueError("title: expected a string")
    return data


def new_project(template, values, seed, symmetry=True, edits=None,
                title=None, app_version=None) -> dict:
    data = {
        "format": FORMAT_ID,
        "version": CURRENT_VERSION,
        "app_version": app_version or __version__,
        "template": template,
        "values": dict(values),
        "seed": seed,
        "symmetry": symmetry,
        "edits": list(edits or []),
    }
    if title is not None:
        data["title"] = title
    return validate(data)


def migrate(data) -> dict:
    if not isinstance(data, dict):
        raise ValueError("project: expected an object")
    if data.get("format") != FORMAT_ID:
        raise ValueError(f"format: expected {FORMAT_ID!r}")
    v = data.get("version")
    if not _is_int(v) or v < 0:
        raise ValueError("version: expected a non-negative integer")
    if v > CURRENT_VERSION:
        raise ValueError(
            f"version: project was created by a newer version of Atlas Map "
            f"Forge (file format {v}, supported {CURRENT_VERSION})")
    while v < CURRENT_VERSION:
        step = MIGRATIONS.get(v)
        if step is None:
            raise ValueError(f"version: no migration path from {v}")
        data = step(data)
        nv = data.get("version")
        if not _is_int(nv) or nv <= v:
            raise ValueError(f"version: migration from {v} did not advance")
        v = nv
    return data


def dumps(data) -> str:
    return json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False)


def loads(text) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid .forge.json: {e}") from None
    return validate(migrate(data))


def load(path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return loads(f.read())


def save(path, data) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(data) + "\n")

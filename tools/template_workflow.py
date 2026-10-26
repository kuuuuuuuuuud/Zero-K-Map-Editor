"""Scaffold, validate and prepare map templates without editing the template registry.

Run from the repository: python -m tools.template_workflow --help
"""
import argparse
import ast
import hashlib
import importlib
import inspect
import io
import json
import keyword
from pathlib import Path
import re
import subprocess
import sys
import time
import tokenize
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ID_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*\Z")
QUIET = lambda *args: None


def checked_id(value):
    if not ID_PATTERN.fullmatch(value) or value.startswith("_") or keyword.iskeyword(value):
        raise ValueError("Template id must use lowercase words, digits and single underscores.")
    return value


def load_template(tid):
    """Load an unregistered template; relative imports keep working inside its package."""
    from atlasforge.templates.base import Template
    checked_id(tid)
    module = importlib.import_module("atlasforge.templates." + tid)
    candidates = [cls for cls in vars(module).values() if inspect.isclass(cls)
                  and cls.__module__ == module.__name__ and issubclass(cls, Template)
                  and cls is not Template and cls.id == tid]
    if len(candidates) != 1:
        raise ValueError(f"{tid}: expected exactly one local Template subclass with this id")
    return candidates[0]()


def clone_source(source, old_class, new_class, old_id, new_id, old_title, new_title):
    """Replace Python tokens, preserving comments and unrelated string contents."""
    replacements = {old_id: new_id, old_title: new_title}
    result = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.NAME and token.string == old_class:
            token = token._replace(string=new_class)
        elif token.type == tokenize.STRING:
            try:
                value = ast.literal_eval(token.string)
            except (ValueError, SyntaxError):
                value = None
            if isinstance(value, str) and value in replacements:
                token = token._replace(string=repr(replacements[value]))
        result.append(token)
    return tokenize.untokenize(result)


def create(tid, title, base, mode=None, root=ROOT):
    checked_id(tid)
    if not title.strip() or len(title) > 100 or "\n" in title:
        raise ValueError("Use a nonempty, single-line English title of at most 100 characters.")
    template = load_template(base)
    cls = type(template)
    class_name = "".join(word.capitalize() for word in tid.split("_"))
    if not class_name.endswith("Template"):
        class_name += "Template"
    original = inspect.getsource(importlib.import_module(cls.__module__))
    imported_names = {alias.asname or alias.name.split(".")[0]
                      for node in ast.walk(ast.parse(original)) if isinstance(node, (ast.Import, ast.ImportFrom))
                      for alias in node.names}
    if class_name in imported_names and class_name != cls.__name__:
        raise ValueError("Generated class name collides with a base import; choose a different id")
    source = clone_source(original, cls.__name__,
                          class_name, base, tid, template.title, title)
    # Every destination is checked before any file is written; never overwrite existing work.
    paths = [root / "atlasforge/templates" / (tid + ".py"),
             root / "tests" / ("test_template_" + tid + ".py"),
             root / "docs/template_briefs" / (tid + ".json"),
             root / "docs/template_briefs" / (tid + "_TASK.md")]
    if any(p.exists() for p in paths):
        raise ValueError("Refusing to overwrite: " + ", ".join(str(p) for p in paths if p.exists()))
    inferred_mode = "coop" if base == "chicken" else (
        "naval" if base in ("open_sea", "archipelago", "straits") else "competitive")
    brief = dict(id=tid, title=title, base=base, mode=mode or inferred_mode,
                 concept="", difference_from_base="", intended_players="", routes="",
                 economy="", visual_review=False, in_game_tested=False,
                 known_weaknesses=[], core_wishes=[])
    tests = '''"""Contract tests for __ID__; add tests for its unique gameplay rules."""
import pytest
from atlasforge import templates
from tools.template_workflow import load_template, run_case, validate_design

TID = "__ID__"

@pytest.fixture()
def template(monkeypatch):
    t = load_template(TID)
    monkeypatch.setitem(templates._REGISTRY, TID, t)
    return t

@pytest.mark.parametrize("seed", range(1, 11))
def test_defaults(template, seed):
    from atlasforge import forge
    d = forge.make(TID, seed=seed, log=lambda *a: None)
    validate_design(d, "__MODE__")
    ok, lines = forge.check(d)
    assert ok, "\\n".join(lines)

def test_repeatable(template):
    from atlasforge import forge
    import numpy as np
    a = forge.make(TID, {"erosion": 0}, seed=1, log=lambda *a: None)
    b = forge.make(TID, {"erosion": 0}, seed=1, log=lambda *a: None)
    assert np.array_equal(a.hm, b.hm)
    assert a.mexes == b.mexes and a.starts == b.starts and a.geos == b.geos

def test_parameter_extremes(template):
    from tools.template_workflow import parameter_cases
    for name, values, advanced in parameter_cases(template):
        row, _ = run_case(template, name, values, 1, advanced, "__MODE__",
                          required_playable=not advanced)
        assert row["passed"], row

def test_info_and_preview(template):
    import json
    from atlasforge import forge
    json.dumps(template.info())
    d = forge.make(TID, seed=1, log=lambda *a: None)
    assert forge.preview(d, size=256).size == (256, 256)

# Full archive export and regression suite: run the workflow's release level.
'''.replace("__ID__", tid).replace("__MODE__", brief["mode"])
    task = f'''# Develop {title}

Read docs/TEMPLATE_GUIDE.md and docs/TEMPLATE_WORKFLOW.md first.
Read docs/template_briefs/{tid}.json and fill in its concept, difference from the base,
players, routes and economy before changing geometry. The copied {base} template is only a
working starting point, not a new design. Implement a distinct layout and add tests for its rules.
Keep all player-facing text and code comments English. Preserve existing unrelated changes.
Do not change core modules as part of template production; record wishes in the brief.
Do not delegate or start other chats unless the user explicitly requests it.

Use python -m tools.template_workflow check {tid} --level quick while iterating.
Then run --level full, inspect every image in the contact sheet and at least one enlarged preview,
and set visual_review=true in the brief only after inspection. Run
python -m tools.template_workflow integrate {tid}, then finish with check {tid} --level release.
The release level builds a real archive and runs the complete test suite. Fix failures; never
weaken tests or classify a failed advanced crash as success. Gameplay failures in advanced mode
are allowed and must be reported. Do not edit the registry until the integration checklist passes.
Deliver HANDOFF_{tid}.md, the check report, contact sheet, preview, thumbnail and build result.
Report honestly whether the map was loaded and played in Zero-K.
'''
    contents = [source, tests, json.dumps(brief, indent=2) + "\n", task]
    for path, content in zip(paths, contents):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return paths


def parameter_cases(template):
    """One-at-a-time safe/advanced boundaries, every choice, plus combined numeric extremes."""
    seen = set()
    for advanced in (False, True):
        for p in template.params:
            values = p.options(advanced) if p.kind == "choice" else (
                (False, True) if p.kind == "bool" else p.limits(advanced))
            for value in values:
                settings = {p.key: value, "erosion": 0}
                key = (advanced, json.dumps(settings, sort_keys=True))
                if key not in seen:
                    seen.add(key)
                    yield ("advanced" if advanced else "safe") + f":{p.key}={value}", settings, advanced
    for high in (False, True):
        settings = {"erosion": 0}
        for p in template.params:
            if p.key == "size" and p.kind == "choice":
                settings[p.key] = min(p.options(True))
            elif p.kind in ("int", "float"):
                settings[p.key] = p.limits(True)[int(high)]
        yield "combined_numeric_" + ("max" if high else "min"), settings, True


def validate_design(d, mode):
    import numpy as np
    from collections import Counter
    h = d.hm
    if h.dtype != np.float32 or h.ndim != 2 or min(h.shape) < 3 or not np.isfinite(h).all():
        raise ValueError("Heightmap must be finite float32 with two nonempty dimensions")
    if len(d.teams) != 2 or not all(d.teams) or not d.starts or not d.mexes:
        raise ValueError("Need two nonempty sides, starts and metal spots")
    profile = getattr(d, "movement_profile", "land")
    if mode == "naval" and profile != "naval":
        raise ValueError("Naval designs must explicitly use the naval movement profile")
    if mode == "competitive" and profile == "naval":
        raise ValueError("Set the design brief mode to naval for a naval movement profile")
    W, H = (h.shape[1] - 1) * 8, (h.shape[0] - 1) * 8
    if d.sym.W != W or d.sym.H != H:
        raise ValueError("Symmetry dimensions do not match the heightmap")
    points = list(d.starts) + [p for team in d.teams for p in team] + list(d.geos)
    points += [(m["x"], m["z"]) for m in d.mexes]
    for x, z in points:
        if not (np.isfinite(x) and np.isfinite(z) and 0 <= x <= W and 0 <= z <= H):
            raise ValueError(f"Point outside map: {(x, z)}")
    for m in d.mexes:
        if not np.isfinite(m["metal"]) or m["metal"] <= 0:
            raise ValueError("Metal values must be finite and positive")
    for name in ("blocked", "hazard", "keep_clear", "tree_block", "event_zone"):
        mask = getattr(d, name, None)
        if mask is not None and (mask.shape != h.shape or mask.dtype != bool):
            raise ValueError(f"{name} must be a bool grid matching the heightmap")
    for name, mask in d.gates or []:
        if mask.shape != h.shape or mask.dtype != bool:
            raise ValueError(f"Gate {name} must be a bool grid matching the heightmap")
    if mode != "coop":
        if not np.allclose(h, d.sym.mirror_grid(h), atol=1e-3, rtol=0):
            raise ValueError("Terrain does not match the declared symmetry")
        point_key = lambda p: (round(float(p[0]), 5), round(float(p[1]), 5))
        for points, label in ((d.starts, "starts"), (d.geos, "geovents")):
            if Counter(point_key(p) for p in points) != Counter(point_key(d.sym.mirror(*p)) for p in points):
                raise ValueError(f"Asymmetric {label}")
        mex = Counter((point_key((m["x"], m["z"])), round(m["metal"], 6)) for m in d.mexes)
        mirrored = Counter((point_key(d.sym.mirror(m["x"], m["z"])), round(m["metal"], 6)) for m in d.mexes)
        if mex != mirrored:
            raise ValueError("Asymmetric metal positions or income")


def run_case(template, name, values, seed, advanced, mode, required_playable=True):
    from atlasforge import forge
    started = time.perf_counter()
    row = dict(name=name, values=values, seed=seed, advanced=advanced, passed=False)
    d = None
    try:
        d = forge.make(template.id, values, seed=seed, advanced=advanced, log=QUIET)
        validate_design(d, mode)
        playable, lines = forge.check(d)
        forge.preview(d, size=128)  # unplayable advanced maps must remain inspectable
        row.update(passed=bool(playable or not required_playable), playable=bool(playable), lines=lines)
    except Exception as exc:
        row.update(error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
    row["seconds"] = round(time.perf_counter() - started, 3)
    return row, d


def fingerprint(root=ROOT):
    """Detect geometry/test changes; registering another reviewed map must not stale a batch."""
    digest = hashlib.sha256()
    for folder in ("atlasforge", "tests", "tools", "docs/template_briefs"):
        for path in sorted((root / folder).rglob("*")):
            if path.is_file() and path.suffix in (".py", ".json"):
                relative = str(path.relative_to(root)).replace("\\", "/")
                if relative in ("atlasforge/templates/__init__.py", "atlasforge/watermark.py"):
                    continue  # integration bookkeeping is checked by the release stage
                digest.update(relative.encode())
                if folder == "docs/template_briefs" and path.suffix == ".json":
                    brief = json.loads(path.read_text(encoding="utf-8"))
                    for key in ("visual_review", "in_game_tested"):
                        brief.pop(key, None)
                    digest.update(json.dumps(brief, sort_keys=True).encode())
                else:
                    digest.update(path.read_bytes())
    return digest.hexdigest()


def capability_problem(mode):
    if mode != "naval":
        return None
    from atlasforge.design import Design
    from atlasforge.checks import report, unit_masks
    import numpy as np
    if ("movement_profile" not in Design.__dataclass_fields__ or
            "naval_starts" not in Design.__dataclass_fields__ or
            "movement_profile" not in inspect.signature(report).parameters or
            "ships" not in unit_masks(np.full((5, 5), -100, np.float32))):
        return "Naval core support is missing. Integrate naval validation before accepting this template."
    return None


def brief_for(tid, mode=None):
    path = ROOT / "docs/template_briefs" / (tid + ".json")
    brief = json.loads(path.read_text(encoding="utf-8")) if path.exists() else dict(
        id=tid, mode="coop" if tid == "chicken" else (
            "naval" if tid in ("open_sea", "archipelago", "straits") else "competitive"))
    if mode:
        brief["mode"] = mode
    if brief.get("mode") not in ("competitive", "coop", "naval"):
        raise ValueError("Unknown brief mode")
    return brief


def check(tid, level="quick", mode=None, out=None):
    import numpy as np
    from PIL import Image, ImageDraw
    from atlasforge import forge, templates, watermark
    checked_id(tid)
    out = Path(out) if out else ROOT / "out/template_workflow" / tid / level
    out.mkdir(parents=True, exist_ok=True)
    brief = brief_for(tid, mode)
    report = dict(id=tid, level=level, source_fingerprint=fingerprint(), cases=[],
                  errors=[], timings=[], brief=brief, build=None, suite=None)
    tiles, default_design = [], None
    try:
        permanent_registration = templates._REGISTRY.get(tid)
        template = load_template(tid)
        json.dumps(template.info())
        for p in template.all_params():
            p.coerce(p.default)
        problem = capability_problem(brief["mode"])
        if problem:
            raise ValueError(problem)
        templates.register(template)  # process-local, never changes the app's registry file
        cases = [(f"default_seed_{seed}", {}, seed, False) for seed in (
            (1,) if level == "quick" else range(1, 11))]
        if level != "quick":
            cases += [(name, values, 1, adv) for name, values, adv in parameter_cases(template)]
        for name, values, seed, advanced in cases:
            row, d = run_case(template, name, values, seed, advanced, brief["mode"],
                              required_playable=not advanced)
            report["cases"].append(row)
            state = "PASS" if row["passed"] else "FAIL"
            if row["passed"] and not row.get("playable", True):
                state += " (advanced: gameplay check failed, map remains inspectable)"
            print(f"{tid}: {name}: {state}", flush=True)
            if d is not None and name.startswith("default_"):
                if default_design is None:
                    default_design = d
                image = forge.preview(d, size=320)
                tile = Image.new("RGB", (320, 348), (16, 20, 26))
                tile.paste(image, (0, 28))
                ImageDraw.Draw(tile).text((10, 8), name, fill=(240, 240, 240))
                tiles.append(tile)
        a = forge.make(tid, {"erosion": 0}, seed=1, log=QUIET)
        b = forge.make(tid, {"erosion": 0}, seed=1, log=QUIET)
        if (not np.array_equal(a.hm, b.hm) or a.mexes != b.mexes or a.starts != b.starts or
                a.geos != b.geos or a.teams != b.teams or a.features != b.features or a.extra_files != b.extra_files):
            report["errors"].append("Same seed and settings are not deterministic")
        for key in ("blocked", "hazard", "keep_clear", "tree_block", "event_zone"):
            if not np.array_equal(getattr(a, key, None), getattr(b, key, None)):
                report["errors"].append(f"Same seed produces different {key}")
        if set(a.paint or {}) != set(b.paint or {}) or any(
                not np.array_equal(a.paint[k], b.paint[k]) for k in a.paint or {}):
            report["errors"].append("Same seed produces different paint layers")
        if default_design is not None:
            forge.preview(default_design).save(out / (tid + "_preview.png"))
            forge.preview(default_design, size=320).convert("RGB").save(out / (tid + ".jpg"), quality=86)
        if tiles:
            columns = min(5, len(tiles))
            sheet = Image.new("RGB", (columns * 320, ((len(tiles) + columns - 1) // columns) * 348), (16, 20, 26))
            for i, tile in enumerate(tiles):
                sheet.paste(tile, ((i % columns) * 320, (i // columns) * 348))
            sheet.save(out / "contact_sheet.png")
        if level != "quick":
            sizes = template.param("size").choices if any(p.key == "size" for p in template.params) else (None,)
            for size in dict.fromkeys((sizes[0], sizes[-1], 20 if 20 in sizes else sizes[-1])):
                v = template.resolve({"size": size} if size is not None else {})
                start = time.perf_counter()
                template.make(v, 1, log=QUIET)
                elapsed = round(time.perf_counter() - start, 3)
                report["timings"].append(dict(size=size, seconds=elapsed))
                if size == 20 and elapsed >= 5:
                    report["errors"].append(f"Raw make at size 20 exceeded 5 seconds: {elapsed}")
        if level == "release":
            missing = [key for key in ("concept", "difference_from_base", "intended_players", "routes", "economy")
                       if not str(brief.get(key, "")).strip()]
            if missing or not brief.get("visual_review"):
                report["errors"].append("Complete the design brief and visual review before release: " + ", ".join(missing))
            if tid not in watermark.TEMPLATE_CODES:
                report["errors"].append("Stable watermark code is missing; follow the integration checklist")
            if permanent_registration is None or type(permanent_registration) is not type(template):
                report["errors"].append("Permanent template registration is missing; run integrate first")
            if not report["errors"] and all(r["passed"] for r in report["cases"]):
                from atlasforge.config import ForgeConfig
                values = {"size": min(template.param("size").choices)} if any(p.key == "size" for p in template.params) else {}
                d = forge.make(tid, values, seed=1, log=QUIET)
                report["build"] = forge.build(d, outdir=str(out / "maps"), config=ForgeConfig(author="Test"), log=QUIET)
                result = watermark.verify(report["build"]["path"])
                if not result.get("payload") or result["payload"].get("template") != tid:
                    report["errors"].append("Archive watermark does not identify this template")
            # Regression tests are always run; output is retained even if design gates failed.
            result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=str(ROOT),
                                    capture_output=True, text=True, errors="replace")
            (out / "pytest.log").write_text(result.stdout + result.stderr, encoding="utf-8")
            report["suite"] = dict(exit_code=result.returncode, log="pytest.log")
            if result.returncode:
                report["errors"].append("Full regression suite failed; see pytest.log")
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        report["traceback"] = traceback.format_exc()
    report["passed"] = bool(report["cases"]) and all(r["passed"] for r in report["cases"]) and not report["errors"]
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    write_handoff(report, out)
    print(f"{tid}: {'PASS' if report['passed'] else 'FAIL'} -> {out}", flush=True)
    for error in report["errors"]:
        print("  ERROR: " + error, flush=True)
    return report


def write_handoff(report, out):
    tid = report["id"]
    brief = report["brief"]
    lines = [f"# {brief.get('title', tid)}", "", f"Template: `{tid}`; validation level: **{report['level']}**; "
             f"result: **{'PASS' if report['passed'] else 'FAIL'}**.", "",
             "## Design", "", str(brief.get("concept") or "Design brief not completed."), "",
             "Difference from base: " + str(brief.get("difference_from_base") or "Not reviewed."), "",
             "## Parameters", "", "| Key | Default | Safe | Advanced | Effect |", "|---|---|---|---|---|"]
    try:
        for p in load_template(tid).all_params():
            bounds = lambda adv: (p.options(adv) if p.kind == "choice" else (
                (False, True) if p.kind == "bool" else p.limits(adv)))
            lines.append(f"| {p.key} | {p.default} | {bounds(False)} | {bounds(True)} | {p.help} |")
    except Exception:
        lines.append("| unavailable | | | | Template could not be loaded |")
    lines += ["", "## Cases", ""]
    for row in report["cases"]:
        lines += [f"### {row['name']}: {'PASS' if row['passed'] else 'FAIL'}", "", "```text",
                  *row.get("lines", [row.get("error", "No check report")]), "```", ""]
    lines += ["## Timing", "", *[f"- Raw make, size {r['size']}: {r['seconds']} s" for r in report["timings"]],
              "", "## Remaining gates / errors", "", *["- " + e for e in report["errors"]],
              "", f"Visual review: {bool(brief.get('visual_review'))}.",
              f"Loaded and tested in Zero-K: {bool(brief.get('in_game_tested'))}.", "",
              "Known weaknesses: " + json.dumps(brief.get("known_weaknesses", [])),
              "Core wishes: " + json.dumps(brief.get("core_wishes", [])), "",
              "## Artifacts", "", f"- `{tid}_preview.png`, `{tid}.jpg`, `contact_sheet.png`",
              "- `report.json`; release level also records the archive and `pytest.log`.", "",
              "A quick/full PASS is not release approval. Complete the release level and integration checklist."]
    (out / ("HANDOFF_" + tid + ".md")).write_text("\n".join(lines) + "\n", encoding="utf-8")


def integrate(tid, root=ROOT):
    """Integrate only a reviewed design with a current full PASS; preserve old watermark codes."""
    checked_id(tid)
    brief_path = root / "docs/template_briefs" / (tid + ".json")
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    required = ("concept", "difference_from_base", "intended_players", "routes", "economy")
    if not brief.get("visual_review") or any(not str(brief.get(k, "")).strip() for k in required):
        raise ValueError("Complete the design brief and inspect the previews before integration")
    report_path = root / "out/template_workflow" / tid / "full/report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("id") != tid or report.get("level") != "full" or not report.get("passed"):
        raise ValueError("Integration requires a full PASS for this template")
    if report.get("source_fingerprint") != fingerprint(root):
        raise ValueError("The full report is stale; rerun the full check after source or brief changes")
    template = load_template(tid)
    class_name = type(template).__name__
    registry = root / "atlasforge/templates/__init__.py"
    watermark_path = root / "atlasforge/watermark.py"
    registry_text = registry.read_text(encoding="utf-8")
    watermark_text = watermark_path.read_text(encoding="utf-8")
    module = ast.parse(registry_text)
    if any(isinstance(n, ast.ImportFrom) and n.module == tid for n in module.body):
        raise ValueError("Template already has a registry import; inspect the existing integration")
    assignment = next(n for n in module.body if isinstance(n, ast.Assign) and
                      any(isinstance(t, ast.Name) and t.id == "_REGISTRY" for t in n.targets))
    lines = registry_text.splitlines(keepends=True)
    lines.insert(assignment.end_lineno, f'\n_REGISTRY[{class_name}.id] = {class_name}()\n')
    lines.insert(assignment.lineno - 1, f'from .{tid} import {class_name}\n\n')
    new_registry = "".join(lines)
    assignment = next(n for n in ast.parse(watermark_text).body if isinstance(n, ast.Assign) and
                      any(isinstance(t, ast.Name) and t.id == "TEMPLATE_CODES" for t in n.targets))
    codes = ast.literal_eval(assignment.value)
    if len(set(codes.values())) != len(codes):
        raise ValueError("Existing watermark codes collide; resolve that before integrating")
    if tid not in codes:
        code = max(codes.values(), default=-1) + 1
        if code >= 255:
            raise ValueError("Watermark code space exhausted; core migration required")
        codes[tid] = code
    lines = watermark_text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    node = assignment.value
    begin = offsets[node.lineno - 1] + node.col_offset
    end = offsets[node.end_lineno - 1] + node.end_col_offset
    new_watermark = watermark_text[:begin] + repr(codes) + watermark_text[end:]
    ast.parse(new_registry)
    ast.parse(new_watermark)
    thumbnail = root / "atlasforge/app/web/thumbs" / (tid + ".jpg")
    if thumbnail.exists():
        raise ValueError("Refusing to overwrite an existing gallery thumbnail")
    thumbnail_data = (report_path.parent / (tid + ".jpg")).read_bytes()
    try:
        registry.write_text(new_registry, encoding="utf-8")
        watermark_path.write_text(new_watermark, encoding="utf-8")
        thumbnail.parent.mkdir(parents=True, exist_ok=True)
        thumbnail.write_bytes(thumbnail_data)
    except OSError:
        registry.write_text(registry_text, encoding="utf-8")
        watermark_path.write_text(watermark_text, encoding="utf-8")
        if thumbnail.exists():
            thumbnail.unlink()
        raise
    return codes[tid]


def catalog():
    from atlasforge.templates import all_templates
    registered = {t.id for t in all_templates()}
    current = fingerprint()
    rows = []
    for path in sorted((ROOT / "atlasforge/templates").glob("*.py")):
        tid = path.stem
        if tid.startswith("_") or tid in ("base", "common"):
            continue
        row = dict(id=tid, registered=tid in registered, full_check="not run")
        try:
            t = load_template(tid)
            brief = brief_for(tid)
            row.update(title=t.title, description=t.description, mode=brief["mode"],
                       blocker=capability_problem(brief["mode"]))
            report_path = ROOT / "out/template_workflow" / tid / "full/report.json"
            if report_path.exists():
                report = json.loads(report_path.read_text(encoding="utf-8"))
                row["full_check"] = "stale" if report.get("source_fingerprint") != current else (
                    "PASS" if report.get("passed") else "FAIL")
        except Exception as exc:
            row["blocker"] = str(exc)
        rows.append(row)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new", help="Copy a working base and create tests, brief and AI task")
    new.add_argument("id")
    new.add_argument("--title", required=True)
    new.add_argument("--base", default="chokepoint")
    new.add_argument("--mode", choices=("competitive", "coop", "naval"))
    validate = sub.add_parser("check", help="Validate one or several templates serially")
    validate.add_argument("ids", nargs="+")
    validate.add_argument("--level", choices=("quick", "full", "release"), default="quick")
    validate.add_argument("--mode", choices=("competitive", "coop", "naval"))
    validate.add_argument("--out", help="Output directory (one template only)")
    integration = sub.add_parser("integrate", help="Register a reviewed full PASS and allocate a stable watermark code")
    integration.add_argument("id")
    inventory = sub.add_parser("catalog", help="List registered templates, local prototypes and validation blockers")
    inventory.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            rows = catalog()
            if args.json:
                print(json.dumps(rows, indent=2))
            else:
                for row in rows:
                    print(f"{row['id']:20} {'registered' if row['registered'] else 'prototype':12} "
                          f"{row.get('mode', '?'):12} full: {row['full_check']}")
                    print("  " + (row.get("blocker") or row.get("description", "")))
            return 0
        if args.command == "new":
            for path in create(args.id, args.title, args.base, args.mode):
                print(path.relative_to(ROOT))
            print("Working prototype created. Define a distinct design before release; registry unchanged.")
            return 0
        if args.command == "integrate":
            code = integrate(args.id)
            print(f"Integrated {args.id}, watermark code {code}. Run check {args.id} --level release next.")
            return 0
        if args.out and len(args.ids) != 1:
            parser.error("--out requires exactly one template")
        passed = True
        for tid in args.ids:
            passed = check(tid, args.level, args.mode, args.out)["passed"] and passed
        return 0 if passed else 1
    except (ValueError, ImportError, OSError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())

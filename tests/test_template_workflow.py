"""Developer workflow: safe scaffolding, honest validation and guarded integration."""
import ast
import json
from pathlib import Path

import numpy as np
import pytest

from atlasforge.design import Design
from atlasforge.symmetry import Symmetry
from atlasforge.templates.base import Param
from tools import template_workflow as W


@pytest.mark.parametrize("tid", ["../escape", "_private", "BadName", "x__y", "x/y", "x.py", "", "class", "import"])
def test_ids_cannot_escape_template_directory(tid):
    with pytest.raises(ValueError):
        W.checked_id(tid)


def test_clone_keeps_comments_and_only_replaces_exact_tokens():
    source = '# Keep this comment\nclass Base:\n    id = "base"\n    title = "Old Title"\n    path = "database"\n'
    result = W.clone_source(source, "Base", "New", "base", "new", "Old Title", "New Title")
    ast.parse(result)
    assert "# Keep this comment" in result and '"database"' in result
    assert "class New:" in result and "New Title" in result


def test_scaffold_checks_every_destination_before_writing(tmp_path):
    existing = tmp_path / "tests/test_template_new_map.py"
    existing.parent.mkdir()
    existing.write_text("existing user work")
    with pytest.raises(ValueError, match="overwrite"):
        W.create("new_map", "New Map", "skirmish", root=tmp_path)
    assert existing.read_text() == "existing user work"
    assert not (tmp_path / "atlasforge/templates/new_map.py").exists()


def test_scaffold_is_valid_python_and_has_a_design_brief(tmp_path):
    paths = W.create("new_map", "New Map", "skirmish", root=tmp_path)
    for path in paths[:2]:
        ast.parse(path.read_text())
    source = paths[0].read_text()
    assert "class NewMap" in source and "new_map" in source
    brief = json.loads(paths[2].read_text())
    assert brief["mode"] == "competitive" and not brief["visual_review"]
    assert "distinct layout" in paths[3].read_text()
    assert not (tmp_path / "atlasforge/templates/__init__.py").exists()


def test_scaffold_class_name_does_not_shadow_terrain_imports(tmp_path):
    paths = W.create("symmetry", "Symmetry", "chokepoint", root=tmp_path)
    module = ast.parse(paths[0].read_text())
    assert any(isinstance(node, ast.ClassDef) and node.name == "SymmetryTemplate" for node in module.body)


def test_scaffold_runs_as_an_unregistered_template(tmp_path, monkeypatch):
    from atlasforge import templates
    W.create("workflow_sample", "Workflow Sample", "chokepoint", root=tmp_path)
    monkeypatch.setattr(templates, "__path__", list(templates.__path__) + [str(tmp_path / "atlasforge/templates")])
    t = W.load_template("workflow_sample")
    monkeypatch.setitem(templates._REGISTRY, t.id, t)
    row, d = W.run_case(t, "sample", {}, 1, False, "competitive")
    assert row["passed"], row
    assert d.title == "Workflow Sample" and t.title == "Workflow Sample"


def test_parameter_matrix_covers_booleans_choices_and_combined_extremes():
    class Fake:
        params = (Param("size", "Size", "choice", 12, choices=(12, 16), adv_choices=(8, 12, 16)),
                  Param("gates", "Gates", "int", 2, min=1, max=3, adv_max=8),
                  Param("lava", "Lava", "bool", False))
    cases = list(W.parameter_cases(Fake()))
    assert any(v.get("lava") is True and a for _, v, a in cases)
    assert any(v.get("size") == 8 and a for _, v, a in cases)
    assert cases[-1][1]["size"] == 8 and cases[-1][1]["gates"] == 8


def design():
    return Design(hm=np.full((129, 129), 100, np.float32), sym=Symmetry("ew", 1024, 1024),
                  starts=[(128, 512), (896, 512)], teams=[[(128, 512)], [(896, 512)]],
                  mexes=[dict(x=256, z=256, metal=2, side=0), dict(x=768, z=256, metal=2, side=1)],
                  geos=[], biome={}, title="Test", description="Test")


def test_declared_symmetry_and_metal_income_are_checked():
    d = design()
    W.validate_design(d, "competitive")
    d.mexes[1]["metal"] = 3
    with pytest.raises(ValueError, match="income"):
        W.validate_design(d, "competitive")
    d = design()
    d.hm[0, 0] = 150
    with pytest.raises(ValueError, match="symmetry"):
        W.validate_design(d, "competitive")
    W.validate_design(d, "coop")


def test_naval_brief_cannot_silently_use_land_checks():
    with pytest.raises(ValueError, match="naval movement profile"):
        W.validate_design(design(), "naval")


def test_advanced_gameplay_failure_is_allowed_but_crash_is_not(monkeypatch):
    from atlasforge import forge
    from PIL import Image
    class Fake:
        id = "fake"
    monkeypatch.setattr(forge, "make", lambda *a, **kw: design())
    monkeypatch.setattr(forge, "check", lambda d: (False, ["Closed route"]))
    monkeypatch.setattr(forge, "preview", lambda d, size: Image.new("RGB", (size, size)))
    row, _ = W.run_case(Fake(), "advanced", {}, 1, True, "competitive", False)
    assert row["passed"] and not row["playable"]
    row, _ = W.run_case(Fake(), "safe", {}, 1, False, "competitive", True)
    assert not row["passed"]
    def broken(*a, **kw):
        raise IndexError("broken geometry")
    monkeypatch.setattr(forge, "make", broken)
    row, _ = W.run_case(Fake(), "advanced", {}, 1, True, "competitive", False)
    assert not row["passed"] and "IndexError" in row["error"]


def integration_tree(tmp_path):
    registry = tmp_path / "atlasforge/templates/__init__.py"
    registry.parent.mkdir(parents=True)
    registry.write_text('# user comment\n_REGISTRY = {}\n\ndef all_templates():\n    return list(_REGISTRY.values())\n')
    watermark = tmp_path / "atlasforge/watermark.py"
    watermark.write_text('# stable old codes\nTEMPLATE_CODES = {"procedural": 0, "older": 8}\n')
    brief_path = tmp_path / "docs/template_briefs/new_map.json"
    brief_path.parent.mkdir(parents=True)
    brief = dict(id="new_map", concept="New layout", difference_from_base="Different routes",
                 intended_players="2 teams", routes="Three lanes", economy="Contested centre", visual_review=True)
    brief_path.write_text(json.dumps(brief))
    report_path = tmp_path / "out/template_workflow/new_map/full/report.json"
    report_path.parent.mkdir(parents=True)
    (report_path.parent / "new_map.jpg").write_bytes(b"test-thumbnail")
    return registry, watermark, brief_path, report_path


def test_integration_rejects_stale_reports_without_mutation(tmp_path):
    registry, watermark, _, report = integration_tree(tmp_path)
    report.write_text(json.dumps(dict(id="new_map", level="full", passed=True, source_fingerprint="stale")))
    before = (registry.read_bytes(), watermark.read_bytes())
    with pytest.raises(ValueError, match="stale"):
        W.integrate("new_map", root=tmp_path)
    assert before == (registry.read_bytes(), watermark.read_bytes())


def test_integration_preserves_existing_codes_and_registry_code(tmp_path, monkeypatch):
    registry, watermark, _, report = integration_tree(tmp_path)
    report.write_text(json.dumps(dict(id="new_map", level="full", passed=True,
                                     source_fingerprint=W.fingerprint(tmp_path))))
    class NewMap:
        pass
    monkeypatch.setattr(W, "load_template", lambda tid: NewMap())
    assert W.integrate("new_map", root=tmp_path) == 9
    assert "# user comment" in registry.read_text() and "def all_templates" in registry.read_text()
    assert "from .new_map import NewMap" in registry.read_text()
    namespace = {}
    exec(compile(watermark.read_text(), str(watermark), "exec"), namespace)
    assert namespace["TEMPLATE_CODES"] == {"procedural": 0, "older": 8, "new_map": 9}
    assert (tmp_path / "atlasforge/app/web/thumbs/new_map.jpg").read_bytes() == b"test-thumbnail"
    ast.parse(registry.read_text())


def test_visual_signoff_does_not_stale_geometry_checks(tmp_path):
    _, _, path, _ = integration_tree(tmp_path)
    before = W.fingerprint(tmp_path)
    brief = json.loads(path.read_text())
    brief["visual_review"] = False
    path.write_text(json.dumps(brief))
    assert W.fingerprint(tmp_path) == before
    brief["mode"] = "naval"
    path.write_text(json.dumps(brief))
    assert W.fingerprint(tmp_path) != before


def test_integrating_another_template_does_not_stale_a_batch(tmp_path):
    registry, watermark, _, _ = integration_tree(tmp_path)
    before = W.fingerprint(tmp_path)
    registry.write_text(registry.read_text() + "# another reviewed template registration\n")
    watermark.write_text('TEMPLATE_CODES = {"procedural": 0, "older": 8, "another": 9}\n')
    assert W.fingerprint(tmp_path) == before
    (tmp_path / "atlasforge/terrain.py").write_text("# geometry changed\n")
    assert W.fingerprint(tmp_path) != before


def test_quick_check_writes_real_preview_and_handoff(tmp_path):
    report = W.check("chokepoint", out=tmp_path)
    assert report["passed"], report
    assert (tmp_path / "chokepoint_preview.png").stat().st_size > 1000
    assert (tmp_path / "contact_sheet.png").exists()
    assert (tmp_path / "HANDOFF_chokepoint.md").exists()
    assert json.loads((tmp_path / "report.json").read_text())["level"] == "quick"


def test_missing_capability_is_a_failed_report_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(W, "capability_problem", lambda mode: "Required naval support is missing")
    report = W.check("chokepoint", mode="naval", out=tmp_path)
    assert not report["passed"] and not report["cases"]
    assert "naval support is missing" in report["errors"][0]
    assert (tmp_path / "report.json").exists()


def test_batch_keeps_checking_after_failure_and_returns_nonzero(monkeypatch):
    called = []
    def fake_check(tid, *args):
        called.append(tid)
        return {"passed": tid == "second"}
    monkeypatch.setattr(W, "check", fake_check)
    assert W.main(["check", "first", "second"]) == 1
    assert called == ["first", "second"]

"""Focused contract tests for Mountain Spine."""
import json
import numpy as np
import pytest

from atlasforge import templates
from tools.template_workflow import load_template, validate_design

TID = "mountain_spine"


@pytest.fixture()
def template(monkeypatch):
    t = load_template(TID)
    monkeypatch.setitem(templates._REGISTRY, TID, t)
    return t


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_default_design_is_playable(template, seed):
    from atlasforge import forge
    d = forge.make(TID, {"erosion": 0}, seed=seed, log=lambda *a: None)
    validate_design(d, "competitive")
    ok, lines = forge.check(d)
    assert ok, "\n".join(lines)
    assert len(d.gates) == 4


def test_seed_changes_spine_and_repeats_deterministically(template):
    from atlasforge import forge
    a = forge.make(TID, {"erosion": 0}, seed=1, log=lambda *a: None)
    b = forge.make(TID, {"erosion": 0}, seed=1, log=lambda *a: None)
    c = forge.make(TID, {"erosion": 0}, seed=2, log=lambda *a: None)
    assert np.array_equal(a.hm, b.hm)
    assert not np.array_equal(a.hm, c.hm)


def test_parameter_info_and_preview(template):
    from atlasforge import forge
    json.dumps(template.info())
    d = forge.make(TID, {"erosion": 0}, seed=1, log=lambda *a: None)
    assert forge.preview(d, size=256).size == (256, 256)


def test_advanced_extremes_do_not_crash(template):
    from atlasforge import forge
    for key, values in (("spine_width", (300, 2400)), ("pass_width", (100, 700)),
                        ("form", ("folded", "straight"))):
        for value in values:
            forge.make(TID, {key: value, "erosion": 0}, seed=1, log=lambda *a: None, advanced=True)

"""Focused contract tests for Canyon Network."""
import numpy as np
import pytest

from atlasforge import templates
from tools.template_workflow import load_template, validate_design

TID = "canyon_network"


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


def test_seed_changes_network_and_same_seed_repeats(template):
    from atlasforge import forge
    a = forge.make(TID, {"erosion": 0}, seed=1, log=lambda *a: None)
    again = forge.make(TID, {"erosion": 0}, seed=1, log=lambda *a: None)
    other = forge.make(TID, {"erosion": 0}, seed=2, log=lambda *a: None)
    assert np.array_equal(a.hm, again.hm)
    assert np.array_equal(a.hm, other.hm) is False


def test_info_and_preview(template):
    import json
    from atlasforge import forge
    json.dumps(template.info())
    d = forge.make(TID, {"erosion": 0}, seed=1, log=lambda *a: None)
    assert forge.preview(d, size=256).size == (256, 256)

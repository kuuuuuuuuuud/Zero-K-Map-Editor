"""Focused contract tests for the standalone Chicken Mesa template."""
import json

import numpy as np
import pytest

from atlasforge import templates
from tools.template_workflow import load_template

TID = "chicken_mesa"


@pytest.fixture()
def template(monkeypatch):
    t = load_template(TID)
    monkeypatch.setitem(templates._REGISTRY, TID, t)
    return t


def test_coop_contract_and_ramps(template):
    from atlasforge import forge

    d = forge.make(TID, {"size": 16}, seed=1, log=lambda *a: None)
    assert d.hm.shape == (16 * 64 + 1, 16 * 64 + 1)
    assert d.sym.layout == "diag"
    assert len(d.teams) == 2 and len(d.teams[0]) == 4
    assert len(d.gates) == 3
    assert all(mask.dtype == bool and mask.any() for _, mask in d.gates)
    assert d.keep_clear.any() and np.all(~d.keep_clear | d.tree_block)
    assert len(d.extra_files) > 0
    centre = d.hm.shape[0] // 2
    assert float(d.hm[centre, centre]) > float(d.hm[0, 0]) + 100
    # Summit terrain retains visible relief instead of becoming a broad flat pad.
    patch = d.hm[centre-80:centre+81, centre-80:centre+81]
    assert float(patch.std()) > 2


def test_seed_changes_mesa_and_ramp_arrangement(template):
    from atlasforge import forge

    a = forge.make(TID, {"size": 16}, seed=1, log=lambda *a: None)
    b = forge.make(TID, {"size": 16}, seed=2, log=lambda *a: None)
    assert not np.array_equal(a.hm, b.hm)
    assert any(not np.array_equal(x[1], y[1]) for x, y in zip(a.gates, b.gates))


def test_info_popup_text_is_complete(template):
    json.dumps(template.info())
    for p in template.all_params():
        if p.key in {"mesa_height", "ramps", "ramp_width"}:
            assert len(p.info) > 60

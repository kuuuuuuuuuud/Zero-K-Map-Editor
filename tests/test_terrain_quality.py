"""Seamless symmetry, erosion and advanced-mode limits."""
import numpy as np
import pytest
from scipy import ndimage

from atlasforge import forge
from atlasforge.erosion import erode, symmetric_like
from atlasforge.symmetry import seam_blend
from atlasforge.templates import get


def _kink(h):
    """Mean slope change across the vertical centre line relative to elsewhere (1 = no visible seam)."""
    c = h.shape[1] // 2
    jump = lambda j: np.abs((h[:, j + 1] - h[:, j]) - (h[:, j] - h[:, j - 1])).mean()
    return jump(c) / np.mean([jump(c + k) for k in (-60, -40, 40, 60)])


def test_seam_blend_removes_the_crease():
    rng = np.random.default_rng(4)
    a = ndimage.gaussian_filter(rng.normal(size=(513, 513)), 6)
    hard = a.copy()
    hard[:, 257:] = a[:, :256][:, ::-1]                         # old way: hard mirror copy
    soft = seam_blend(a, "ew")
    assert np.allclose(soft, soft[:, ::-1])                     # exactly symmetric
    assert _kink(hard) > 2.5 * _kink(soft)
    assert 0.85 < soft.std() / a.std() < 1.15                   # no flattened band


@pytest.mark.parametrize("mode,flip", [("ns", lambda x: x[::-1]), ("point", lambda x: x[::-1, ::-1])])
def test_seam_blend_modes(mode, flip):
    a = np.random.default_rng(1).normal(size=(129, 129))
    b = seam_blend(a, mode)
    assert np.allclose(b, flip(b))


def test_erosion_respects_protection_and_symmetry():
    d = forge.make("skirmish", {"size": 8, "erosion": 0}, seed=5, log=lambda *a: None)
    prot = np.zeros(d.hm.shape, bool)
    prot[100:200, 100:200] = True
    e = erode(d.hm, 1.0, protect=prot, seed=1)
    assert np.abs(e - d.hm)[110:190, 110:190].max() < 1e-3
    assert np.abs(e - d.hm).mean() > 0.5
    sym = d.hm + symmetric_like(d.hm, e - d.hm)
    assert np.allclose(sym, sym[::-1, ::-1], atol=1e-3)


def test_general_settings():
    base = forge.make("arena", {"size": 12, "erosion": 0}, seed=2, log=lambda *a: None)
    more = forge.make("arena", {"size": 12, "erosion": 0, "metal": 2.0}, seed=2, log=lambda *a: None)
    assert sum(m["metal"] for m in more.mexes) == pytest.approx(2 * sum(m["metal"] for m in base.mexes), rel=0.02)


def test_advanced_limits():
    t = get("chokepoint")
    with pytest.raises(ValueError):
        t.resolve({"gates": 7})
    assert t.resolve({"gates": 7, "size": 24}, advanced=True)["gates"] == 7
    with pytest.raises(ValueError):
        t.resolve({"gates": 99}, advanced=True)
    d = forge.make("chokepoint", {"gates": 6, "size": 12}, seed=1, log=lambda *a: None, advanced=True)
    assert len(d.gates) == 6

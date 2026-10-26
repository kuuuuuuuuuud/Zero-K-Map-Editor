"""Naval validation must reject real defects without weakening default land checks."""
import numpy as np
import pytest

from atlasforge.checks import report, unit_masks


def ocean():
    h = np.full((129, 129), -100, np.float32)
    return h, [(200, 512)], [(824, 512)]


def test_ship_depth_uses_heavy_ship_limit():
    h = np.array([[-16, -15, -5, 0, 100]] * 5, np.float32)
    assert unit_masks(h)["ships"][0].tolist() == [True, False, False, False, False]


def test_naval_profile_does_not_change_land_requirements():
    h, a, b = ocean()
    assert not report(h, a, b)[0]
    assert report(h, a, b, movement_profile="naval", naval_starts=[a, b])[0]


def test_missing_or_dry_ports_fail():
    h, a, b = ocean()
    assert not report(h, a, b, movement_profile="naval")[0]
    h[64, 25] = 100
    assert not report(h, a, b, movement_profile="naval", naval_starts=[a, b])[0]


def test_severed_shipping_lane_fails():
    h, a, b = ocean()
    h[:, 64] = 20  # amphibians still cross this ridge, ships cannot
    assert not report(h, a, b, movement_profile="naval", naval_starts=[a, b])[0]


def test_isolated_underwater_economy_fails():
    h, a, b = ocean()
    h[10:30, 10:30] = 100
    h[16:24, 16:24] = -100
    mexes = [dict(x=160, z=160, metal=2, side=0)]
    assert not report(h, a, b, mexes, movement_profile="naval", naval_starts=[a, b])[0]


def test_blocked_water_is_not_a_route():
    h, a, b = ocean()
    blocked = np.zeros(h.shape, bool)
    blocked[:, 64] = True
    assert not report(h, a, b, blocked=blocked, movement_profile="naval", naval_starts=[a, b])[0]


def test_unknown_profile_is_rejected():
    h, a, b = ocean()
    with pytest.raises(ValueError):
        report(h, a, b, movement_profile="typo")

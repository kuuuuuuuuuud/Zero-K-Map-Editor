import numpy as np
import pytest

from atlasforge import SQ
from tools.terrain_variety import flat_metrics, height_difference, run, slope_percent


def test_slope_percent_on_elmo_scale():
    h = np.tile((np.arange(9)[:, None] * SQ), (1, 9)).astype(np.float32)
    s = slope_percent(h)
    assert s[4, 4] == pytest.approx(100.0, abs=0.5)


def test_flat_plane_is_one_patch():
    h = np.full((8, 8), 10.0, dtype=np.float32)
    m = flat_metrics(h)
    assert m["flat_share"] == pytest.approx(1.0)
    assert m["largest_flat"] == pytest.approx(1.0)


def test_open_water_has_no_land():
    h = np.full((8, 8), -4.0, dtype=np.float32)
    m = flat_metrics(h)
    assert m["flat_share"] == 0.0
    assert m["largest_flat"] == 0.0


def test_steep_land_is_not_flat():
    h = (np.tile((np.arange(8)[:, None] * SQ), (1, 8))).astype(np.float32) + 4.0
    m = flat_metrics(h)
    assert m["flat_share"] == pytest.approx(0.0)


def test_largest_patch_ignores_background_and_water():
    h = np.zeros((64, 64), dtype=np.float32)
    h[:, 31] = -5.0
    land = int((h >= 0).sum())
    m = flat_metrics(h)
    assert m["flat_share"] == pytest.approx(1.0)
    assert m["largest_flat"] == pytest.approx((64 * 32) / land, rel=1e-9)


def test_height_difference_is_normalised():
    ref = np.zeros((4, 4), dtype=np.float32)
    ref[0, 0] = 10.0
    other = ref.copy()
    other[1, 1] += 5.0
    assert height_difference(ref, other) == pytest.approx(5.0 / (16 * 10))


def test_height_difference_identical_is_zero():
    ref = np.random.default_rng(0).integers(-8, 40, size=(16, 16)).astype(np.float32)
    assert height_difference(ref, ref.copy()) == 0.0


def test_run_small_real_template():
    rows, failures = run(["arena"], [1, 2], size=12)
    assert not failures
    assert [(r[0], r[2]) for r in rows] == [("arena", 1), ("arena", 2)]
    for _tid, used_size, _seed, flat, largest, diff in rows:
        assert used_size == 12
        assert 0.0 <= largest <= flat <= 1.0
        assert diff >= 0.0
    assert rows[0][5] == 0.0

"""Naval smoothing ticket: geometric joins, protected openings, routes and spacing."""
import numpy as np
import pytest
from scipy.spatial.distance import pdist, cdist

from atlasforge import forge
from atlasforge.terrain import grid
from atlasforge.templates._naval import soften_seabed
from tools.naval_quality import curvature, inspect_design

IDS = ('open_sea', 'archipelago', 'straits', 'coastal_front', 'atoll')


@pytest.mark.parametrize('tid', IDS)
@pytest.mark.parametrize('seed', range(1, 11))
def test_naval_contacts_routes_and_economy(tid, seed):
    d, _, metrics = inspect_design(tid, seed)
    ok, lines = forge.check(d)
    assert ok, '\n'.join(lines)
    for kind, measured in metrics.items():
        if kind == 'flank_contacts' and measured['candidates'] == 0:
            # This mainland and its submerged shelf do not intersect above the
            # sea floor. An absent join has no curvature ratio to measure.
            assert tid == 'coastal_front'
            continue
        assert measured['samples'] >= 100, (tid, seed, kind, measured)
        assert measured['ratio'] <= 1.5, (tid, seed, kind, measured)
    assert set(metrics) == {'seam', 'flank_contacts'}
    assert np.array_equal(d.hm, d.hm[:, ::-1])
    fixed = [m for m in d.mexes if m.get('fixed')]
    expansion = [m for m in d.mexes if not m.get('fixed')]
    assert len(fixed) == 6
    assert len(expansion) >= 12
    W = d.sym.W
    for m in expansion:
        assert min(m['x'], m['z'], W-m['x'], W-m['z']) >= 0.08*W
        assert abs(W-2*m['x']) >= 0.08*W
    west = [(m['x'], m['z']) for m in expansion if m['side'] == 0]
    gap = max(300, 0.06*W)
    assert pdist(west).min() >= gap - 1e-5
    assert cdist(west, [(m['x'], m['z']) for m in fixed]).min() >= gap - 1e-5


def test_filter_preserves_shores_ports_and_ship_depth():
    xx, zz = grid(257)
    h = (100-abs(xx-1024)*0.5).astype(np.float32)
    ports = [(200, 700), (1848, 700)]
    result = soften_seabed(h, xx, zz, ports)
    protected = h >= -20
    for x, z in ports:
        protected |= np.hypot(xx-x, zz-z) <= 500
    assert np.array_equal(h[protected], result[protected])
    assert np.isfinite(result).all()
    assert (result[h < -15] < -15).all()


def test_curvature_metric_detects_a_hard_v_crease():
    xx, zz = grid(257)
    h = (-180 + abs(xx-1024)*0.08 + np.sin(zz/100)*0.1).astype(np.float32)
    mask = (abs(xx-1024) <= 16) & (zz > 100) & (zz < 1900)
    assert curvature(h, mask, 1, 0)['ratio'] > 20


@pytest.mark.parametrize('tid', IDS)
@pytest.mark.parametrize('mex_count,geos', ((6, 0), (20, 3)))
def test_naval_general_resource_controls(tid, mex_count, geos):
    d = forge.make(tid, {'erosion': 0, 'mex_count': mex_count, 'geos': geos}, seed=4, log=lambda *a: None)
    assert forge.check(d)[0]
    assert sum(m.get('fixed', False) for m in d.mexes) == 6
    assert len(d.mexes) == mex_count * 2
    assert len(d.geos) == geos * 2

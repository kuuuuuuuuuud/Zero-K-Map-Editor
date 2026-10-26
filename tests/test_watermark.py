"""Hidden watermark: found in marked heightmaps, survives common edits, absent in other maps."""
import numpy as np
from scipy import ndimage

from atlasforge import watermark as W


def _terrain(seed, n=513):
    rng = np.random.default_rng(seed)
    h = ndimage.gaussian_filter(rng.normal(size=(n, n)), 10)
    h = (h - h.min()) / (h.max() - h.min())
    return np.round(h * 60000 + 2000).astype(np.uint16)


def test_marked_and_clean():
    for seed in range(5):
        clean = _terrain(seed)
        r0 = W.detect(clean)
        assert not r0["forge"] and r0["payload"] is None and abs(r0["pattern_z"]) < 5
        m = W.embed(clean, -60.0, 600.0, "0.4.0", "volcano", 1234 + seed, build_id=7)
        r = W.detect(m)
        assert r["forge"] and r["confidence"] == "certain"
        assert r["payload"]["template"] == "volcano" and r["payload"]["seed"] == 1234 + seed
        assert r["payload"]["tool_version"] == "0.4.0"
        assert np.abs(m.astype(int) - clean).max() * 660 / 65535 < 0.1        # under 0.1 elmos


def test_survives_edits():
    m = W.embed(_terrain(9), -60.0, 600.0, "0.4.0", "river", 5).astype(np.float64)
    for edited in (np.floor(m / 2) * 2,                                       # lowest bit wiped
                   ndimage.gaussian_filter(m, 0.7),                          # slight smoothing
                   m * 0.9 + 3000):                                          # height range changed
        assert W.detect(np.clip(edited, 0, 65535).astype(np.uint16))["forge"]
